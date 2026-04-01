"""Conclusion report generation for Problem Discussion mode."""

from typing import Callable, Awaitable
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client

EventCallback = Callable[[str, dict], Awaitable[None]]

_CONCLUSION_PROMPT = """\
Read the brainstorming discussion and the Living Artifact, then produce a
structured Conclusion Report.

LIVING ARTIFACT:
{artifact_text}

DISCUSSION (last 30 messages):
{discussion_text}

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


async def generate_conclusion(
    config: EngineConfig,
    messages: list,
    living_artifact: dict,
    emit: EventCallback,
) -> str:
    await emit("phase_transition", {"phase": "conclusion"})

    artifact_text = (
        "\n\n".join(f"== {name} ==\n{content}" for name, content in living_artifact.items())
        if living_artifact
        else "No artifact sections generated."
    )
    agent_msgs = [m for m in messages if getattr(m, "source", "") in config.agent_names]
    recent = agent_msgs[-30:]
    discussion_text = "\n\n".join(
        f"[{getattr(m, 'source', '?')}]:\n{getattr(m, 'content', '').strip()}"
        for m in recent
    )

    client = make_client(
        model=config.main_model,
        api_key=config.gemini_api_key,
        temperature=config.temperature,
    )
    writer = AssistantAgent(
        name="ConclusionWriter",
        system_message="You produce structured conclusion reports from brainstorming discussions. Follow the template exactly.",
        model_client=client,
    )

    prompt = _CONCLUSION_PROMPT.format(
        artifact_text=artifact_text,
        discussion_text=discussion_text,
    )

    response = await writer.on_messages(
        [TextMessage(content=prompt, source="user")], CancellationToken()
    )

    return response.chat_message.content if response and response.chat_message else "Conclusion generation failed."
