"""Speech gate — pre-commit: state specific claim or SKIP."""

import asyncio
from typing import Tuple
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

_GATE_PROMPT = """\
You are {agent_name} in an expert brainstorming panel.

Recent discussion (last 10 messages):
{recent_messages}

Before speaking, state in ONE SENTENCE the specific new argument, challenge,
refinement, or counter-example you will contribute that has NOT already been
clearly made above.

A valid contribution must be:
  · A genuinely new angle or specific challenge
  · Tied to YOUR persona's specific expertise and role
  · Something not already said or clearly implied above

These do NOT qualify:
  · "I agree and want to add..." (validation loop)
  · Restating someone else's point in different words
  · General endorsement of the current direction

If you cannot honestly identify a new contribution, respond exactly:
SKIP

Your one sentence (or SKIP):\
"""


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt < max_retries:
                wait = delays[min(attempt, len(delays) - 1)]
                await asyncio.sleep(wait)
    return None


_STRESS_GATE_PROMPT = """\
You are {agent_name} in a structured document review board.

Recent discussion (last 10 messages):
{recent_messages}

Before speaking, state in ONE SENTENCE what you will contribute.

A valid contribution in a stress-test review includes ANY of these:
  · A specific challenge to a claim in the documents (with evidence)
  · A defense of a claim that has been challenged (with evidence)
  · A new finding from the documents that hasn't been raised
  · A cross-document contradiction or dependency issue
  · A specific response to another agent's point (agree or disagree WITH reasoning)
  · An explicit decision recommendation [accept/revise/reopen/defer] with justification

These do NOT qualify:
  · Restating what someone already said without adding evidence
  · Vague agreement ("I concur with the general direction")
  · Repeating your own previous point

If you cannot identify a contribution that adds evidence or advances a decision, respond exactly:
SKIP

Your one sentence (or SKIP):\
"""


async def run_speech_gate(
    support_agent: AssistantAgent,
    agent_name: str,
    messages: list,
    all_agent_names: list[str],
    stress_test: bool = False,
) -> Tuple[bool, str]:
    recent = [
        m for m in messages[-12:]
        if isinstance(getattr(m, "content", ""), str)
        and getattr(m, "source", "") not in ["system"]
    ]
    recent_text = "\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:200]}"
        for m in recent
    )
    template = _STRESS_GATE_PROMPT if stress_test else _GATE_PROMPT
    prompt = template.format(agent_name=agent_name, recent_messages=recent_text)

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label=f"gate_{agent_name}")
    if response is None:
        return True, ""

    claim = (response.chat_message.content or "").strip() if response.chat_message else ""
    if not claim or claim.upper().startswith("SKIP"):
        return False, ""

    recent_lower = " ".join(getattr(m, "content", "").lower() for m in recent)
    words = claim.lower().split()
    if len(words) >= 6:
        for i in range(len(words) - 4):
            if " ".join(words[i: i + 5]) in recent_lower:
                return False, claim

    return True, claim
