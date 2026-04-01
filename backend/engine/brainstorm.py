"""Main brainstorm loop — extracted from lemnisca_panel.py:577-714.

Key change: all print() calls replaced with an async callback function
that emits structured events (for WebSocket streaming)."""

import asyncio
from typing import Optional, Callable, Awaitable
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client
from backend.engine.gate import run_speech_gate
from backend.engine.selector import hybrid_selector, _phase_context
from backend.engine.convergence import check_convergence, check_consensus_termination
from backend.engine.overseer import generate_overseer_reminder
from backend.engine.artifact import update_living_artifact, finalize_artifact
from backend.engine.summary import generate_rolling_summary, build_agent_context

EventCallback = Callable[[str, dict], Awaitable[None]]


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


def _build_agents(config: EngineConfig):
    agents = []
    for agent_conf in config.agents:
        client = make_client(
            model=agent_conf["model"],
            api_key=config.gemini_api_key,
            temperature=config.temperature,
        )
        agents.append(AssistantAgent(
            name=agent_conf["name"],
            description=agent_conf.get("role_tag", agent_conf["name"]),
            system_message=agent_conf["persona"],
            model_client=client,
        ))
    return agents


def _update_coverage(coverage: dict, content: str):
    for key in list(coverage.keys()):
        if key in content:
            coverage[key] = True


async def run_brainstorm(
    config: EngineConfig,
    emit: EventCallback,
) -> tuple[list, dict, dict]:
    agents = _build_agents(config)
    agent_map = {a.name: a for a in agents}

    support_client = make_client(
        model=config.support_model,
        api_key=config.gemini_api_key,
        temperature=0.3,
    )
    support_agent = AssistantAgent(
        name="Support",
        description="Gate, selector, overseer support agent",
        system_message="You are a precise, concise assistant. Follow instructions exactly. Output only what is asked.",
        model_client=support_client,
    )

    messages = [TextMessage(content=config.problem_statement, source="user")]
    last_spoke = {name: 0 for name in config.agent_names}
    persona_turns = {name: 0 for name in config.agent_names}
    c_coverage = {}
    living_artifact = {}
    rolling_summary = None

    turn_counter = 0
    gate_skips = 0
    overseer_injections = 0
    convergence_triggers = 0
    forced_next = None

    await emit("session_started", {"max_rounds": config.max_rounds})

    while turn_counter < config.max_rounds:

        if turn_counter > 0 and turn_counter % config.overseer_interval == 0:
            phase = _phase_context(turn_counter, config.max_rounds)
            overseer_msg = await generate_overseer_reminder(
                support_agent, messages, turn_counter, c_coverage, phase, config.agent_names,
            )
            messages.append(overseer_msg)
            overseer_injections += 1
            await emit("overseer", {
                "content": overseer_msg.content,
                "round": turn_counter,
            })

        if turn_counter > config.rolling_summary_threshold and rolling_summary is None:
            rolling_summary = await generate_rolling_summary(
                support_agent, messages, config.agent_names,
            )

        chosen = await hybrid_selector(
            support_agent, messages, last_spoke, turn_counter,
            config.agent_names, config.max_rounds, forced_next,
        )
        forced_next = None

        if turn_counter >= config.gate_start_round:
            should_speak, claim = await run_speech_gate(
                support_agent, chosen, messages, config.agent_names,
            )
            if not should_speak:
                gate_skips += 1
                await emit("gate_skip", {"agent": chosen, "round": turn_counter})
                last_speaker = None
                for m in reversed(messages):
                    if getattr(m, "source", "") in config.agent_names:
                        last_speaker = getattr(m, "source")
                        break
                fallback = sorted(
                    [p for p in config.agent_names if p != chosen and p != last_speaker],
                    key=lambda p: last_spoke.get(p, 0),
                )
                chosen = fallback[0] if fallback else chosen

        agent = agent_map[chosen]
        context = build_agent_context(messages, rolling_summary, config.agent_names)

        await emit("agent_message", {
            "source": chosen,
            "round": turn_counter + 1,
            "streaming": True,
            "content": "",
        })

        async def _agent_call(a=agent, ctx=context):
            return await a.on_messages(ctx, CancellationToken())

        response = await _call_with_retry(_agent_call, label=chosen)
        if response is None or response.chat_message is None:
            turn_counter += 1
            continue

        content = response.chat_message.content or ""
        msg = TextMessage(content=content, source=chosen)
        messages.append(msg)
        last_spoke[chosen] = turn_counter
        persona_turns[chosen] += 1
        turn_counter += 1

        await emit("agent_message", {
            "source": chosen,
            "round": turn_counter,
            "streaming": False,
            "content": content,
        })

        if turn_counter in config.artifact_schedule:
            living_artifact = await update_living_artifact(
                support_agent, messages, living_artifact, turn_counter,
                config.artifact_schedule, config.agent_names,
            )
            section_info = config.artifact_schedule[turn_counter]
            await emit("artifact_section", {
                "section_num": section_info[1],
                "section_name": section_info[0],
                "content": living_artifact.get(section_info[0], ""),
            })

        _update_coverage(c_coverage, content)

        await emit("stats", {
            "rounds": turn_counter,
            "gate_skips": gate_skips,
            "overseer_injections": overseer_injections,
            "c_coverage": c_coverage,
        })

        if turn_counter >= 10 and check_convergence(
            messages, config.agent_names, config.convergence_keywords,
        ):
            convergence_triggers += 1
            if turn_counter < config.min_rounds_before_convergence:
                forced_next = config.agent_names[-1] if config.agent_names else None
                await emit("convergence", {"forced_next": forced_next})
            else:
                forced_next = config.agent_names[-2] if len(config.agent_names) > 1 else config.agent_names[0]
                await emit("convergence", {"forced_next": forced_next})

        if check_consensus_termination(
            messages, turn_counter, c_coverage,
            config.agent_names, config.consensus_phrases,
            config.min_rounds_before_convergence,
        ):
            await emit("session_complete", {"terminated_by": "consensus"})
            break

    living_artifact = await finalize_artifact(
        support_agent, messages, living_artifact, config.agent_names,
    )

    stats = {
        "total_rounds": turn_counter,
        "gate_skips": gate_skips,
        "overseer_injections": overseer_injections,
        "convergence_triggers": convergence_triggers,
        "c_coverage": c_coverage,
        "persona_turns": persona_turns,
        "rolling_summary_used": rolling_summary is not None,
        "terminated_by": "consensus" if turn_counter < config.max_rounds else "max_rounds",
    }

    return messages, stats, living_artifact
