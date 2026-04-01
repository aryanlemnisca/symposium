"""Rolling summary — auto-activates above threshold rounds."""

import asyncio
from typing import Optional
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


async def generate_rolling_summary(
    support_agent: AssistantAgent,
    messages: list,
    agent_names: list[str],
    n: int = 30,
) -> str:
    agent_msgs = [m for m in messages if getattr(m, "source", "") in agent_names][:n]
    text = "\n\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:400]}"
        for m in agent_msgs
    )
    prompt = (
        f"Compress the first {n} agent messages of this brainstorm into a "
        "structured 200-word summary.\n\n"
        "Focus on: key positions championed/rejected, product concepts that emerged, "
        "key agreements/disagreements, constraints established.\n\n"
        f"Discussion:\n{text}\n\n"
        f"Output:\nEARLY DISCUSSION SUMMARY (Rounds 1-{n}):\n"
        "[200 words max. Bullet points.]"
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label="rolling_summary")
    if response and response.chat_message:
        return response.chat_message.content
    return ""


def build_agent_context(
    messages: list,
    rolling_summary: Optional[str],
    agent_names: list[str],
) -> list:
    if not rolling_summary:
        return messages
    agent_msgs = [m for m in messages if getattr(m, "source", "") in agent_names]
    if len(agent_msgs) <= 30:
        return messages
    cutoff = agent_msgs[29]
    try:
        idx = messages.index(cutoff)
    except ValueError:
        return messages
    return [messages[0], TextMessage(content=rolling_summary, source="system")] + messages[idx + 1:]
