"""PRD mini-panel — 4 agents, pure rotation, reads artifact not transcript."""

import asyncio
from typing import Callable, Awaitable
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client

_PRODUCT_THINKER_PERSONA = """\
You are the PRD PRODUCT THINKER — injected into this panel to ensure the PRD is \
shaped as a viable, distributable product.

ONE-LINE MISSION: Translate the brainstorm's decisions into a sharply defined \
digital product with a clear form, interaction model, and adoption path.

WHAT YOU CARE ABOUT MOST:
- Whether the PRD describes a named product form, not a vague concept
- Whether the interaction model is simple enough for broad distribution
- Whether the product delivers value before requiring heavy setup
- Whether the scope is narrow enough to build and broad enough to matter

WHAT YOU DISTRUST OR REJECT:
- PRD sections that read like consulting proposals instead of product specs
- Feature lists without a clear product core
- Outputs that cannot be explained in one sentence

DEFAULT QUESTIONS YOU ASK:
- What does the user do in the first 5 minutes?
- Is this a calculator, assessment, triage tool, or something else? Name it.
- Can version 1 work without data integration?

HOW YOU INTERACT WITH OTHERS:
Push every section toward product clarity. When someone writes a vague requirement, \
demand they name the specific interaction. You are allergic to ambiguity in product form.

STYLE: Sharp, concise. Speaks in product primitives — forms, flows, triggers, outputs.\
"""

EventCallback = Callable[[str, dict], Awaitable[None]]

_PRD_TASK = """\
You are now in a focused PRD co-authoring session.

The main brainstorm is complete. Here is the full structured decision artifact:

{artifact_text}

Your goal: debate and finalize a build-ready product specification in {panel_rounds} rounds.

RULES:
  · Do NOT reopen concept debates — those are closed
  · Disagree openly within your owned sections
  · Every section must be agreed or flagged as contested
  · PRD is done when all agents can defend every section to engineering

Start: each state the ONE thing you most want to sharpen in the artifact.\
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


async def run_prd_mini_panel(
    config: EngineConfig,
    living_artifact: dict,
    emit: EventCallback,
) -> list:
    await emit("phase_transition", {"phase": "prd_panel"})

    artifact_text = (
        "\n\n".join(f"== {name} ==\n{content}" for name, content in living_artifact.items())
        if living_artifact
        else "Artifact not yet fully populated. Work from your understanding of the brainstorm."
    )

    task = _PRD_TASK.format(artifact_text=artifact_text, panel_rounds=config.prd_panel_rounds)

    prd_agents = {}
    for agent_conf in config.agents:
        if agent_conf["name"] in config.prd_panel_names:
            client = make_client(
                model=agent_conf["model"],
                api_key=config.gemini_api_key,
                temperature=config.temperature,
            )
            prd_agents[agent_conf["name"]] = AssistantAgent(
                name=agent_conf["name"],
                description=agent_conf.get("role_tag", agent_conf["name"]),
                system_message=agent_conf["persona"],
                model_client=client,
            )

    # Always ensure a Product Thinker is on the PRD panel
    has_product_agent = any(
        "product" in (a.get("role_tag", "") or "").lower() or
        "product" in (a.get("name", "") or "").lower()
        for a in config.agents
        if a["name"] in prd_agents
    )
    if not has_product_agent:
        client = make_client(
            model=config.main_model,
            api_key=config.gemini_api_key,
            temperature=config.temperature,
        )
        prd_agents["PRD_Product_Thinker"] = AssistantAgent(
            name="PRD_Product_Thinker",
            description="Product form and scope owner",
            system_message=_PRODUCT_THINKER_PERSONA,
            model_client=client,
        )

    if not prd_agents:
        return []

    prd_names = list(prd_agents.keys())
    messages = [TextMessage(content=task, source="user")]
    last_spoke = {name: 0 for name in prd_names}
    panel_messages = []

    for turn in range(config.prd_panel_rounds):
        # Pure rotation: pick whoever spoke least recently
        last_src = None
        for m in reversed(messages):
            if getattr(m, "source", "") in prd_names:
                last_src = getattr(m, "source")
                break
        cands = sorted(
            [p for p in prd_names if p != last_src],
            key=lambda p: last_spoke.get(p, 0),
        )
        chosen = cands[0] if cands else prd_names[0]

        await emit("agent_message", {
            "source": chosen,
            "round": f"PRD {turn + 1}",
            "streaming": True,
            "content": "",
        })

        agent = prd_agents[chosen]

        content = ""
        try:
            stream = agent.on_messages_stream(messages, CancellationToken())
            async for chunk in stream:
                if hasattr(chunk, 'content') and isinstance(chunk.content, str):
                    content = chunk.content
                    await emit("agent_message_chunk", {
                        "source": chosen,
                        "round": f"PRD {turn + 1}",
                        "content": chunk.content,
                    })
                elif hasattr(chunk, 'chat_message') and chunk.chat_message:
                    content = chunk.chat_message.content or ""
        except Exception:
            async def _call(a=agent, ctx=messages):
                return await a.on_messages(ctx, CancellationToken())
            response = await _call_with_retry(_call, label=f"prd_{chosen}")
            if response and response.chat_message:
                content = response.chat_message.content or ""

        if not content:
            continue

        msg = TextMessage(content=content, source=chosen)
        messages.append(msg)
        panel_messages.append(msg)
        last_spoke[chosen] = turn

        await emit("agent_message", {
            "source": chosen,
            "round": f"PRD {turn + 1}",
            "streaming": False,
            "content": content,
        })

    return panel_messages
