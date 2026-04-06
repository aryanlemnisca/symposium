"""Problem Discussion brainstorm engine — phase-aware using shared components."""

import logging
import time

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client
from backend.engine.phase_loop import (
    EventCallback,
    PhaseLoopState,
    run_phase,
    _build_agents,
    _call_with_retry,
)
from backend.engine.phase_overseer import PhaseOverseer
from backend.engine.outputs import build_transcript

logger = logging.getLogger("symposium")


# ---------------------------------------------------------------------------
# Context builder — problem mode (no documents)
# ---------------------------------------------------------------------------

def _problem_context_builder(
    problem_statement_msg: TextMessage,
    phases: list[dict],
):
    """Return a closure matching the context_builder signature for run_phase."""

    def _builder(phase_messages: list, phase_index: int, all_phases: list[dict]) -> list:
        context = [problem_statement_msg]
        for prev_phase in all_phases[:phase_index]:
            if prev_phase.get("artifact"):
                context.append(
                    TextMessage(content=prev_phase["artifact"], source="Overseer")
                )
        context.extend(phase_messages)
        return context

    return _builder


# ---------------------------------------------------------------------------
# Conclusion report
# ---------------------------------------------------------------------------

_CONCLUSION_PROMPT = """\
You are producing a structured Conclusion Report for a Problem Discussion session.

PHASE ARTIFACTS:
{artifact_text}

Output using this exact template:

# Conclusion Report

## 1. Problem Restated
[One paragraph restating the problem as understood after discussion]

## 2. Key Agreements
[What the panel definitively concluded — bullet points]

## 3. Key Tensions
[Where disagreement remained and why it matters — bullet points]

## 4. Recommended Direction
[The panel's strongest supported conclusion — 1-2 paragraphs]

## 5. Dissenting Views
[Minority positions worth preserving — bullet points with who held them]

## 6. Open Questions
[Specific questions that would change direction if answered — bullet points]

## 7. Next Steps
[Concrete actions — bullet points]\
"""


async def _generate_conclusion(
    support_agent: AssistantAgent,
    phases: list[dict],
    config: EngineConfig,
    emit: EventCallback,
) -> str:
    """Generate a structured conclusion report from all phase artifacts."""
    await emit("phase_transition", {"phase": "conclusion"})

    artifact_text = "\n\n---\n\n".join(
        f"Phase {p['number']}: {p['name']}\n{p.get('artifact', '')}"
        for p in phases if p.get("artifact")
    )
    if not artifact_text:
        artifact_text = "No phase artifacts were generated."

    client = make_client(
        model=config.main_model,
        api_key=config.gemini_api_key,
        temperature=config.temperature,
    )
    writer = AssistantAgent(
        name="ConclusionWriter",
        system_message=(
            "You produce structured conclusion reports from brainstorming discussions. "
            "Follow the template exactly."
        ),
        model_client=client,
    )

    prompt = _CONCLUSION_PROMPT.format(artifact_text=artifact_text)

    async def _call():
        return await writer.on_messages(
            [TextMessage(content=prompt, source="user")], CancellationToken()
        )

    response = await _call_with_retry(_call, max_retries=3, label="conclusion")
    if response and response.chat_message:
        return response.chat_message.content
    return "Conclusion generation failed."


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

_EXEC_SUMMARY_PROMPT = """\
You are a senior analyst reading the output of a structured Problem Discussion session.

You have been given:
1. Per-phase discussion artifacts from {phase_count} phases
2. A conclusion report

Your job: produce a crisp executive summary that a busy leader can read in 2 minutes.

PHASE ARTIFACTS:
{all_artifacts}

CONCLUSION:
{conclusion}

Produce the summary in this EXACT format:

EXECUTIVE SUMMARY
━━━━━━━━━━━━━━━━━

CORE FINDING: [one line — the single most important takeaway]

KEY AGREEMENTS:
· [3-5 bullet points — what the panel definitively concluded, each one sentence]

KEY TENSIONS:
· [2-3 bullet points — where disagreement remained and why it matters]

RISKS:
· [2-3 bullet points — risks that could derail progress if ignored]

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
    conclusion: str,
) -> str:
    """Generate a crisp executive summary from all artifacts + conclusion."""
    all_artifacts = "\n\n---\n\n".join(
        f"Phase {p.get('number', '?')} — {p.get('name', '?')}:\n{p.get('artifact', 'No artifact')}"
        for p in phases if p.get("artifact")
    )

    prompt = _EXEC_SUMMARY_PROMPT.format(
        phase_count=len(phases),
        all_artifacts=all_artifacts,
        conclusion=conclusion,
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

async def run_problem_session(
    config: EngineConfig,
    phases: list[dict],
    emit: EventCallback,
) -> tuple[list, dict, dict]:
    """Run a problem discussion session.

    Returns (all_messages, stats, outputs).
    outputs dict has keys like 'transcript.md', 'phase_1_artifact.md',
    'conclusion.md', 'executive_summary.md'
    """

    # 1. Build agents
    agents_list = _build_agents(config)
    agent_map = {a.name: a for a in agents_list}

    support_client = make_client(
        model=config.support_model,
        api_key=config.gemini_api_key,
        temperature=0.3,
    )
    support_agent = AssistantAgent(
        name="Support",
        description="Problem discussion support agent",
        system_message=(
            "You are a precise, concise assistant. Follow instructions exactly. "
            "Output only what is asked."
        ),
        model_client=support_client,
    )

    # 2. Create PhaseOverseer (no documents)
    min_rounds = getattr(config, "stress_test_min_rounds_per_phase", 10)
    overseer = PhaseOverseer(
        support_agent=support_agent,
        phases=phases,
        agent_names=config.agent_names,
        documents=None,
        min_rounds_per_phase=min_rounds,
    )

    # 3. Create PhaseLoopState
    problem_statement_msg = TextMessage(
        content=config.problem_statement, source="user"
    )
    state = PhaseLoopState()
    state.all_messages.append(problem_statement_msg)

    context_builder = _problem_context_builder(problem_statement_msg, phases)

    await emit("session_started", {
        "max_rounds": config.max_rounds,
        "total_phases": len(phases),
    })

    # 4. Loop through phases
    for phase_index in range(len(phases)):
        result = await run_phase(
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

    # 5. Generate conclusion report from all phase artifacts
    conclusion = await _generate_conclusion(
        support_agent, phases, config, emit
    )
    await emit("conclusion_complete", {"content": conclusion})

    # 6. Generate executive summary
    await emit("phase_transition", {"phase": "executive_summary"})
    exec_summary = await _generate_executive_summary(
        support_agent, phases, conclusion
    )
    await emit("executive_summary", {"content": exec_summary})

    # 7. Build outputs dict
    outputs: dict[str, str] = {}

    # Transcript
    stats = {
        "total_rounds": state.total_round_count,
        "gate_skips": state.total_gate_skips,
        "overseer_injections": state.total_overseer_injections,
        "persona_turns": dict(state.persona_turns),
        "phases_completed": len(phases),
        "elapsed_seconds": round(time.monotonic() - state.start_time),
        "terminated_by": "phases_complete",
        "mode": "problem",
    }

    outputs["transcript.md"] = build_transcript(
        state.all_messages, stats, config.agent_names
    )

    # Per-phase artifacts
    for p in phases:
        if p.get("artifact"):
            outputs[f"phase_{p['number']}_artifact.md"] = p["artifact"]

    # Conclusion and executive summary
    outputs["conclusion.md"] = conclusion
    outputs["executive_summary.md"] = exec_summary

    await emit("session_complete", {
        "terminated_by": "phases_complete",
        "total_rounds": state.total_round_count,
        "phases_completed": len(phases),
    })

    return state.all_messages, stats, outputs
