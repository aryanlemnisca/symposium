"""PRD mini-panel — 20-round overseer-driven PRD co-authoring session."""

import asyncio
import json
from typing import Callable, Awaitable
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client

EventCallback = Callable[[str, dict], Awaitable[None]]

# ---------------------------------------------------------------------------
# PRD sections that must be covered
# ---------------------------------------------------------------------------

PRD_SECTIONS = [
    "Target User",
    "Trigger Moment",
    "Required Inputs",
    "Processing Logic",
    "Output",
    "Trust Mechanism",
    "v1 Scope",
    "Wedge Mechanic",
    "Team Ownership",
]

# ---------------------------------------------------------------------------
# Sub-phases
# ---------------------------------------------------------------------------

_SUB_PHASES = [
    (0.20, "Open", "State your single most important sharpening request for the PRD. One sentence per agent."),
    (0.60, "Section Debate", "Debate specific PRD sections. Defend or attack section content. Cite the artifact. Force resolution."),
    (0.80, "Lock", "Lock in the contested sections. Each agent commits to a position with rationale."),
    (1.00, "Final Commit", "Final round. Each agent states either 'I can defend every section to engineering' or names the blocker."),
]


def _get_sub_phase(round_num: int, total_rounds: int) -> tuple[str, str]:
    pct = round_num / max(total_rounds, 1)
    for threshold, name, directive in _SUB_PHASES:
        if pct <= threshold:
            return name, directive
    return _SUB_PHASES[-1][1], _SUB_PHASES[-1][2]


# ---------------------------------------------------------------------------
# Product Thinker fallback persona
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Initial task
# ---------------------------------------------------------------------------

_PRD_TASK = """\
You are now in a focused {panel_rounds}-round PRD co-authoring session.

The main brainstorm is complete. Here is the full structured decision artifact from all phases:

{artifact_text}

Your goal: debate and finalize a build-ready product specification. The PRD must cover ALL these sections:
{section_list}

RULES:
- Do NOT reopen concept debates — those are closed
- Disagree openly within your owned sections
- Every section must be either agreed or explicitly flagged as contested
- PRD is done when all agents can defend every section to engineering
- Cite the brainstorm artifact when defending positions

You will be guided through 4 sub-phases: Open → Section Debate → Lock → Final Commit.

Start: each state the ONE thing you most want to sharpen in the artifact.\
"""


# ---------------------------------------------------------------------------
# Overseer evaluation prompt
# ---------------------------------------------------------------------------

_OVERSEER_PROMPT = """\
You are the PRD Review Chair. Evaluate the PRD panel discussion so far.

PRD SECTIONS THAT MUST BE COVERED:
{section_list}

DISCUSSION SO FAR (last 15 messages):
{discussion_text}

For each section, decide:
- "settled" — agreed with specifics
- "contested" — actively debated, no resolution yet
- "missing" — not yet discussed in any meaningful way

Return JSON only:
{{
  "section_status": {{
    "Target User": "settled|contested|missing",
    "Trigger Moment": "settled|contested|missing",
    "Required Inputs": "settled|contested|missing",
    "Processing Logic": "settled|contested|missing",
    "Output": "settled|contested|missing",
    "Trust Mechanism": "settled|contested|missing",
    "v1 Scope": "settled|contested|missing",
    "Wedge Mechanic": "settled|contested|missing",
    "Team Ownership": "settled|contested|missing"
  }},
  "redirect": "One sentence telling agents which section to focus on next. Be specific. Name the section. If everything is settled, say 'All sections are settled — proceed to final commits.'"
}}
"""


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


def _parse_json_safe(raw: str) -> dict | None:
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except Exception:
        return None


async def _evaluate_prd_coverage(
    support_agent: AssistantAgent,
    panel_messages: list,
) -> dict:
    """Use the support agent to evaluate which PRD sections are settled/contested/missing."""
    section_list = "\n".join(f"- {s}" for s in PRD_SECTIONS)
    recent = panel_messages[-15:] if len(panel_messages) > 15 else panel_messages
    discussion_text = "\n\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:400]}"
        for m in recent
    )
    prompt = _OVERSEER_PROMPT.format(
        section_list=section_list,
        discussion_text=discussion_text,
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label="prd_overseer")
    if response and response.chat_message:
        parsed = _parse_json_safe(response.chat_message.content)
        if parsed:
            return parsed
    return {"section_status": {}, "redirect": "Continue debating contested sections."}


def _select_speaker(
    panel_messages: list,
    prd_names: list[str],
    last_spoke: dict[str, int],
    sub_phase: str,
) -> str:
    """Select next speaker based on sub-phase logic."""
    last_src = None
    for m in reversed(panel_messages):
        if getattr(m, "source", "") in prd_names:
            last_src = getattr(m, "source")
            break

    cands = sorted(
        [p for p in prd_names if p != last_src],
        key=lambda p: last_spoke.get(p, 0),
    )
    return cands[0] if cands else prd_names[0]


async def run_prd_mini_panel(
    config: EngineConfig,
    living_artifact: dict,
    emit: EventCallback,
) -> list:
    await emit("phase_transition", {"phase": "prd_panel"})

    panel_rounds = max(config.prd_panel_rounds or 20, 12)

    artifact_text = (
        "\n\n".join(f"== {name} ==\n{content}" for name, content in living_artifact.items())
        if living_artifact
        else "Artifact not yet fully populated. Work from your understanding of the brainstorm."
    )

    section_list = "\n".join(f"- {s}" for s in PRD_SECTIONS)
    task = _PRD_TASK.format(
        artifact_text=artifact_text,
        panel_rounds=panel_rounds,
        section_list=section_list,
    )

    # --- Build PRD agents ---
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
                model_client_stream=True,
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
            model_client_stream=True,
        )

    if not prd_agents:
        return []

    # --- Build support agent for overseer evaluations ---
    support_client = make_client(
        model=config.support_model,
        api_key=config.gemini_api_key,
        temperature=0.3,
    )
    support_agent = AssistantAgent(
        name="PRD_Chair",
        description="PRD review chair",
        system_message="You are a precise PRD review chair. Output only valid JSON.",
        model_client=support_client,
    )

    prd_names = list(prd_agents.keys())
    messages = [TextMessage(content=task, source="user")]
    last_spoke = {name: 0 for name in prd_names}
    panel_messages = []

    await emit("prd_panel_started", {
        "total_rounds": panel_rounds,
        "agents": prd_names,
        "sections": PRD_SECTIONS,
    })

    current_sub_phase = _SUB_PHASES[0][1]

    for turn in range(panel_rounds):
        sub_phase_name, sub_phase_directive = _get_sub_phase(turn + 1, panel_rounds)

        # Emit sub-phase change
        if sub_phase_name != current_sub_phase:
            current_sub_phase = sub_phase_name
            await emit("prd_sub_phase", {
                "sub_phase": sub_phase_name,
                "directive": sub_phase_directive,
                "round": turn + 1,
            })

        # --- Overseer evaluation every 4 rounds (skip first round) ---
        if turn > 0 and turn % 4 == 0:
            evaluation = await _evaluate_prd_coverage(support_agent, panel_messages)
            section_status = evaluation.get("section_status", {})
            redirect = evaluation.get("redirect", "")

            await emit("prd_overseer_eval", {
                "round": turn + 1,
                "section_status": section_status,
                "redirect": redirect,
            })

            # Inject redirect message
            if redirect:
                missing_sections = [s for s, st in section_status.items() if st == "missing"]
                contested_sections = [s for s, st in section_status.items() if st == "contested"]
                parts = [f"[PRD CHAIR — Round {turn + 1}, Sub-phase: {sub_phase_name}]"]
                parts.append(sub_phase_directive)
                if missing_sections:
                    parts.append(f"\nSTILL MISSING: {', '.join(missing_sections)}")
                if contested_sections:
                    parts.append(f"\nSTILL CONTESTED: {', '.join(contested_sections)}")
                parts.append(f"\n{redirect}")
                directive_msg = TextMessage(content="\n".join(parts), source="PRD_Chair")
                messages.append(directive_msg)
                panel_messages.append(directive_msg)

        # --- Select speaker ---
        chosen = _select_speaker(panel_messages, prd_names, last_spoke, sub_phase_name)

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
                    content += chunk.content
                    await emit("agent_message_chunk", {
                        "source": chosen,
                        "round": f"PRD {turn + 1}",
                        "content": content,
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

    # Final coverage evaluation
    final_eval = await _evaluate_prd_coverage(support_agent, panel_messages)
    await emit("prd_panel_complete", {
        "section_status": final_eval.get("section_status", {}),
        "total_rounds": panel_rounds,
    })

    return panel_messages
