"""Living Artifact — built progressively at milestone rounds."""

import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

_ARTIFACT_PROMPT = """\
Build Section {section_num} of the session Living Artifact.
Section: {section_name} | Written at round: {round_num}

Do NOT repeat content from existing sections.

Relevant agent discussion (last 25 messages):
{relevant_excerpt}

Existing artifact:
{existing_artifact}

Output ONLY this new section (max 300 words):

SECTION {section_num} — {section_name} (Round {round_num})
──────────────────────────────────────────────────────────
[Each item: label · decision/status · who said it · one-line reason]
[Be specific. Include persona names. No vague summaries.]\
"""

_FINALIZE_PROMPT = """\
Write the final section of the Living Artifact.

Recent discussion:
{recent_text}

SECTION {section_num} — UNRESOLVED QUESTIONS (Session End)
──────────────────────────────────────────────────────────
List 3-5 specific open questions that:
  · Remain genuinely unanswered
  · Would materially change direction if answered differently
  · Are specific enough to be actionable research tasks

Format:
Q[n]: [question]
  Why it matters: [one sentence]
  Who raised it: [persona name]

Max 3-5 questions. No generic filler.\
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


async def update_living_artifact(
    support_agent: AssistantAgent,
    messages: list,
    living_artifact: dict,
    round_num: int,
    artifact_schedule: dict,
    agent_names: list[str],
) -> dict:
    section_info = artifact_schedule.get(round_num)
    if not section_info:
        return living_artifact

    section_name, section_num = section_info
    agent_msgs = [
        m for m in messages
        if getattr(m, "source", "") in agent_names
        and isinstance(getattr(m, "content", ""), str)
    ]
    relevant = agent_msgs[max(0, len(agent_msgs) - 25):]
    relevant_text = "\n\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:350]}"
        for m in relevant
    )
    existing = "\n\n".join(living_artifact.values()) if living_artifact else "None yet."
    prompt = _ARTIFACT_PROMPT.format(
        section_num=section_num, section_name=section_name, round_num=round_num,
        relevant_excerpt=relevant_text, existing_artifact=existing,
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label=f"artifact_s{section_num}")
    if response and response.chat_message:
        living_artifact[section_name] = response.chat_message.content
    return living_artifact


async def finalize_artifact(
    support_agent: AssistantAgent,
    messages: list,
    living_artifact: dict,
    agent_names: list[str],
) -> dict:
    recent_agent = [m for m in messages[-20:] if getattr(m, "source", "") in agent_names]
    recent_text = "\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:250]}"
        for m in recent_agent
    )
    section_num = len(living_artifact) + 1
    prompt = _FINALIZE_PROMPT.format(recent_text=recent_text, section_num=section_num)

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label="artifact_final")
    if response and response.chat_message:
        living_artifact["Unresolved Questions"] = response.chat_message.content
    return living_artifact
