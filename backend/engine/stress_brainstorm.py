"""Stress test brainstorm — phase-aware loop using shared components."""

import logging
import time
from typing import Callable, Awaitable

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client
from backend.engine.phase_loop import (
    run_phase,
    PhaseLoopState,
    PhaseResult,
    _build_agents,
    _call_with_retry,
    EventCallback,
)
from backend.engine.phase_overseer import PhaseOverseer

logger = logging.getLogger("symposium")


# ---------------------------------------------------------------------------
# Stress-test-specific context builder
# ---------------------------------------------------------------------------

def _stress_context_builder(
    problem_statement_msg: TextMessage,
    review_instructions: str,
    documents: list[dict],
    phases: list[dict],
) -> Callable:
    """Return a context-builder closure matching the signature expected by run_phase.

    The returned callable has signature:
        (phase_messages, phase_index, phases) -> list[TextMessage]
    """

    def _build(phase_messages: list, phase_index: int, _phases: list[dict]) -> list:
        context: list = [problem_statement_msg]

        # Review instructions
        if review_instructions:
            context.append(TextMessage(content=review_instructions, source="system"))

        # All documents — full text always available
        doc_text = "\n\n".join(
            f"[Document: {d['filename']}]\n{d['content_text']}"
            for d in documents
        )
        if doc_text:
            context.append(
                TextMessage(
                    content=f"UPLOADED DOCUMENTS\n{'=' * 40}\n\n{doc_text}",
                    source="system",
                )
            )

        # Previous phase artifacts (carry-forward decisions)
        for prev_phase in phases[:phase_index]:
            if prev_phase.get("artifact"):
                context.append(
                    TextMessage(content=prev_phase["artifact"], source="Overseer")
                )

        # Phase conversation history
        context.extend(phase_messages)
        return context

    return _build


# ---------------------------------------------------------------------------
# Final verdict prompt (kept from StressOverseer)
# ---------------------------------------------------------------------------

_FINAL_VERDICT_PROMPT = """\
You are producing the final readiness verdict for a stress-test review session.

The following phase artifacts were produced during the session:
{all_phase_artifacts}

Produce the final verdict in this exact format:

STRESS TEST — FINAL READINESS VERDICT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OVERALL VERDICT
READY / NOT READY / CONDITIONALLY READY

[One paragraph explaining the verdict]

BLOCKING ISSUES
[Must be resolved before the next step — specific, actionable]
· [issue]: [what must change]

NON-BLOCKING ISSUES
[Should be addressed but do not block progress]
· [issue]: [recommendation]

CONFIRMED SOUND — DO NOT REVISIT
[Items that survived stress-testing across all phases]
· [item]

CROSS-PHASE CONTRADICTIONS
[Places where findings in one phase conflict with another]
· [contradiction]: [which phases · what the conflict is]

RECOMMENDED FIRST ACTION
[The single most important thing to do before proceeding]

Be direct. Do not hedge. This verdict will be used to make a real decision.\
"""


async def _generate_final_verdict(
    support_agent: AssistantAgent,
    phases: list[dict],
) -> str:
    """Generate final readiness verdict from all phase artifacts."""
    all_artifacts = "\n\n---\n\n".join(
        p.get("artifact", "No artifact") for p in phases if p.get("artifact")
    )
    prompt = _FINAL_VERDICT_PROMPT.format(all_phase_artifacts=all_artifacts)

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, max_retries=3, label="final_verdict")
    if response and response.chat_message:
        return response.chat_message.content
    return "Verdict generation failed."


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

_EXEC_SUMMARY_PROMPT = """\
You are a senior executive reading the output of a structured document stress-test review.

You have been given:
1. Per-phase review artifacts from {phase_count} phases
2. A final readiness verdict

Your job: produce a crisp executive summary that a busy leader can read in 2 minutes.

PHASE ARTIFACTS:
{all_artifacts}

FINAL VERDICT:
{verdict}

Produce the summary in this EXACT format:

EXECUTIVE SUMMARY
━━━━━━━━━━━━━━━━━

VERDICT: [one line — Ready / Not Ready / Conditionally Ready + one sentence why]

WHAT'S SOUND:
· [3-5 bullet points — the strongest confirmed elements, each one sentence]

WHAT MUST CHANGE:
· [3-5 bullet points — the most critical issues, each one sentence with specific action]

KEY RISKS:
· [2-3 bullet points — risks that could derail execution even if issues are fixed]

RECOMMENDED NEXT STEP:
[One sentence — the single most important thing to do now]

Rules:
- No hedging. Be direct.
- Each bullet must be specific and actionable — no vague summaries.
- If the verdict is "Not Ready," lead with what blocks progress.
- Keep the entire summary under 300 words.\
"""


async def _generate_executive_summary(
    support_agent: AssistantAgent,
    phases: list[dict],
    verdict: str,
) -> str:
    """Generate a crisp executive summary from all artifacts + verdict."""
    all_artifacts = "\n\n---\n\n".join(
        f"Phase {p.get('number', '?')} — {p.get('name', '?')}:\n{p.get('artifact', 'No artifact')}"
        for p in phases if p.get("artifact")
    )

    prompt = _EXEC_SUMMARY_PROMPT.format(
        phase_count=len(phases),
        all_artifacts=all_artifacts,
        verdict=verdict,
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, max_retries=5, label="exec_summary")
    if response and response.chat_message:
        return response.chat_message.content
    return "Executive summary generation failed."


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_stress_test(
    config: EngineConfig,
    phases: list[dict],
    documents: list[dict],
    review_instructions: str,
    emit: EventCallback,
    receive,  # kept for signature compat — unused
) -> tuple[list, dict, list[dict], str, str]:
    """Run a stress test session. Returns (messages, stats, phases, verdict, exec_summary)."""

    # --- Build agents ---
    agents_list = _build_agents(config)
    agent_map = {a.name: a for a in agents_list}

    support_client = make_client(
        model=config.support_model,
        api_key=config.gemini_api_key,
        temperature=0.3,
    )
    support_agent = AssistantAgent(
        name="Support",
        description="Stress test support agent",
        system_message="You are a precise, concise assistant. Follow instructions exactly.",
        model_client=support_client,
    )

    # --- Build overseer (shared component) ---
    min_rounds_per_phase = getattr(config, "stress_test_min_rounds_per_phase", 20)

    overseer = PhaseOverseer(
        support_agent=support_agent,
        phases=phases,
        agent_names=config.agent_names,
        documents=documents,
        min_rounds_per_phase=min_rounds_per_phase,
    )

    # --- Build shared state ---
    state = PhaseLoopState()
    state.all_messages = [TextMessage(content=config.problem_statement, source="user")]

    # --- Build context builder closure ---
    context_builder = _stress_context_builder(
        problem_statement_msg=state.all_messages[0],
        review_instructions=review_instructions,
        documents=documents,
        phases=phases,
    )

    await emit("session_started", {
        "max_rounds": config.max_rounds,
        "total_phases": len(phases),
    })

    # --- Phase loop ---
    for phase_index in range(len(phases)):
        result: PhaseResult = await run_phase(
            agents=agent_map,
            support_agent=support_agent,
            overseer=overseer,
            phase=phases[phase_index],
            phase_index=phase_index,
            context_builder=context_builder,
            config=config,
            emit=emit,
            state=state,
        )

    # --- Final verdict ---
    await emit("verdict_generating", {})
    verdict = await _generate_final_verdict(support_agent, phases)
    await emit("verdict_complete", {"content": verdict})

    # --- Executive summary ---
    await emit("phase_transition", {"phase": "executive_summary"})
    exec_summary = await _generate_executive_summary(support_agent, phases, verdict)
    await emit("executive_summary", {"content": exec_summary})

    # --- Stats ---
    stats = {
        "total_rounds": state.total_round_count,
        "gate_skips": state.total_gate_skips,
        "overseer_injections": state.total_overseer_injections,
        "persona_turns": dict(state.persona_turns),
        "phases_completed": len(phases),
        "elapsed_seconds": round(time.monotonic() - state.start_time),
        "terminated_by": "verdict",
    }

    return state.all_messages, stats, phases, verdict, exec_summary
