"""PRD mini-panel — 4 agents, pure rotation, reads artifact not transcript."""

from typing import Callable, Awaitable
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client

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

    prd_agents = []
    for agent_conf in config.agents:
        if agent_conf["name"] in config.prd_panel_names:
            client = make_client(
                model=agent_conf["model"],
                api_key=config.gemini_api_key,
                temperature=config.temperature,
            )
            prd_agents.append(AssistantAgent(
                name=agent_conf["name"],
                description=agent_conf.get("role_tag", agent_conf["name"]),
                system_message=agent_conf["persona"],
                model_client=client,
            ))

    if not prd_agents:
        return []

    prd_last_spoke = {a.name: 0 for a in prd_agents}
    prd_turn = [0]
    prd_names = [a.name for a in prd_agents]

    def prd_selector(msgs):
        prd_turn[0] += 1
        last = None
        for m in reversed(msgs):
            if getattr(m, "source", "") in prd_names:
                last = getattr(m, "source")
                break
        cands = sorted(
            [p for p in prd_names if p != last],
            key=lambda p: prd_last_spoke.get(p, 0),
        )
        chosen = cands[0]
        prd_last_spoke[chosen] = prd_turn[0]
        return chosen

    main_client = make_client(
        model=config.main_model,
        api_key=config.gemini_api_key,
        temperature=config.temperature,
    )

    team = SelectorGroupChat(
        participants=prd_agents,
        model_client=main_client,
        termination_condition=MaxMessageTermination(config.prd_panel_rounds + 2),
        selector_prompt="Select next speaker by pure rotation.",
        selector_func=prd_selector,
    )

    result = await Console(team.run_stream(task=task))
    panel_messages = [m for m in result.messages if getattr(m, "source", "") in prd_names]

    for msg in panel_messages:
        await emit("agent_message", {
            "source": getattr(msg, "source", ""),
            "round": 0,
            "streaming": False,
            "content": getattr(msg, "content", ""),
        })

    return panel_messages
