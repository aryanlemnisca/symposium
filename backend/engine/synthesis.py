"""Synthesis report + PRD generation from mini-panel discussion."""

import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.clients import make_client

_SYNTHESIS_SYSTEM = (
    "You are a Senior Strategy Synthesizer reading a focused PRD co-authoring "
    "discussion. The main decisions have already been made. Extract, clarify, and "
    "structure what was agreed and what remains open. Every sentence must earn its place."
)

_SYNTHESIS_PROMPT = """\
Read the PRD panel discussion and produce a structured synthesis report.

## 1. Consensus Areas
What did the panel agree on definitively?

## 2. Key Tensions Resolved
Where did agents disagree? How resolved?

## 3. Winning Product Concept
  - Product name and one-line description
  - Product form
  - Target pain
  - Why it works
  - Confidence: High / Medium / Exploratory

## 4. What Was Explicitly Ruled Out

## 5. Open Questions Before Build Starts

PRD PANEL DISCUSSION:
{panel_text}\
"""

_PRD_SYSTEM = (
    "You are producing a build-ready Product Requirements Document. "
    "Follow the template exactly. Do not add or skip sections."
)

_PRD_PROMPT = """\
Extract the build-ready PRD from the PRD panel discussion.

PRD PANEL DISCUSSION:
{panel_text}

Output using this exact template:

# [Product Name] — Build-Ready PRD

## 1. Product Name and One-Line Description
## 2. Target User
## 3. Trigger Moment
## 4. Required Inputs
## 5. Processing Logic
## 6. Output
## 7. Trust Mechanism
## 8. v1 Scope
## 9. Wedge Mechanic
## 10. Team Ownership
## 11. Unresolved Questions Before Build Starts\
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


async def generate_synthesis_and_prd(
    model: str,
    api_key: str,
    temperature: float,
    panel_messages: list,
) -> tuple[str, str]:
    panel_text = "\n\n".join(
        f"[{getattr(m, 'source', '?')}]:\n{getattr(m, 'content', '').strip()}"
        for m in panel_messages
    )

    client = make_client(model=model, api_key=api_key, temperature=temperature)
    synthesizer = AssistantAgent(name="Synthesizer", system_message=_SYNTHESIS_SYSTEM, model_client=client)
    prd_writer = AssistantAgent(name="PRD_Writer", system_message=_PRD_SYSTEM, model_client=client)

    async def _synth():
        return await synthesizer.on_messages(
            [TextMessage(content=_SYNTHESIS_PROMPT.format(panel_text=panel_text), source="user")],
            CancellationToken(),
        )
    synth_r = await _call_with_retry(_synth, label="synthesizer")
    synthesis_text = synth_r.chat_message.content if synth_r and synth_r.chat_message else "Synthesis failed."

    async def _prd():
        return await prd_writer.on_messages(
            [TextMessage(content=_PRD_PROMPT.format(panel_text=panel_text), source="user")],
            CancellationToken(),
        )
    prd_r = await _call_with_retry(_prd, label="prd_writer")
    prd_text = prd_r.chat_message.content if prd_r and prd_r.chat_message else "PRD generation failed."

    return synthesis_text, prd_text
