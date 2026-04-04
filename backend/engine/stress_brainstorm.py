"""Stress test brainstorm loop — phase-aware with bidirectional WebSocket."""

import asyncio
import time
from typing import Callable, Awaitable, Optional
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client
from backend.engine.gate import run_speech_gate
from backend.engine.selector import hybrid_selector
from backend.engine.summary import generate_rolling_summary, build_agent_context
from backend.engine.stress_overseer import StressOverseer

EventCallback = Callable[[str, dict], Awaitable[None]]
ReceiveCallback = Callable[[], Awaitable[dict]]


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


async def wait_for_command(receive: ReceiveCallback, timeout: Optional[float] = 60) -> str:
    """Wait for a client command or timeout."""
    try:
        if timeout:
            msg = await asyncio.wait_for(receive(), timeout=timeout)
        else:
            msg = await receive()
        return msg.get("action", "advance_phase")
    except asyncio.TimeoutError:
        return "auto_advance"
    except Exception:
        return "auto_advance"


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


def _build_stress_context(
    problem_statement_msg: TextMessage,
    review_instructions: str,
    documents: list[dict],
    phases: list[dict],
    current_phase_index: int,
    phase_messages: list,
) -> list:
    """Build agent context for stress test mode."""
    context = [problem_statement_msg]

    # Review instructions
    if review_instructions:
        context.append(TextMessage(content=review_instructions, source="system"))

    # All documents — full text always available
    doc_text = "\n\n".join(
        f"[Document: {d['filename']}]\n{d['content_text']}"
        for d in documents
    )
    if doc_text:
        context.append(TextMessage(content=f"UPLOADED DOCUMENTS\n{'='*40}\n\n{doc_text}", source="system"))

    # Previous phase artifacts (carry-forward decisions)
    for prev_phase in phases[:current_phase_index]:
        if prev_phase.get("artifact"):
            context.append(TextMessage(content=prev_phase["artifact"], source="Overseer"))

    # Phase conversation history
    context.extend(phase_messages)

    return context


_EXEC_SUMMARY_PROMPT = """\
You are a senior executive reading the output of a structured document stress-test review.

You have been given:
1. Per-phase review artifacts from {phase_count} phases
2. A final readiness verdict

Your job: produce a crisp executive summary that a busy leader can read in 2 minutes.

PHASE ARTIFACTS:
{all_artifacts}

FINAL VERDICT:
{verdict}

Produce the summary in this EXACT format:

EXECUTIVE SUMMARY
━━━━━━━━━━━━━━━━━

VERDICT: [one line — Ready / Not Ready / Conditionally Ready + one sentence why]

WHAT'S SOUND:
· [3-5 bullet points — the strongest confirmed elements, each one sentence]

WHAT MUST CHANGE:
· [3-5 bullet points — the most critical issues, each one sentence with specific action]

KEY RISKS:
· [2-3 bullet points — risks that could derail execution even if issues are fixed]

RECOMMENDED NEXT STEP:
[One sentence — the single most important thing to do now]

Rules:
- No hedging. Be direct.
- Each bullet must be specific and actionable — no vague summaries.
- If the verdict is "Not Ready," lead with what blocks progress.
- Keep the entire summary under 300 words.\
"""


async def _generate_executive_summary(
    support_agent: AssistantAgent,
    phases: list[dict],
    verdict: str,
) -> str:
    """Generate a crisp executive summary from all artifacts + verdict."""
    all_artifacts = "\n\n---\n\n".join(
        f"Phase {p.get('number', '?')} — {p.get('name', '?')}:\n{p.get('artifact', 'No artifact')}"
        for p in phases if p.get("artifact")
    )

    prompt = _EXEC_SUMMARY_PROMPT.format(
        phase_count=len(phases),
        all_artifacts=all_artifacts,
        verdict=verdict,
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label="exec_summary")
    if response and response.chat_message:
        return response.chat_message.content
    return "Executive summary generation failed."


async def run_stress_test(
    config: EngineConfig,
    phases: list[dict],
    documents: list[dict],
    review_instructions: str,
    emit: EventCallback,
    receive: ReceiveCallback,
) -> tuple[list, dict, list[dict], str, str]:
    """Run a stress test session. Returns (messages, stats, phases, verdict, exec_summary)."""

    agents = _build_agents(config)
    agent_map = {a.name: a for a in agents}

    support_client = make_client(
        model=config.support_model,
        api_key=config.gemini_api_key,
        temperature=0.3,
    )
    support_agent = AssistantAgent(
        name="Support",
        description="Stress test support agent",
        system_message="You are a precise, concise assistant. Follow instructions exactly.",
        model_client=support_client,
    )

    min_rounds_per_phase = getattr(config, "stress_test_min_rounds_per_phase", 20)

    overseer = StressOverseer(
        support_agent=support_agent,
        phases=phases,
        documents=documents,
        min_rounds_per_phase=min_rounds_per_phase,
        agent_names=config.agent_names,
    )

    all_messages = [TextMessage(content=config.problem_statement, source="user")]
    last_spoke = {name: 0 for name in config.agent_names}
    persona_turns = {name: 0 for name in config.agent_names}

    total_round_count = 0
    total_gate_skips = 0
    start_time = time.monotonic()

    await emit("session_started", {"max_rounds": config.max_rounds, "total_phases": len(phases)})

    for phase_index in range(len(phases)):
        phase = phases[phase_index]
        phase["status"] = "active"
        phase["start_round"] = total_round_count

        # Inject phase directive
        directive = overseer.generate_phase_directive(phase_index)
        all_messages.append(directive)
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

        while phase_active and total_round_count < config.max_rounds:
            phase_round_count += 1
            overseer.phase_round_counts[phase_index] = phase_round_count

            # Drift check / evaluation
            if phase_round_count % 5 == 0:
                # Full evaluation
                evaluation = await overseer.evaluate_phase(phase_index, all_messages, total_round_count)
                await emit("overseer_phase_eval", {
                    "action": evaluation["action"],
                    "confirmed": evaluation.get("confirmed", []),
                    "contested": evaluation.get("contested", []),
                    "summary": evaluation.get("summary", ""),
                    "phase_number": phase["number"],
                })

                if evaluation["action"] == "suggest_advance":
                    await emit("phase_pause", {
                        "phase_number": phase["number"],
                        "timeout_seconds": 60,
                        "summary": evaluation.get("summary", ""),
                        "confirmed": evaluation.get("confirmed", []),
                        "contested": evaluation.get("contested", []),
                        "open_questions": evaluation.get("open_questions", []),
                        "next_phase": phase_index + 1 < len(phases),
                    })

                    command = await wait_for_command(receive, timeout=60)

                    if command == "pause_timer":
                        command = await wait_for_command(receive, timeout=None)

                    if command == "continue_phase":
                        await emit("phase_continue", {"phase_number": phase["number"], "reason": "user override"})
                        continue
                    else:
                        # advance_phase or auto_advance
                        phase_active = False
                        break
                else:
                    # Build an orchestration directive, not raw eval output
                    sub_phase_name, sub_phase_directive = overseer.get_sub_phase(phase_round_count)
                    open_sqs = evaluation.get("open_questions", [])
                    confirmed = evaluation.get("confirmed", [])

                    parts = [f"[REVIEW CHAIR — Phase {phase['number']}, Round {phase_round_count}]"]
                    parts.append(f"\nCurrent stage: {sub_phase_name} — {sub_phase_directive}")

                    if confirmed:
                        parts.append(f"\nSettled so far: {', '.join(confirmed[:3])}")
                    if open_sqs:
                        parts.append(f"\nStill unresolved: {', '.join(open_sqs[:3])}")
                        parts.append(f"\nAgents, please address the unresolved items above. {sub_phase_directive}")
                    else:
                        parts.append(f"\nContinue working through the phase subquestions. {sub_phase_directive}")

                    directive_content = "\n".join(parts)
                    msg = TextMessage(content=directive_content, source="Overseer")
                    all_messages.append(msg)
                    phase_messages.append(msg)
                    await emit("overseer", {"content": msg.content, "round": total_round_count})

            elif phase_round_count % 5 == 3:
                # LLM drift check
                drift = await overseer.check_drift(phase_index, all_messages, total_round_count)
                if drift:
                    all_messages.append(drift)
                    phase_messages.append(drift)
                    await emit("drift_redirect", {"message": drift.content, "sub_phase": overseer.get_sub_phase(phase_round_count)[0]})
            else:
                # Keyword drift check (zero cost)
                drift = overseer.check_keyword_drift(phase_index, all_messages)
                if drift:
                    all_messages.append(drift)
                    phase_messages.append(drift)
                    await emit("drift_redirect", {"message": drift.content, "sub_phase": overseer.get_sub_phase(phase_round_count)[0]})

            # Select next speaker
            stress_ctx = overseer.get_selector_context(phase_index)
            chosen = await hybrid_selector(
                support_agent, all_messages, last_spoke, total_round_count,
                config.agent_names, config.max_rounds, None,
                stress_context=stress_ctx,
            )

            # Gate check
            if total_round_count >= config.gate_start_round:
                should_speak, claim = await run_speech_gate(
                    support_agent, chosen, all_messages, config.agent_names,
                    stress_test=True,
                )
                if not should_speak:
                    total_gate_skips += 1
                    await emit("gate_skip", {"agent": chosen, "round": total_round_count})
                    fallback = sorted(
                        [p for p in config.agent_names if p != chosen],
                        key=lambda p: last_spoke.get(p, 0),
                    )
                    chosen = fallback[0] if fallback else chosen

            # Agent call with streaming
            agent = agent_map[chosen]
            context = _build_stress_context(
                all_messages[0], review_instructions, documents,
                phases, phase_index, phase_messages,
            )

            await emit("agent_message", {
                "source": chosen,
                "round": total_round_count + 1,
                "streaming": True,
                "content": "",
            })

            content = ""
            try:
                stream = agent.on_messages_stream(context, CancellationToken())
                async for chunk in stream:
                    if hasattr(chunk, 'content') and isinstance(chunk.content, str):
                        content = chunk.content
                        await emit("agent_message_chunk", {
                            "source": chosen,
                            "round": total_round_count + 1,
                            "content": chunk.content,
                        })
                    elif hasattr(chunk, 'chat_message') and chunk.chat_message:
                        content = chunk.chat_message.content or ""
            except Exception:
                async def _agent_call(a=agent, ctx=context):
                    return await a.on_messages(ctx, CancellationToken())
                response = await _call_with_retry(_agent_call, label=chosen)
                if response and response.chat_message:
                    content = response.chat_message.content or ""

            if not content:
                total_round_count += 1
                continue

            msg = TextMessage(content=content, source=chosen)
            all_messages.append(msg)
            phase_messages.append(msg)
            last_spoke[chosen] = total_round_count
            persona_turns[chosen] += 1
            total_round_count += 1

            await emit("agent_message", {
                "source": chosen,
                "round": total_round_count,
                "streaming": False,
                "content": content,
            })

            # Stats
            elapsed = time.monotonic() - start_time
            avg_per_round = elapsed / max(total_round_count, 1)
            remaining = config.max_rounds - total_round_count
            sub_phase_name = overseer.get_sub_phase(phase_round_count)[0]

            await emit("stats", {
                "rounds": total_round_count,
                "gate_skips": total_gate_skips,
                "phase_number": phase["number"],
                "phase_name": phase["name"],
                "phase_round": phase_round_count,
                "sub_phase": sub_phase_name,
                "total_phases": len(phases),
                "elapsed_seconds": round(elapsed),
                "eta_seconds": round(avg_per_round * remaining),
            })

        # Phase ended — write artifact
        phase["end_round"] = total_round_count
        phase["status"] = "complete"

        artifact = await overseer.write_phase_artifact(phase_index, all_messages)
        phase["artifact"] = artifact

        await emit("phase_artifact_written", {
            "phase_number": phase["number"],
            "content": artifact,
        })

        if phase_index + 1 < len(phases):
            await emit("phase_advanced", {
                "from_phase": phase["number"],
                "to_phase": phases[phase_index + 1]["number"],
            })

    # Session close
    await emit("session_close_suggest", {
        "total_rounds": total_round_count,
        "phases_complete": len(phases),
    })

    command = await wait_for_command(receive, timeout=60)
    if command == "pause_timer":
        command = await wait_for_command(receive, timeout=None)

    if command == "continue_reviewing":
        # Run additional rounds without phases (free-form)
        # For now, just proceed to verdict
        pass

    # Generate final verdict
    await emit("verdict_generating", {})
    verdict = await overseer.generate_final_verdict()
    await emit("verdict_complete", {"content": verdict})

    # Generate executive summary
    await emit("phase_transition", {"phase": "executive_summary"})
    exec_summary = await _generate_executive_summary(support_agent, phases, verdict)
    await emit("executive_summary", {"content": exec_summary})

    stats = {
        "total_rounds": total_round_count,
        "gate_skips": total_gate_skips,
        "persona_turns": persona_turns,
        "phases_completed": len(phases),
        "terminated_by": "verdict",
    }

    return all_messages, stats, phases, verdict, exec_summary
