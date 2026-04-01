"""Overseer middleware — constraint reminder every N rounds."""

import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

_OVERSEER_PROMPT = """\
You are a background session monitor for a brainstorming panel.
Write a terse structured context reminder for round {round_num}. Max 180 words.

Coverage status:
{coverage_status}

Recent messages (last 8):
{recent_messages}

Phase: {phase_context}

Output in this EXACT format:

[OVERSEER — Round {round_num}]

KEY CONSTRAINTS (from problem statement):
  - Remind agents of the core constraints from the problem statement
  - Keep agents focused on the defined scope

COVERAGE STATUS:
{coverage_status}

PHASE DIRECTIVE: {phase_context}

REMINDER: Challenge specifically. Disagree by name.
State something your persona uniquely sees — or stay silent.\
"""


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


def _format_coverage(coverage: dict) -> str:
    if not coverage:
        return "  No specific coverage tracking for this session."
    return "\n".join(
        f"  {k}: {'Covered' if v else 'NOT YET — must be addressed'}"
        for k, v in coverage.items()
    )


async def generate_overseer_reminder(
    support_agent: AssistantAgent,
    messages: list,
    round_num: int,
    coverage: dict,
    phase_context: str,
    agent_names: list[str],
) -> TextMessage:
    recent = [
        m for m in messages[-10:]
        if getattr(m, "source", "") not in ["system", "Overseer"]
        and isinstance(getattr(m, "content", ""), str)
    ]
    recent_text = "\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:150]}"
        for m in recent
    )
    coverage_status = _format_coverage(coverage)
    prompt = _OVERSEER_PROMPT.format(
        round_num=round_num,
        coverage_status=coverage_status,
        recent_messages=recent_text,
        phase_context=phase_context,
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label="overseer")
    if response and response.chat_message:
        content = response.chat_message.content
    else:
        content = (
            f"[OVERSEER — Round {round_num}]\n\n"
            f"COVERAGE STATUS:\n{coverage_status}\n\n"
            "REMINDER: Challenge specifically. Disagree by name."
        )
    return TextMessage(content=content, source="Overseer")
