"""Phase loop — core per-phase orchestration for all brainstorm modes."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Optional

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client
from backend.engine.tools import get_tools_for_agent
from backend.engine.gate import run_speech_gate
from backend.engine.selector import hybrid_selector
from backend.engine.phase_overseer import PhaseOverseer

logger = logging.getLogger("symposium")

EventCallback = Callable[[str, dict], Awaitable[None]]

_WEB_SEARCH_HINT = (
    "\n\nYou have access to a web_search tool. Use it to look up real-world data, "
    "recent statistics, market figures, regulatory info, or any factual claims that "
    "would strengthen your arguments. Cite what you find. Don't search for every turn — "
    "only when concrete evidence would add value."
)


@dataclass
class PhaseLoopState:
    """Mutable state tracked across phases throughout a session."""
    total_round_count: int = 0
    last_spoke: dict[str, int] = field(default_factory=dict)
    persona_turns: dict[str, int] = field(default_factory=dict)
    total_gate_skips: int = 0
    total_overseer_injections: int = 0
    start_time: float = field(default_factory=time.monotonic)
    all_messages: list = field(default_factory=list)
    previous_artifacts: list[str] = field(default_factory=list)


@dataclass
class PhaseResult:
    """Output from a single phase run."""
    phase_messages: list
    artifact: str
    stats_snapshot: dict


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    """Retry an async callable with exponential backoff and logging."""
    delays = [2, 4, 8, 16]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            logger.warning(
                f"[{label}] attempt {attempt+1}/{max_retries+1} failed: {e}"
            )
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    logger.error(f"[{label}] all {max_retries+1} attempts failed")
    return None


def _build_agents(config: EngineConfig) -> list[AssistantAgent]:
    """Build AssistantAgent instances from config, enabling tools when present."""
    agents = []
    for agent_conf in config.agents:
        tool_names = agent_conf.get("tools", [])
        tools = get_tools_for_agent(tool_names)
        persona = agent_conf["persona"]
        if tools:
            persona += _WEB_SEARCH_HINT
        client = make_client(
            model=agent_conf["model"],
            api_key=config.gemini_api_key,
            temperature=config.temperature,
            function_calling=len(tools) > 0,
        )
        agents.append(AssistantAgent(
            name=agent_conf["name"],
            description=agent_conf.get("role_tag", agent_conf["name"]),
            system_message=persona,
            model_client=client,
            model_client_stream=not tools,
            tools=tools if tools else None,
        ))
    return agents


async def run_phase(
    agents: dict[str, AssistantAgent],
    support_agent: AssistantAgent,
    overseer: PhaseOverseer,
    phase: dict,
    phase_index: int,
    context_builder: Callable,
    config: EngineConfig,
    emit: EventCallback,
    state: PhaseLoopState,
) -> PhaseResult:
    """Run a single phase of a brainstorm session.

    Args:
        agents: Map of agent name -> AssistantAgent.
        support_agent: LLM agent for overseer/gate/selector calls.
        overseer: PhaseOverseer instance managing phase progression.
        phase: Phase dict (number, name, focus_question, key_subquestions, etc.).
        phase_index: Zero-based index of this phase.
        context_builder: Mode-specific callable that builds message context for agent calls.
            Signature: (phase_messages, phase_index, phases) -> list[TextMessage]
        config: Engine configuration.
        emit: Async event callback for WebSocket events.
        state: Mutable PhaseLoopState shared across phases.

    Returns:
        PhaseResult with phase messages, artifact, and stats snapshot.
    """
    phase["status"] = "active"
    phase["start_round"] = state.total_round_count

    # Inject phase directive
    directive = overseer.generate_phase_directive(phase_index)
    state.all_messages.append(directive)
    phase_messages = [directive]

    await emit("phase_directive", {
        "phase_number": phase["number"],
        "phase_name": phase["name"],
        "focus_question": phase.get("focus_question", ""),
        "subquestions": phase.get("key_subquestions", []),
        "sub_phase": "Comprehend",
    })

    phase_round_count = 0
    phase_active = True
    total_phases = len(overseer.phases)

    while phase_active and state.total_round_count < config.max_rounds:
        phase_round_count += 1
        overseer.phase_round_counts[phase_index] = phase_round_count

        # --- Drift checks and evaluation ---
        if phase_round_count % 5 == 0:
            # Full evaluation every 5 rounds
            evaluation = await overseer.evaluate_phase(
                phase_index, state.all_messages, state.total_round_count
            )
            await emit("overseer_phase_eval", {
                "action": evaluation["action"],
                "confirmed": evaluation.get("confirmed", []),
                "contested": evaluation.get("contested", []),
                "summary": evaluation.get("summary", ""),
                "phase_number": phase["number"],
            })

            if evaluation["action"] == "suggest_advance":
                # Phase ready to advance — break out
                phase_active = False
                break
            else:
                # Build orchestration directive from evaluation
                sub_phase_name, sub_phase_directive = overseer.get_sub_phase(
                    phase_round_count
                )
                open_sqs = evaluation.get("open_questions", [])
                confirmed = evaluation.get("confirmed", [])

                parts = [
                    f"[REVIEW CHAIR — Phase {phase['number']}, "
                    f"Round {phase_round_count}]"
                ]
                parts.append(
                    f"\nCurrent stage: {sub_phase_name} — {sub_phase_directive}"
                )
                if confirmed:
                    parts.append(
                        f"\nSettled so far: {', '.join(confirmed[:3])}"
                    )
                if open_sqs:
                    parts.append(
                        f"\nStill unresolved: {', '.join(open_sqs[:3])}"
                    )
                    parts.append(
                        f"\nAgents, please address the unresolved items above. "
                        f"{sub_phase_directive}"
                    )
                else:
                    parts.append(
                        f"\nContinue working through the phase subquestions. "
                        f"{sub_phase_directive}"
                    )

                directive_content = "\n".join(parts)
                msg = TextMessage(content=directive_content, source="Overseer")
                state.all_messages.append(msg)
                phase_messages.append(msg)
                state.total_overseer_injections += 1
                await emit("overseer", {
                    "content": msg.content,
                    "round": state.total_round_count,
                })

        elif phase_round_count % 3 == 0 and phase_round_count >= 3:
            # LLM drift check every 3 rounds (offset: round 3, 6, 9...)
            # Skip rounds that are also multiples of 5 (handled above)
            drift = await overseer.check_drift(
                phase_index, state.all_messages, state.total_round_count
            )
            if drift:
                state.all_messages.append(drift)
                phase_messages.append(drift)
                state.total_overseer_injections += 1
                await emit("drift_redirect", {
                    "message": drift.content,
                    "sub_phase": overseer.get_sub_phase(phase_round_count)[0],
                })
        else:
            # Keyword drift check (zero cost) every other round
            drift = overseer.check_keyword_drift(phase_index, state.all_messages)
            if drift:
                state.all_messages.append(drift)
                phase_messages.append(drift)
                state.total_overseer_injections += 1
                await emit("drift_redirect", {
                    "message": drift.content,
                    "sub_phase": overseer.get_sub_phase(phase_round_count)[0],
                })

        # --- Select next speaker ---
        stress_ctx = overseer.get_selector_context(phase_index)
        chosen = await hybrid_selector(
            support_agent,
            state.all_messages,
            state.last_spoke,
            state.total_round_count,
            config.agent_names,
            config.max_rounds,
            None,
            stress_context=stress_ctx,
        )

        # --- Speech gate ---
        if state.total_round_count >= config.gate_start_round:
            is_stress = config.mode == "stress_test"
            should_speak, claim = await run_speech_gate(
                support_agent,
                chosen,
                state.all_messages,
                config.agent_names,
                stress_test=is_stress,
            )
            if not should_speak:
                state.total_gate_skips += 1
                await emit("gate_skip", {
                    "agent": chosen,
                    "round": state.total_round_count,
                })
                fallback = sorted(
                    [p for p in config.agent_names if p != chosen],
                    key=lambda p: state.last_spoke.get(p, 0),
                )
                chosen = fallback[0] if fallback else chosen

        # --- Agent call with streaming ---
        agent = agents[chosen]
        context = context_builder(phase_messages, phase_index, overseer.phases)

        await emit("agent_message", {
            "source": chosen,
            "round": state.total_round_count + 1,
            "streaming": True,
            "content": "",
        })

        content = ""
        try:
            stream = agent.on_messages_stream(context, CancellationToken())
            async for chunk in stream:
                if hasattr(chunk, "content") and isinstance(chunk.content, str):
                    content += chunk.content
                    await emit("agent_message_chunk", {
                        "source": chosen,
                        "round": state.total_round_count + 1,
                        "content": content,
                    })
                elif hasattr(chunk, "chat_message") and chunk.chat_message:
                    content = chunk.chat_message.content or ""
        except Exception:
            async def _agent_call(a=agent, ctx=context):
                return await a.on_messages(ctx, CancellationToken())

            response = await _call_with_retry(_agent_call, label=chosen)
            if response and response.chat_message:
                content = response.chat_message.content or ""

        if not content:
            state.total_round_count += 1
            continue

        msg = TextMessage(content=content, source=chosen)
        state.all_messages.append(msg)
        phase_messages.append(msg)
        state.last_spoke[chosen] = state.total_round_count
        state.persona_turns[chosen] = state.persona_turns.get(chosen, 0) + 1
        state.total_round_count += 1

        await emit("agent_message", {
            "source": chosen,
            "round": state.total_round_count,
            "streaming": False,
            "content": content,
        })

        # --- Stats ---
        elapsed = time.monotonic() - state.start_time
        avg_per_round = elapsed / max(state.total_round_count, 1)
        remaining = config.max_rounds - state.total_round_count
        sub_phase_name = overseer.get_sub_phase(phase_round_count)[0]

        await emit("stats", {
            "rounds": state.total_round_count,
            "gate_skips": state.total_gate_skips,
            "phase_number": phase["number"],
            "phase_name": phase["name"],
            "phase_round": phase_round_count,
            "sub_phase": sub_phase_name,
            "total_phases": total_phases,
            "elapsed_seconds": round(elapsed),
            "eta_seconds": round(avg_per_round * remaining),
        })

    # --- Phase ended — write artifact ---
    phase["end_round"] = state.total_round_count
    phase["status"] = "complete"

    artifact = await overseer.write_phase_artifact(phase_index, state.all_messages)
    phase["artifact"] = artifact
    state.previous_artifacts.append(artifact)

    await emit("phase_artifact_written", {
        "phase_number": phase["number"],
        "content": artifact,
    })

    if phase_index + 1 < total_phases:
        await emit("phase_advanced", {
            "from_phase": phase["number"],
            "to_phase": overseer.phases[phase_index + 1]["number"],
        })

    stats_snapshot = {
        "total_rounds": state.total_round_count,
        "gate_skips": state.total_gate_skips,
        "overseer_injections": state.total_overseer_injections,
        "persona_turns": dict(state.persona_turns),
        "phase_rounds": phase_round_count,
        "elapsed_seconds": round(time.monotonic() - state.start_time),
    }

    return PhaseResult(
        phase_messages=phase_messages,
        artifact=artifact,
        stats_snapshot=stats_snapshot,
    )
