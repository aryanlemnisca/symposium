"""Product brainstorm engine — phase-aware session using shared phase components."""

import asyncio
import logging
import time
from typing import Callable, Awaitable

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client
from backend.engine.phase_loop import (
    _build_agents,
    run_phase,
    PhaseLoopState,
    PhaseResult,
    EventCallback,
)
from backend.engine.phase_overseer import PhaseOverseer
from backend.engine.prd_panel import run_prd_mini_panel
from backend.engine.synthesis import generate_synthesis_and_prd

logger = logging.getLogger("symposium")


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    """Retry an async callable with exponential backoff."""
    delays = [2, 4, 8, 16]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            logger.warning(
                f"[{label}] attempt {attempt+1}/{max_retries+1} failed: {e}"
            )
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    logger.error(f"[{label}] all {max_retries+1} attempts failed")
    return None


# ---------------------------------------------------------------------------
# Executive summary prompt — product mode variant
# ---------------------------------------------------------------------------

_EXEC_SUMMARY_PROMPT = """\
You are a senior product leader reading the output of a structured product brainstorm.

You have been given per-phase artifacts from {phase_count} phases of ideation and debate.

PHASE ARTIFACTS:
{all_artifacts}

Produce the summary in this EXACT format:

EXECUTIVE SUMMARY
━━━━━━━━━━━━━━━━━

KEY PRODUCT DIRECTION:
[2-3 sentences — the winning concept, form factor, and target user]

WHAT'S VALIDATED:
· [3-5 bullet points — decisions the panel confirmed with conviction]

WHAT NEEDS WORK:
· [3-5 bullet points — areas still fuzzy, contested, or under-specified]

KEY RISKS:
· [2-3 bullet points — risks that could derail the product even if built correctly]

RECOMMENDED NEXT STEP:
[One sentence — the single most important thing to do now]

Rules:
- No hedging. Be direct.
- Each bullet must be specific and actionable — no vague summaries.
- Keep the entire summary under 300 words.\
"""


async def _generate_executive_summary(
    support_agent: AssistantAgent,
    phases: list[dict],
) -> str:
    """Generate a crisp executive summary from all phase artifacts."""
    all_artifacts = "\n\n---\n\n".join(
        f"Phase {p.get('number', '?')} — {p.get('name', '?')}:\n{p.get('artifact', 'No artifact')}"
        for p in phases if p.get("artifact")
    )

    prompt = _EXEC_SUMMARY_PROMPT.format(
        phase_count=len(phases),
        all_artifacts=all_artifacts,
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
# Product context builder
# ---------------------------------------------------------------------------

def _product_context_builder(
    problem_statement_msg: TextMessage,
    phases: list[dict],
):
    """Return a context builder closure for product brainstorm mode.

    The returned callable matches the signature expected by run_phase:
        (phase_messages, phase_index, phases_list) -> list[TextMessage]
    """

    def _builder(phase_messages: list, phase_index: int, phases_list: list[dict]) -> list:
        context = [problem_statement_msg]

        # Carry forward previous phase artifacts
        for prev_phase in phases_list[:phase_index]:
            if prev_phase.get("artifact"):
                context.append(TextMessage(
                    content=prev_phase["artifact"],
                    source="Overseer",
                ))

        # Current phase conversation
        context.extend(phase_messages)
        return context

    return _builder


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_product_session(
    config: EngineConfig,
    phases: list[dict],
    emit: EventCallback,
) -> tuple[list, dict, dict]:
    """Run a product brainstorm session.

    Returns (all_messages, stats, outputs).
    outputs dict has keys like 'transcript.md', 'phase_1_artifact.md',
    'synthesis.md', 'executive_summary.md'.
    """

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
        description="Product brainstorm support agent",
        system_message=(
            "You are a precise, concise assistant. "
            "Follow instructions exactly. Output only what is asked."
        ),
        model_client=support_client,
    )

    # --- Phase overseer (no documents in product mode) ---
    min_rounds = getattr(config, "stress_test_min_rounds_per_phase", 10)
    overseer = PhaseOverseer(
        support_agent=support_agent,
        phases=phases,
        agent_names=config.agent_names,
        documents=None,
        min_rounds_per_phase=min_rounds,
    )

    # --- Session state ---
    state = PhaseLoopState()
    problem_statement_msg = TextMessage(content=config.problem_statement, source="user")
    state.all_messages.append(problem_statement_msg)

    context_builder = _product_context_builder(problem_statement_msg, phases)

    await emit("session_started", {
        "max_rounds": config.max_rounds,
        "total_phases": len(phases),
    })

    # --- Phase loop ---
    phase_results: list[PhaseResult] = []

    for phase_index, phase in enumerate(phases):
        result = await run_phase(
            agents=agent_map,
            support_agent=support_agent,
            overseer=overseer,
            phase=phase,
            phase_index=phase_index,
            context_builder=context_builder,
            config=config,
            emit=emit,
            state=state,
        )
        phase_results.append(result)

    # --- PRD panel (optional) ---
    panel_messages = []
    if config.prd_panel_rounds and config.prd_panel_rounds > 0:
        await emit("phase_transition", {"phase": "prd_panel"})

        # Build artifact dict from all phase artifacts for prd_panel interface
        artifact_text = "\n\n---\n\n".join(
            f"Phase {p['number']}: {p['name']}\n{p.get('artifact', '')}"
            for p in phases if p.get("artifact")
        )
        # run_prd_mini_panel expects a living_artifact dict
        living_artifact = {"Brainstorm Phase Artifacts": artifact_text}

        panel_messages = await run_prd_mini_panel(config, living_artifact, emit)

    # --- Synthesis & PRD ---
    await emit("phase_transition", {"phase": "synthesis"})

    # Build panel text: prefer PRD panel output if available, else use phase artifacts
    if panel_messages:
        synthesis_input = panel_messages
    else:
        # Create synthetic messages from phase artifacts so synthesis can process them
        synthesis_input = [
            TextMessage(
                content=(
                    f"Phase {p['number']}: {p['name']}\n\n{p.get('artifact', '')}"
                ),
                source="Overseer",
            )
            for p in phases if p.get("artifact")
        ]

    synthesis_text, prd_text = await generate_synthesis_and_prd(
        model=config.main_model,
        api_key=config.gemini_api_key,
        temperature=config.temperature,
        panel_messages=synthesis_input,
    )

    await emit("synthesis_complete", {"content": synthesis_text})
    await emit("prd_complete", {"content": prd_text})

    # --- Executive summary ---
    await emit("phase_transition", {"phase": "executive_summary"})
    exec_summary = await _generate_executive_summary(support_agent, phases)
    await emit("executive_summary", {"content": exec_summary})

    # --- Build transcript ---
    transcript_lines = []
    for msg in state.all_messages:
        source = getattr(msg, "source", "?")
        content = getattr(msg, "content", "")
        transcript_lines.append(f"[{source}]:\n{content}\n")
    transcript = "\n---\n\n".join(transcript_lines)

    # --- Build outputs dict ---
    outputs: dict[str, str] = {
        "transcript.md": transcript,
        "synthesis.md": synthesis_text,
        "prd.md": prd_text,
        "executive_summary.md": exec_summary,
    }

    # Add per-phase artifacts
    for p in phases:
        if p.get("artifact"):
            key = f"phase_{p['number']}_artifact.md"
            outputs[key] = p["artifact"]

    # Add PRD panel transcript if it ran
    if panel_messages:
        panel_transcript = "\n\n---\n\n".join(
            f"[{getattr(m, 'source', '?')}]:\n{getattr(m, 'content', '')}"
            for m in panel_messages
        )
        outputs["prd_panel.md"] = panel_transcript

    # --- Final stats ---
    last_result = phase_results[-1] if phase_results else None
    stats = {
        "total_rounds": state.total_round_count,
        "gate_skips": state.total_gate_skips,
        "overseer_injections": state.total_overseer_injections,
        "persona_turns": dict(state.persona_turns),
        "phases_completed": len(phases),
        "prd_panel_ran": len(panel_messages) > 0,
        "terminated_by": "complete",
        "elapsed_seconds": round(time.monotonic() - state.start_time),
    }

    await emit("session_complete", {"stats": stats})

    return state.all_messages, stats, outputs
