"""Hybrid selector — rotation floor + LLM contextual pick."""

import asyncio
from typing import Optional
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

_SELECTOR_PROMPT = """\
Select the next speaker from these eligible candidates:
{candidates}

Last speaker: {last_speaker}
Last message (first 200 chars): "{last_message_preview}"
Current phase: {phase_context}

Choose who adds the most value right now:
  · Strong claim just made       → select someone who challenges it
  · Product concept proposed     → prefer product/operations thinkers
  · Discussion too abstract      → prefer domain experts
  · Converging too fast          → prefer challengers/outsiders
  · Technical/mechanistic claim  → prefer scientific rigor agents

Respond with ONLY the exact name of one candidate. No explanation.\
"""


def _phase_context(turn: int, max_rounds: int) -> str:
    pct = turn / max(max_rounds, 1)
    if pct <= 0.2:
        return "Phase 1 — stake positions, raise all perspectives"
    elif pct <= 0.45:
        return "Phase 2 — cross-debate, force disagreement"
    elif pct <= 0.65:
        return "Phase 3 — converge on 2-4 named concepts"
    elif pct <= 0.85:
        return "Phase 4 — stress-test shortlist, punch holes, rank"
    else:
        return "Phase 5 — final refinement, nail interaction model and output format"


def _last_persona_speaker(messages: list, agent_names: list[str]) -> Optional[str]:
    for m in reversed(messages):
        if getattr(m, "source", "") in agent_names:
            return getattr(m, "source")
    return None


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


async def hybrid_selector(
    support_agent: AssistantAgent,
    messages: list,
    last_spoke: dict,
    turn_counter: int,
    agent_names: list[str],
    max_rounds: int,
    forced_next: Optional[str] = None,
    stress_context: Optional[dict] = None,
) -> str:
    if forced_next and forced_next in agent_names:
        last_spoke[forced_next] = turn_counter
        return forced_next

    last_speaker = _last_persona_speaker(messages, agent_names)
    candidates = [p for p in agent_names if p != last_speaker]

    mandatory = [p for p in candidates if (turn_counter - last_spoke.get(p, 0)) >= 4]
    if mandatory:
        chosen = min(mandatory, key=lambda p: last_spoke.get(p, 0))
        last_spoke[chosen] = turn_counter
        return chosen

    sorted_cands = sorted(candidates, key=lambda p: last_spoke.get(p, 0))

    last_preview = ""
    for m in reversed(messages):
        if getattr(m, "source", "") in agent_names:
            last_preview = getattr(m, "content", "")[:200].replace("\n", " ")
            break

    prompt = _SELECTOR_PROMPT.format(
        candidates="\n".join(f"- {c}" for c in sorted_cands),
        last_speaker=last_speaker or "none",
        last_message_preview=last_preview,
        phase_context=_phase_context(turn_counter, max_rounds),
    )

    stress_addition = ""
    if stress_context:
        stress_addition = (
            f"\n\nCurrent phase: {stress_context.get('phase_name', '')}\n"
            f"Phase focus: {stress_context.get('focus_question', '')}\n"
            f"Sub-phase: {stress_context.get('sub_phase', '')} — {stress_context.get('sub_phase_directive', '')}\n\n"
            f"In Challenge sub-phase: prioritize adversarial agents.\n"
            f"In Comprehend sub-phase: rotate evenly — everyone must state their reading.\n"
            f"In Synthesize/Conclude: prioritize agents who haven't committed a position yet."
        )
    prompt += stress_addition

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label="selector")
    if response and response.chat_message:
        raw = response.chat_message.content.strip()
        for persona in sorted_cands:
            if persona.lower() in raw.lower():
                last_spoke[persona] = turn_counter
                return persona

    chosen = sorted_cands[0]
    last_spoke[chosen] = turn_counter
    return chosen
