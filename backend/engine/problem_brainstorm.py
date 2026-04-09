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
You are producing a structured Conclusion Report for a rigorous Problem Discussion session.

The panel has debated this problem across {phase_count} phases. Each phase produced a structured artifact with confirmed findings, contested points, and open questions. Your job is to synthesize everything into a decision-ready document.

PHASE ARTIFACTS:
{artifact_text}

Output using this exact template:

# Conclusion Report

## 1. Problem Restated
[One paragraph restating the problem as the panel now understands it — not how it was originally framed, but how it evolved through discussion. Include any reframing that happened.]

## 2. Root Causes Identified
[What the panel identified as the fundamental drivers of this problem — bullet points with evidence from discussion. Tag each: [confirmed] if panel agreed, [contested] if debated]

## 3. Key Agreements
[What the panel definitively concluded — bullet points. Each must name WHO agreed and WHAT evidence supported it. Only include genuinely locked decisions.]

## 4. Key Tensions Unresolved
[Where disagreement remained and why it matters — bullet points. For each: state both positions, who held them, and why resolution matters for next steps.]

## 5. Frameworks & Mental Models Applied
[What analytical frameworks, analogies, or mental models the panel used to reason about this problem — bullet points. Note which ones were productive vs. misleading.]

## 6. Recommended Direction
[The panel's strongest supported path forward — 2-3 paragraphs. This must flow logically from the root causes and agreements above. Include specific conditions under which this recommendation changes.]

## 7. Dissenting Views Worth Preserving
[Minority positions that could prove correct under different assumptions — bullet points with who held them and under what conditions they'd be right.]

## 8. Critical Unknowns
[Specific questions where the answer would materially change the recommendation — bullet points. For each: what you'd need to learn, how you'd learn it, and what changes if the answer goes the other way.]

## 9. Immediate Next Steps
[Concrete, assignable actions — numbered list. Each must have: what to do, why it's urgent, and what it unblocks.]

Rules:
- Be specific. "Do more research" is not a next step. "Interview 5 operations managers about X to validate Y" is.
- Name the agents who held each position — readers need to understand the diversity of perspectives.
- If the panel converged too quickly on a topic, flag it — premature consensus is a risk.
- Do not soften disagreements. Preserved tension is more useful than false harmony.\
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

    prompt = _CONCLUSION_PROMPT.format(
        phase_count=len(phases),
        artifact_text=artifact_text,
    )

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

CORE FINDING:
[2-3 sentences — the single most important takeaway from the entire discussion. What did the panel discover that wasn't obvious before?]

ROOT CAUSE:
[1-2 sentences — what the panel identified as the fundamental driver of this problem]

WHAT'S SETTLED:
· [3-5 bullet points — decisions the panel locked with evidence, each one sentence]

WHAT'S STILL CONTESTED:
· [2-3 bullet points — where smart people disagreed and why both sides have merit]

BLIND SPOTS FLAGGED:
· [1-2 bullet points — areas the panel identified as under-examined or where premature consensus occurred]

RECOMMENDED PATH:
[2-3 sentences — the strongest supported direction, with the key condition that would change it]

RECOMMENDED NEXT STEP:
[One sentence — the single most important thing to do before anything else]

Rules:
- No hedging. Be direct.
- Each bullet must be specific and actionable — no vague summaries.
- If the panel agreed too easily on something important, flag it.
- Keep the entire summary under 350 words.\
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
    # Scale global round budget to the per-phase minimum so the overseer
    # is the sole authority on phase transitions (prevents late phases
    # getting squeezed to 4-5 rounds by a too-low session-wide cap).
    config.max_rounds = max(config.max_rounds, len(phases) * min_rounds)
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
