"""
╔══════════════════════════════════════════════════════════════╗
║   LEMNISCA FERMENTATION BRAINSTORMING PANEL  v2.0           ║
║   6 Expert Personas · AutoGen v0.4 · Gemini 3.1 Pro         ║
║                                                              ║
║   v2 additions:                                              ║
║   · Pre-commit speech gate (SKIP or state specific claim)   ║
║   · Hybrid selector (rotation floor + LLM contextual pick)  ║
║   · Overseer middleware: constraint reminders every 10 rds  ║
║   · Living Artifact built progressively                     ║
║   · Convergence detection → forced challenger agent         ║
║   · Rolling summary above 70 rounds                         ║
║   · Exponential backoff retry on every API call             ║
║   · PRD mini-panel: 4 agents read artifact not transcript   ║
║   · Build-ready PRD as dedicated 4th output file            ║
║   · All 4 outputs timestamped                               ║
║                                                              ║
║   Python 3.13 compatible                                    ║
╚══════════════════════════════════════════════════════════════╝

SETUP (one-time):
    pip install pyautogen "autogen-ext[openai]" rich

RUN:
    export GEMINI_API_KEY=your_key_here
    python lemnisca_panel.py

OUTPUTS (all timestamped YYYY-MM-DD_HH-MM):
    lemnisca_transcript_*.md   — Full brainstorm
    lemnisca_artifact_*.md     — Living Artifact
    lemnisca_synthesis_*.md    — Synthesis report
    lemnisca_prd_*.md          — Build-ready PRD

COST (Gemini 3.1 Pro):
    20 rounds  ~$0.51   <- START HERE
    50 rounds  ~$1.27
    80 rounds  ~$2.40
   100 rounds  ~$3.80
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core import CancellationToken


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
MAX_ROUNDS     = 50        # START: 20 → 50 → 80 → 100
TEMPERATURE    = 0.70

MAIN_MODEL    = "gemini-3.1-pro-preview"   # brainstorm + PRD + synthesizer
SUPPORT_MODEL = "gemini-2.5-flash"          # gate + selector + overseer + summary

MIN_ROUNDS_BEFORE_CONVERGENCE = 30
GATE_START_ROUND              = 10
OVERSEER_INTERVAL             = 10
ROLLING_SUMMARY_THRESHOLD     = 70
PRD_PANEL_ROUNDS              = 10

ALL_PERSONAS = [
    "Fermentation_Veteran", "Ops_Leader", "MSAT_Lead",
    "Product_Thinker", "First_Principles_Outsider", "BioChem_Professor",
]

PRD_PANEL_PERSONAS = [
    "Product_Thinker", "MSAT_Lead", "BioChem_Professor", "First_Principles_Outsider",
]

CONVERGENCE_KEYWORDS = [
    "i agree", "exactly right", "well said", "nothing to add",
    "session complete", "spec is locked", "build it", "we are done",
    "meeting adjourned", "lock the spec", "stop brainstorming", "get this built",
]

CONSENSUS_PHRASES = [
    "spec is locked", "session complete", "build it", "we are done here",
    "meeting adjourned", "get this built", "stop brainstorming", "start coding",
]

ARTIFACT_SCHEDULE: Dict[int, Tuple[str, int]] = {
    20: ("C-Level Verdicts", 1),
    40: ("Product Concepts Proposed and Killed", 2),
    55: ("Architectural Decisions", 3),
    65: ("Physics and Logic Engine Constraints", 4),
    75: ("Design Constraints and Rejections", 5),
}


# ─────────────────────────────────────────────────────────────────────────────
# MODEL CLIENTS
# ─────────────────────────────────────────────────────────────────────────────

def make_main_client() -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model=MAIN_MODEL,
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        temperature=TEMPERATURE,
        model_capabilities={"vision": False, "function_calling": False, "json_output": False},
    )

def make_support_client() -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model=SUPPORT_MODEL,
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        temperature=0.3,
        model_capabilities={"vision": False, "function_calling": False, "json_output": False},
    )


# ─────────────────────────────────────────────────────────────────────────────
# RETRY LOGIC  — never halts the session, returns None on total failure
# ─────────────────────────────────────────────────────────────────────────────

async def call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt < max_retries:
                wait = delays[min(attempt, len(delays) - 1)]
                print(f"  [RETRY {attempt+1}: {label} — {e} — waiting {wait}s]")
                await asyncio.sleep(wait)
            else:
                print(f"  [SKIP: {label} failed after {max_retries} retries: {e}]")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# SPEECH GATE  — pre-commit: state specific claim or SKIP
# Fires after GATE_START_ROUND. Allows speech by default on API failure.
# ─────────────────────────────────────────────────────────────────────────────

_GATE_PROMPT = """\
You are {agent_name} in an expert fermentation brainstorming panel.

Recent discussion (last 10 messages):
{recent_messages}

Before speaking, state in ONE SENTENCE the specific new argument, challenge,
refinement, or counter-example you will contribute that has NOT already been
clearly made above.

A valid contribution must be:
  · A genuinely new angle or specific challenge
  · Tied to YOUR persona's specific expertise and role
  · Something not already said or clearly implied above

These do NOT qualify:
  · "I agree and want to add..." (validation loop)
  · Restating someone else's point in different words
  · General endorsement of the current direction

If you cannot honestly identify a new contribution, respond exactly:
SKIP

Your one sentence (or SKIP):\
"""

async def run_speech_gate(
    support_agent: AssistantAgent,
    agent_name: str,
    messages: list,
) -> Tuple[bool, str]:
    recent = [
        m for m in messages[-12:]
        if isinstance(getattr(m, "content", ""), str)
        and getattr(m, "source", "") not in ["system"]
    ]
    recent_text = "\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:200]}"
        for m in recent
    )
    prompt = _GATE_PROMPT.format(agent_name=agent_name, recent_messages=recent_text)

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await call_with_retry(_call, label=f"gate_{agent_name}")
    if response is None:
        return True, ""   # API failure → allow speech by default

    claim = (response.chat_message.content or "").strip() if response.chat_message else ""
    if not claim or claim.upper().startswith("SKIP"):
        return False, ""

    # Lightweight 5-word overlap check (zero LLM cost)
    recent_lower = " ".join(getattr(m, "content", "").lower() for m in recent)
    words = claim.lower().split()
    if len(words) >= 6:
        for i in range(len(words) - 4):
            if " ".join(words[i: i + 5]) in recent_lower:
                return False, claim

    return True, claim


# ─────────────────────────────────────────────────────────────────────────────
# CONVERGENCE DETECTION  — keyword-based, zero LLM cost
# ─────────────────────────────────────────────────────────────────────────────

def check_convergence(messages: list, window: int = 3) -> bool:
    recent = [
        m for m in messages[-(window * 2):]
        if getattr(m, "source", "") in ALL_PERSONAS
    ][-window:]
    if len(recent) < window:
        return False
    return sum(
        1 for m in recent
        if any(kw in getattr(m, "content", "").lower() for kw in CONVERGENCE_KEYWORDS)
    ) >= window


def check_consensus_termination(messages: list, round_num: int, c_coverage: dict) -> bool:
    if round_num < MIN_ROUNDS_BEFORE_CONVERGENCE:
        return False
    if not all(c_coverage.values()):
        return False
    signalling = set()
    for m in messages:
        src = getattr(m, "source", "")
        content = getattr(m, "content", "").lower()
        if src in ALL_PERSONAS and any(p in content for p in CONSENSUS_PHRASES):
            signalling.add(src)
    return len(signalling) >= 3


# ─────────────────────────────────────────────────────────────────────────────
# HYBRID SELECTOR  — rotation floor + LLM contextual pick
# ─────────────────────────────────────────────────────────────────────────────

_SELECTOR_PROMPT = """\
Select the next speaker from these eligible candidates:
{candidates}

Last speaker: {last_speaker}
Last message (first 200 chars): "{last_message_preview}"
Current phase: {phase_context}

Choose who adds the most value right now:
  · Strong claim just made       → select someone who challenges it
  · Product concept proposed     → prefer Product_Thinker or Ops_Leader
  · Discussion too abstract      → prefer Fermentation_Veteran or MSAT_Lead
  · Converging too fast          → prefer First_Principles_Outsider
  · Technical/mechanistic claim  → prefer BioChem_Professor

Respond with ONLY the exact name of one candidate. No explanation.\
"""

def _phase_context(turn: int) -> str:
    if turn <= 15:   return "Phase 1 — stake C/P positions, raise all C1-C5"
    elif turn <= 35: return "Phase 2 — cross-debate, force C-level disagreement"
    elif turn <= 55: return "Phase 3 — converge on 2-4 named product concepts"
    elif turn <= 70: return "Phase 4 — stress-test shortlist, punch holes, rank"
    else:            return "Phase 5 — final refinement, nail interaction model and output format"

def _last_persona_speaker(messages: list) -> Optional[str]:
    for m in reversed(messages):
        if getattr(m, "source", "") in ALL_PERSONAS:
            return getattr(m, "source")
    return None

async def hybrid_selector(
    support_agent: AssistantAgent,
    messages: list,
    last_spoke: dict,
    turn_counter: int,
    forced_next: Optional[str] = None,
) -> str:
    if forced_next and forced_next in ALL_PERSONAS:
        last_spoke[forced_next] = turn_counter
        return forced_next

    last_speaker = _last_persona_speaker(messages)
    candidates   = [p for p in ALL_PERSONAS if p != last_speaker]

    # Rotation floor: mandatory if waiting 4+ turns
    mandatory = [p for p in candidates if (turn_counter - last_spoke.get(p, 0)) >= 4]
    if mandatory:
        chosen = min(mandatory, key=lambda p: last_spoke.get(p, 0))
        last_spoke[chosen] = turn_counter
        return chosen

    sorted_cands = sorted(candidates, key=lambda p: last_spoke.get(p, 0))

    last_preview = ""
    for m in reversed(messages):
        if getattr(m, "source", "") in ALL_PERSONAS:
            last_preview = getattr(m, "content", "")[:200].replace("\n", " ")
            break

    prompt = _SELECTOR_PROMPT.format(
        candidates="\n".join(f"- {c}" for c in sorted_cands),
        last_speaker=last_speaker or "none",
        last_message_preview=last_preview,
        phase_context=_phase_context(turn_counter),
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await call_with_retry(_call, label="selector")
    if response and response.chat_message:
        raw = response.chat_message.content.strip()
        for persona in sorted_cands:
            if persona.lower() in raw.lower():
                last_spoke[persona] = turn_counter
                return persona

    chosen = sorted_cands[0]
    last_spoke[chosen] = turn_counter
    return chosen


# ─────────────────────────────────────────────────────────────────────────────
# C-LEVEL COVERAGE TRACKING
# ─────────────────────────────────────────────────────────────────────────────

def update_c_level_coverage(coverage: dict, content: str):
    for i in range(1, 6):
        if f"C{i}" in content:
            coverage[f"C{i}"] = True

def format_c_level_status(coverage: dict) -> str:
    return "\n".join(
        f"  C{i}: {'OK' if coverage.get(f'C{i}') else 'NOT YET — must be addressed'}"
        for i in range(1, 6)
    )


# ─────────────────────────────────────────────────────────────────────────────
# OVERSEER  — constraint reminder every OVERSEER_INTERVAL rounds
#             Middleware: injected into message list, NOT a panel participant
# ─────────────────────────────────────────────────────────────────────────────

_OVERSEER_PROMPT = """\
You are a background session monitor for a Lemnisca brainstorming panel.
Write a terse structured context reminder for round {round_num}. Max 180 words.

C-level coverage:
{c_level_status}

Recent messages (last 8):
{recent_messages}

Phase: {phase_context}

Output in this EXACT format:

[OVERSEER — Round {round_num}]

KEY CONSTRAINTS (non-negotiable):
  - Solution must be FREE and digitally distributable
  - No bespoke consulting disguised as product
  - No AI/ML unless physics-first and defensible to QA
  - Sparse inputs only — works without historian integration

C-LEVEL COVERAGE:
{c_level_status}

PHASE DIRECTIVE: {phase_context}

REMINDER: Challenge specifically. Disagree by name.
State something your persona uniquely sees — or stay silent.\
"""

async def generate_overseer_reminder(
    support_agent: AssistantAgent,
    messages: list,
    round_num: int,
    c_level_coverage: dict,
) -> TextMessage:
    recent = [
        m for m in messages[-10:]
        if getattr(m, "source", "") not in ["system", "Overseer"]
        and isinstance(getattr(m, "content", ""), str)
    ]
    recent_text = "\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:150]}"
        for m in recent
    )
    prompt = _OVERSEER_PROMPT.format(
        round_num=round_num,
        c_level_status=format_c_level_status(c_level_coverage),
        recent_messages=recent_text,
        phase_context=_phase_context(round_num),
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await call_with_retry(_call, label="overseer")
    if response and response.chat_message:
        content = response.chat_message.content
    else:
        content = (
            f"[OVERSEER — Round {round_num}]\n\n"
            "KEY CONSTRAINTS: Free product · No consulting-ware · "
            "No AI/ML without physics basis · Sparse inputs only\n\n"
            f"C-LEVEL COVERAGE:\n{format_c_level_status(c_level_coverage)}\n\n"
            "REMINDER: Challenge specifically. Disagree by name."
        )
    return TextMessage(content=content, source="Overseer")


# ─────────────────────────────────────────────────────────────────────────────
# LIVING ARTIFACT  — built progressively at milestone rounds by Overseer
# ─────────────────────────────────────────────────────────────────────────────

_ARTIFACT_PROMPT = """\
Build Section {section_num} of the Lemnisca session Living Artifact.
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

async def update_living_artifact(
    support_agent: AssistantAgent,
    messages: list,
    living_artifact: dict,
    round_num: int,
) -> dict:
    section_info = ARTIFACT_SCHEDULE.get(round_num)
    if not section_info:
        return living_artifact
    section_name, section_num = section_info

    agent_msgs = [
        m for m in messages
        if getattr(m, "source", "") in ALL_PERSONAS
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

    response = await call_with_retry(_call, label=f"artifact_s{section_num}")
    if response and response.chat_message:
        living_artifact[section_name] = response.chat_message.content
        print(f"\n  [ARTIFACT: Section {section_num} '{section_name}' written at round {round_num}]")
    return living_artifact


async def finalize_artifact(
    support_agent: AssistantAgent,
    messages: list,
    living_artifact: dict,
) -> dict:
    recent_agent = [m for m in messages[-20:] if getattr(m, "source", "") in ALL_PERSONAS]
    recent_text = "\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:250]}"
        for m in recent_agent
    )
    prompt = (
        "Write the final section of the Lemnisca Living Artifact.\n\n"
        f"Recent discussion:\n{recent_text}\n\n"
        "SECTION 6 — UNRESOLVED QUESTIONS (Session End)\n"
        "──────────────────────────────────────────────────────────\n"
        "List 3-5 specific open questions that:\n"
        "  · Remain genuinely unanswered\n"
        "  · Would materially change product direction if answered differently\n"
        "  · Are specific enough to be actionable pre-build research tasks\n\n"
        "Format:\nQ[n]: [question]\n  Why it matters: [one sentence]\n  Who raised it: [persona name]\n\n"
        "Max 3-5 questions. No generic filler."
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await call_with_retry(_call, label="artifact_final")
    if response and response.chat_message:
        living_artifact["Unresolved Questions"] = response.chat_message.content
    return living_artifact


# ─────────────────────────────────────────────────────────────────────────────
# ROLLING SUMMARY  — auto-activates above ROLLING_SUMMARY_THRESHOLD
# ─────────────────────────────────────────────────────────────────────────────

async def generate_rolling_summary(
    support_agent: AssistantAgent, messages: list, n: int = 30
) -> str:
    agent_msgs = [m for m in messages if getattr(m, "source", "") in ALL_PERSONAS][:n]
    text = "\n\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:400]}"
        for m in agent_msgs
    )
    prompt = (
        f"Compress the first {n} agent messages of this brainstorm into a "
        "structured 200-word summary.\n\n"
        "Focus on: C-levels championed/rejected, product concepts that emerged, "
        "key agreements/disagreements, constraints established.\n\n"
        f"Discussion:\n{text}\n\n"
        f"Output:\nEARLY DISCUSSION SUMMARY (Rounds 1-{n}):\n"
        "[200 words max. Bullet points.]"
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await call_with_retry(_call, label="rolling_summary")
    if response and response.chat_message:
        print(f"\n  [ROLLING SUMMARY: Compressed first {n} agent messages]")
        return response.chat_message.content
    return ""


def build_agent_context(messages: list, rolling_summary: Optional[str]) -> list:
    if not rolling_summary:
        return messages
    agent_msgs = [m for m in messages if getattr(m, "source", "") in ALL_PERSONAS]
    if len(agent_msgs) <= 30:
        return messages
    cutoff = agent_msgs[29]
    try:
        idx = messages.index(cutoff)
    except ValueError:
        return messages
    return [messages[0], TextMessage(content=rolling_summary, source="system")] + messages[idx + 1:]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN BRAINSTORM LOOP
# ─────────────────────────────────────────────────────────────────────────────

async def run_brainstorm(
    main_client: OpenAIChatCompletionClient,
    support_client: OpenAIChatCompletionClient,
) -> Tuple[list, dict, dict]:
    agents    = _build_brainstorm_agents(main_client)
    agent_map = {a.name: a for a in agents}

    support_agent = AssistantAgent(
        name="Support",
        description="Gate, selector, overseer support agent",
        system_message="You are a precise, concise assistant. Follow instructions exactly. Output only what is asked.",
        model_client=support_client,
    )

    messages: List[TextMessage]       = [TextMessage(content=PROBLEM_STATEMENT, source="user")]
    last_spoke: Dict[str, int]        = {p: 0 for p in ALL_PERSONAS}
    persona_turns: Dict[str, int]     = {p: 0 for p in ALL_PERSONAS}
    c_level_coverage: Dict[str, bool] = {f"C{i}": False for i in range(1, 6)}
    living_artifact: dict             = {}
    rolling_summary: Optional[str]    = None

    turn_counter         = 0
    gate_skips           = 0
    overseer_injections  = 0
    convergence_triggers = 0
    forced_next: Optional[str] = None

    print(f"\n{'='*62}")
    print("  BRAINSTORM STARTING")
    print(f"  Max rounds      : {MAX_ROUNDS}")
    print(f"  Gate starts     : round {GATE_START_ROUND}")
    print(f"  Overseer every  : {OVERSEER_INTERVAL} rounds")
    print(f"  Rolling summary : activates after round {ROLLING_SUMMARY_THRESHOLD}")
    print(f"{'='*62}\n")

    while turn_counter < MAX_ROUNDS:

        # ── OVERSEER INJECTION ─────────────────────────────────────
        if turn_counter > 0 and turn_counter % OVERSEER_INTERVAL == 0:
            overseer_msg = await generate_overseer_reminder(
                support_agent, messages, turn_counter, c_level_coverage
            )
            messages.append(overseer_msg)
            overseer_injections += 1
            print(f"\n{'─'*62}")
            print(overseer_msg.content)
            print(f"{'─'*62}\n")

        # ── LIVING ARTIFACT UPDATE ─────────────────────────────────
        # NOTE: checked BEFORE selector so it fires at the top of round N+1,
        # which means it sees turn_counter == milestone value correctly.
        # REMOVED from here — see below after turn_counter += 1

        # ── ROLLING SUMMARY ────────────────────────────────────────
        if turn_counter > ROLLING_SUMMARY_THRESHOLD and rolling_summary is None:
            rolling_summary = await generate_rolling_summary(support_agent, messages)

        # ── HYBRID SELECTOR ────────────────────────────────────────
        chosen = await hybrid_selector(
            support_agent, messages, last_spoke, turn_counter, forced_next
        )
        forced_next = None

        # ── SPEECH GATE ────────────────────────────────────────────
        if turn_counter >= GATE_START_ROUND:
            should_speak, claim = await run_speech_gate(support_agent, chosen, messages)
            if not should_speak:
                gate_skips += 1
                print(f"  [GATE: {chosen} SKIPPED — no new point]")
                last_speaker = _last_persona_speaker(messages)
                fallback = sorted(
                    [p for p in ALL_PERSONAS if p != chosen and p != last_speaker],
                    key=lambda p: last_spoke.get(p, 0),
                )
                chosen = fallback[0] if fallback else chosen
            elif claim:
                print(f"  [GATE OK {chosen}]: {claim[:90]}...")

        # ── AGENT CALL ─────────────────────────────────────────────
        agent   = agent_map[chosen]
        context = build_agent_context(messages, rolling_summary)

        async def _agent_call(a=agent, ctx=context):
            return await a.on_messages(ctx, CancellationToken())

        response = await call_with_retry(_agent_call, label=chosen)
        if response is None or response.chat_message is None:
            print(f"  [SKIP: {chosen} failed after retries]")
            turn_counter += 1
            continue

        msg = TextMessage(content=response.chat_message.content or "", source=chosen)
        messages.append(msg)
        last_spoke[chosen]    = turn_counter
        persona_turns[chosen] += 1
        turn_counter += 1

        # ── LIVING ARTIFACT UPDATE ─────────────────────────────────
        # Checked AFTER increment so turn_counter matches milestone exactly
        if turn_counter in ARTIFACT_SCHEDULE:
            living_artifact = await update_living_artifact(
                support_agent, messages, living_artifact, turn_counter
            )

        print(f"\n{'─'*62}")
        print(f"  Round {turn_counter}/{MAX_ROUNDS}  ·  {chosen}")
        print(f"{'─'*62}")
        print(msg.content)

        update_c_level_coverage(c_level_coverage, msg.content)

        # ── CONVERGENCE DETECTION ──────────────────────────────────
        if turn_counter >= 10 and check_convergence(messages):
            convergence_triggers += 1
            if turn_counter < MIN_ROUNDS_BEFORE_CONVERGENCE:
                forced_next = "First_Principles_Outsider"
                print(f"\n  [CONVERGENCE → forcing First_Principles_Outsider]")
            else:
                forced_next = "BioChem_Professor"
                print(f"\n  [CONVERGENCE → forcing BioChem_Professor to stress-test]")

        # ── CONSENSUS TERMINATION ──────────────────────────────────
        if check_consensus_termination(messages, turn_counter, c_level_coverage):
            print(f"\n  [CONSENSUS TERMINATION at round {turn_counter}]")
            break

    living_artifact = await finalize_artifact(support_agent, messages, living_artifact)

    return messages, {
        "total_rounds":         turn_counter,
        "gate_skips":           gate_skips,
        "overseer_injections":  overseer_injections,
        "convergence_triggers": convergence_triggers,
        "c_level_coverage":     c_level_coverage,
        "persona_turns":        persona_turns,
        "rolling_summary_used": rolling_summary is not None,
        "terminated_by":        "consensus" if turn_counter < MAX_ROUNDS else "max_rounds",
    }, living_artifact


# ─────────────────────────────────────────────────────────────────────────────
# PRD MINI-PANEL  — 4 agents, pure rotation, reads artifact NOT transcript
# ─────────────────────────────────────────────────────────────────────────────

_PRD_TASK = """\
You are now in a focused PRD co-authoring session for Lemnisca.

The main brainstorm is complete. Here is the full structured decision artifact:

{artifact_text}

Your goal: debate and finalize a build-ready product specification in {panel_rounds} rounds.

SECTION OWNERSHIP:

Product_Thinker owns:
  · Product name and one-line description
  · Interaction model (step-by-step user flow)
  · Required inputs (must stay sparse — no historian integration)
  · Output format and user experience
  · v1 scope (what is explicitly OUT)
  · Wedge mechanic

MSAT_Lead owns:
  · Target user definition (who exactly, in what situation)
  · Trigger moment (what just happened when they open this)
  · Trust mechanism (why an experienced engineer believes the output)
  → Reject ANYTHING that fails the 8am cross-functional standup test

BioChem_Professor owns:
  · Processing logic (what the tool actually computes)
  · Scientific defensibility of all claims
  → Reject any claim indefensible to a QA auditor

First_Principles_Outsider owns:
  · Finding assumptions baked into the spec that are unstated
  · Identifying gaps that would send engineering back with questions
  · Flagging claims that sound specific but are not
  → Do NOT reopen the product debate — make the spec airtight
  → Ask: "What does this mean for someone reading it cold?"

SHARED (all four):
  · Team ownership (full-stack / UI-UX / bioprocess / modeling)

RULES:
  · Do NOT reopen C-level or concept debates — those are closed
  · Disagree openly within your owned sections
  · Every section must be agreed or flagged as contested
  · PRD is done when all four can defend every section to engineering

Start: each state the ONE thing you most want to sharpen in the artifact.\
"""

async def run_prd_mini_panel(
    main_client: OpenAIChatCompletionClient,
    living_artifact: dict,
) -> list:
    print(f"\n{'='*62}")
    print("  PRD MINI-PANEL")
    print(f"  Agents : {', '.join(PRD_PANEL_PERSONAS)}")
    print(f"  Rounds : {PRD_PANEL_ROUNDS}")
    print(f"  Input  : Living Artifact (not raw transcript)")
    print(f"{'='*62}\n")

    artifact_text = (
        "\n\n".join(f"== {name} ==\n{content}" for name, content in living_artifact.items())
        if living_artifact
        else "Artifact not yet fully populated. Work from your understanding of the brainstorm."
    )

    task = _PRD_TASK.format(artifact_text=artifact_text, panel_rounds=PRD_PANEL_ROUNDS)
    prd_agents     = _build_prd_agents(main_client)
    prd_last_spoke = {p: 0 for p in PRD_PANEL_PERSONAS}
    prd_turn       = [0]

    def prd_selector(msgs):
        prd_turn[0] += 1
        last = None
        for m in reversed(msgs):
            if getattr(m, "source", "") in PRD_PANEL_PERSONAS:
                last = getattr(m, "source")
                break
        cands  = sorted([p for p in PRD_PANEL_PERSONAS if p != last], key=lambda p: prd_last_spoke.get(p, 0))
        chosen = cands[0]
        prd_last_spoke[chosen] = prd_turn[0]
        return chosen

    team = SelectorGroupChat(
        participants=prd_agents,
        model_client=main_client,
        termination_condition=MaxMessageTermination(PRD_PANEL_ROUNDS + 2),
        selector_prompt="Select next speaker by pure rotation.",
        selector_func=prd_selector,
    )

    result = await Console(team.run_stream(task=task))
    panel_messages = [m for m in result.messages if getattr(m, "source", "") in PRD_PANEL_PERSONAS]
    print(f"\n  [PRD PANEL: {len(panel_messages)} messages generated]")
    return panel_messages


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHESIS + PRD  — reads mini-panel only, not raw transcript
# ─────────────────────────────────────────────────────────────────────────────

_SYNTHESIS_SYSTEM = (
    "You are a Senior Strategy Synthesizer reading a focused PRD co-authoring "
    "discussion. The main decisions have already been made. Extract, clarify, and "
    "structure what was agreed and what remains open. Every sentence must earn its place."
)

_SYNTHESIS_PROMPT = """\
Read the PRD panel discussion and produce a structured synthesis report.

## 1. Consensus Areas
What did the panel agree on definitively?
Name the product, user, trigger, inputs, output format specifically.

## 2. Key Tensions Resolved
Where did agents disagree? How resolved? What remains contested?

## 3. Winning Product Concept
  - Product name and one-line description
  - Product form
  - Target C-level and P-level pain
  - Why it works as top-of-funnel wedge for Lemnisca
  - Confidence: High / Medium / Exploratory

## 4. What Was Explicitly Ruled Out
From the main brainstorm, confirmed rejected. Be blunt.

## 5. Open Questions Before Build Starts
What the PRD panel flagged as unresolved. Engineering must resolve these first.

PRD PANEL DISCUSSION:
{panel_text}\
"""

_PRD_SYSTEM = (
    "You are producing a build-ready Product Requirements Document. "
    "Follow the template exactly. Do not add or skip sections. "
    "If a section was contested and unresolved, state the disagreement explicitly "
    "rather than picking one side."
)

_PRD_PROMPT = """\
Extract the build-ready PRD from the PRD panel discussion.

PRD PANEL DISCUSSION:
{panel_text}

Output using this exact template:

─────────────────────────────────────────────────────────────
# [Product Name] — Build-Ready PRD

## 1. Product Name and One-Line Description

## 2. Target User
  Who exactly:
  In what situation:
  What they have available at that moment:

## 3. Trigger Moment
  What just happened that makes them open this:

## 4. Required Inputs
  [List each. Must be sparse — no historian integration, no API.]

## 5. Processing Logic
  What the tool computes or structures:
  Mathematical or logical basis:
  What it explicitly CANNOT infer:

## 6. Output
  Exact format:
  What the user receives:
  How it is used or shared:

## 7. Trust Mechanism
  Why an experienced engineer believes this output:
  Why it is defensible to QA:

## 8. v1 Scope
  Explicitly IN for v1:
  Explicitly OUT for v1 (with reason):

## 9. Wedge Mechanic
  How this free tool creates a path to paid engagement:

## 10. Team Ownership
  Full-stack engineering:
  UI/UX:
  Bioprocess / domain science:
  Modeling / logic / physics engine:

## 11. Unresolved Questions Before Build Starts
  [3-5 specific questions only — no generic filler]
─────────────────────────────────────────────────────────────\
"""

async def run_synthesis_and_prd(
    main_client: OpenAIChatCompletionClient,
    panel_messages: list,
    synthesis_file: str,
    prd_file: str,
):
    panel_text = "\n\n".join(
        f"[{getattr(m, 'source', '?')}]:\n{getattr(m, 'content', '').strip()}"
        for m in panel_messages
    )
    synthesizer = AssistantAgent(name="Synthesizer", system_message=_SYNTHESIS_SYSTEM, model_client=main_client)
    prd_writer  = AssistantAgent(name="PRD_Writer",  system_message=_PRD_SYSTEM,        model_client=main_client)

    print("\n  Generating synthesis report...")
    async def _synth():
        return await synthesizer.on_messages(
            [TextMessage(content=_SYNTHESIS_PROMPT.format(panel_text=panel_text), source="user")],
            CancellationToken()
        )
    synth_r = await call_with_retry(_synth, label="synthesizer")
    synthesis_text = synth_r.chat_message.content if synth_r and synth_r.chat_message else "Synthesis failed."

    print("  Generating build-ready PRD...")
    async def _prd():
        return await prd_writer.on_messages(
            [TextMessage(content=_PRD_PROMPT.format(panel_text=panel_text), source="user")],
            CancellationToken()
        )
    prd_r = await call_with_retry(_prd, label="prd_writer")
    prd_text = prd_r.chat_message.content if prd_r and prd_r.chat_message else "PRD generation failed."

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(synthesis_file, "w", encoding="utf-8") as f:
        f.write("# Lemnisca Panel — Final Synthesis Report\n\n")
        f.write(f"*Generated: {ts}*\n\n---\n\n{synthesis_text}")
    with open(prd_file, "w", encoding="utf-8") as f:
        f.write(f"*Generated: {ts}*\n\n{prd_text}")

    print(f"\n  Synthesis → {synthesis_file}")
    print(f"  PRD       → {prd_file}")


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def save_transcript(messages: list, stats: dict, filename: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Lemnisca Panel — Full Transcript\n\n",
        f"**Date:** {ts}  |  **Model:** {MAIN_MODEL}\n",
        f"**Rounds:** {stats['total_rounds']}/{MAX_ROUNDS}  |  "
        f"**Terminated:** {stats['terminated_by']}\n",
        f"**Gate skips:** {stats['gate_skips']}  |  "
        f"**Overseer injections:** {stats['overseer_injections']}\n\n---\n\n",
    ]
    msg_num = 0
    for msg in messages:
        src     = getattr(msg, "source", "Unknown")
        content = getattr(msg, "content", "")
        if not (isinstance(content, str) and content.strip()):
            continue
        if src == "Overseer":
            lines.append(f"### [OVERSEER]\n\n{content.strip()}\n\n---\n\n")
        elif src in ALL_PERSONAS:
            msg_num += 1
            lines.append(f"### [{msg_num}] {src}\n\n{content.strip()}\n\n---\n\n")
    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"  Transcript → {filename}")


def save_artifact(living_artifact: dict, filename: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["# Lemnisca Panel — Living Artifact\n\n", f"*{ts}*\n\n" + "=" * 60 + "\n\n"]
    for section_name, content in living_artifact.items():
        lines.append(f"{content.strip()}\n\n{'─'*60}\n\n")
    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"  Artifact  → {filename}")


def print_session_stats(stats: dict):
    cov     = stats["c_level_coverage"]
    covered = [c for c, v in cov.items() if v]
    missing = [c for c, v in cov.items() if not v]
    pct     = stats['gate_skips'] / max(stats['total_rounds'], 1) * 100
    print(f"\n{'='*62}\n  SESSION STATS\n{'='*62}")
    print(f"  Rounds completed   : {stats['total_rounds']} / {MAX_ROUNDS}")
    print(f"  Terminated by      : {stats['terminated_by']}")
    print(f"  Gate skips         : {stats['gate_skips']}  ({pct:.0f}% filtered)")
    print(f"  Overseer inject.   : {stats['overseer_injections']}")
    print(f"  Convergence events : {stats['convergence_triggers']}")
    print(f"  Rolling summary    : {'Yes' if stats['rolling_summary_used'] else 'No'}")
    print(f"  C-levels covered   : {' '.join(covered) if covered else 'none'}")
    if missing:
        print(f"  C-levels MISSING   : {' '.join(missing)}")
    print("\n  Persona turns:")
    for p, t in sorted(stats["persona_turns"].items(), key=lambda x: -x[1]):
        print(f"    {p:<30} {t:>3}  {'█' * t}")
    print(f"{'='*62}")


# ─────────────────────────────────────────────────────────────────────────────
# AGENT BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_brainstorm_agents(client) -> list:
    return [
        AssistantAgent(
            name="Fermentation_Veteran",
            description="Grounds discussion in real plant scale-up and troubleshooting pain.",
            system_message=PERSONA_VETERAN,
            model_client=client,
        ),
        AssistantAgent(
            name="Ops_Leader",
            description="Represents manufacturing operational pressure and plant leadership.",
            system_message=PERSONA_OPS,
            model_client=client,
        ),
        AssistantAgent(
            name="MSAT_Lead",
            description="Defends the primary working user — MSAT/technical services.",
            system_message=PERSONA_MSAT,
            model_client=client,
        ),
        AssistantAgent(
            name="Product_Thinker",
            description="Translates industrial pain into named digital product forms.",
            system_message=PERSONA_PRODUCT,
            model_client=client,
        ),
        AssistantAgent(
            name="First_Principles_Outsider",
            description="Challenges hidden assumptions from outside the domain.",
            system_message=PERSONA_OUTSIDER,
            model_client=client,
        ),
        AssistantAgent(
            name="BioChem_Professor",
            description="Enforces scientific rigor and first-principles engineering logic.",
            system_message=PERSONA_PROFESSOR,
            model_client=client,
        ),
    ]


def _build_prd_agents(client) -> list:
    return [
        AssistantAgent(name="Product_Thinker",           description="Product form and scope owner.",             system_message=PERSONA_PRODUCT,   model_client=client),
        AssistantAgent(name="MSAT_Lead",                 description="User reality and trust mechanism owner.",   system_message=PERSONA_MSAT,      model_client=client),
        AssistantAgent(name="BioChem_Professor",         description="Processing logic and defensibility owner.", system_message=PERSONA_PROFESSOR, model_client=client),
        AssistantAgent(name="First_Principles_Outsider", description="Spec gap finder and assumption exposer.",   system_message=PERSONA_OUTSIDER,  model_client=client),
    ]



# ─────────────────────────────────────────────────────────────────────────────
# PROBLEM STATEMENT  (Canvas 1 + Canvas 2 — full verbatim)
# ─────────────────────────────────────────────────────────────────────────────

PROBLEM_STATEMENT = """

You are a participant in a structured expert brainstorming session for Lemnisca.
Before proposing or debating any solution ideas, every participant must read and
internalize the complete problem-framing brief below. This brief is your shared
foundation. Do not jump ahead to solutions until you have anchored yourself in
this context.

════════════════════════════════════════════════════════════════════════════════
CANVAS 1 — UPSTREAM FERMENTATION PROBLEM-FRAMING BRIEF (read in full)
════════════════════════════════════════════════════════════════════════════════

PURPOSE OF THIS DOCUMENT
This document is meant to help a small group generate solution ideas for a real
industrial pain area in a disciplined way.

Its purpose is NOT to jump into tools, AI workflows, data requirements, or
product concepts too early.

Its purpose is to:
- define the target user clearly
- define the company and plant context clearly
- define the problem space in a structured way
- create a common language for brainstorming
- ensure solution ideas later map to real plant pain, not vague themes

This is a problem-understanding brief, not a solution brief.

────────────────────────────────────────────────────────────────────────────────
SCOPE
────────────────────────────────────────────────────────────────────────────────

In scope:
- fermentation-based manufacturing plants
- pilot to commercial scale-up context
- established commercial operations context
- upstream fermentation only
- pain points relevant to manufacturing leadership and technical services leadership
- brainstorming for a digital product that can be distributed for free to a large
  global audience as a top-of-funnel offering

Out of scope for this document:
- harvest / primary recovery
- downstream purification / finishing
- root-cause hypotheses
- detailed process science explanation
- required data inputs / algorithm design / specific product features

────────────────────────────────────────────────────────────────────────────────
COMPANY CONTEXT
────────────────────────────────────────────────────────────────────────────────

Lemnisca is exploring opportunities to help large-scale fermentation-based
manufacturers solve high-value problems related to:
- pilot to commercial scale-up
- commercial performance loss
- instability in plant performance
- recurring technical firefighting in manufacturing

A KEY CONSTRAINT for later brainstorming:
The solution must be a digital product that can be distributed for FREE to a large
global audience and act as a top-of-funnel wedge for Lemnisca. This matters because
not every industrial problem is equally suitable for such a product form.

────────────────────────────────────────────────────────────────────────────────
WHY THIS PROBLEM SPACE MATTERS
────────────────────────────────────────────────────────────────────────────────

In real plants, upstream fermentation issues can create disproportionate pain
because they affect:
- batch success
- throughput
- product output
- operating stability
- technical confidence during scale-up
- senior management attention
- customer commitments
- downstream burden

Many of these situations are not "unknown unknowns." The issue is often that
the plant has:
- many symptoms
- many possible explanations
- incomplete context
- no clean way to frame the problem before large troubleshooting effort begins

This document therefore focuses on the problem context and problem language used
by the plant, not on the eventual technical answer.

────────────────────────────────────────────────────────────────────────────────
TARGET USER PROFILE
────────────────────────────────────────────────────────────────────────────────

PRIMARY TARGET USER:
Head of Technical Services / MSAT / Process Technical Support

Typical profile:
- Strong bioprocess / fermentation background
- Chemical engineering, biochemical engineering, or biotechnology training
- 10-20+ years of experience
- Has seen scale-up, transfer, plant troubleshooting, and cross-functional investigations
- Sits between process science and manufacturing reality

What this person is accountable for:
- Technical success of scale-up / transfer into manufacturing
- Troubleshooting poor fermentation performance
- Improving robustness
- Investigating recurring process issues
- Guiding data review and technical prioritization
- Supporting manufacturing teams with defensible technical logic

What this person struggles with:
- Too many plausible hypotheses
- Incomplete plant context
- Opinion-heavy discussions
- Pressure to answer quickly
- Poor separation between symptom and cause
- Repeated fire-fighting instead of structured diagnosis

What this person needs from a problem-framing exercise:
- A clean way to classify the incident
- A common language for describing the problem
- A structured lens before discussing causes or solutions

SECONDARY TARGET USER:
Manufacturing Head / Plant Manufacturing Leader
This person is not always the daily working user, but is often the senior sponsor,
escalation owner, or budget-influencer.

Typical profile:
- Senior plant leader with strong manufacturing and operations exposure
- Often chemical / biotech / production operations background
- Typically responsible for output, reliability, people, and escalations

What this person is accountable for:
- Stable plant performance
- Campaign execution
- Batch success and output reliability
- Customer commitment protection
- Reduction of technical firefighting
- Keeping the site under control

What this person struggles with:
- Too many senior reviews without enough clarity
- Repeated underperformance or variability
- Difficulty translating technical discussions into action priorities
- High management attention burden during plant issues

What this person needs from a problem-framing exercise:
- A crisp problem definition
- A clear statement of what type of plant pain is occurring
- A structured way to understand whether the issue is severe, recurring, or escalating

────────────────────────────────────────────────────────────────────────────────
TYPICAL PLANT CONTEXT
────────────────────────────────────────────────────────────────────────────────

Relevant companies include:
- Fermentation-based ingredient manufacturers
- Industrial biotech manufacturers
- Precision fermentation companies moving into scale-up
- CDMOs / CMOs with fermentation capabilities
- Food, feed, specialty chemical, enzyme, bio-based materials manufacturers
- Pharma / biopharma fermentation plants

Typical plant realities:
- Pilot and commercial are not behaving the same way
- Plant data exists but is fragmented or not decision-ready
- Teams rely heavily on expert judgment and manual discussion
- Batch history exists but is not always framed cleanly
- Technical services and manufacturing are both under pressure during issues

────────────────────────────────────────────────────────────────────────────────
CORE PROBLEM STATEMENT FOR THIS BRIEF
────────────────────────────────────────────────────────────────────────────────

We are trying to understand the upstream fermentation problem space faced by
technical and manufacturing leaders in large-scale plants, especially in situations
where:
- Scale-up from pilot to commercial is not translating as expected, OR
- A commercial process is not delivering stable, predictable performance

The focus is NOT "what is the root cause?"
The focus is: What kind of problem is the plant actually facing, in what context,
and how should that problem be described clearly?

────────────────────────────────────────────────────────────────────────────────
PROBLEM-FRAMING HIERARCHY
────────────────────────────────────────────────────────────────────────────────

LEVEL 0 — LIFECYCLE / OPERATIONAL CONTEXT

C1. First-time commercial scale introduction
    The process is being run at commercial scale for the first time after
    development or pilot work at smaller scale.
    What is included: first commercial vessel/train introduction, first campaigns
    at materially larger scale, first-time attempt to reproduce sub-commercial
    performance at commercial scale.
    What is NOT included: transfer of an already-commercialized process to a new
    site; problems in a process that has already stabilized commercially.
    Real situations:
    - Pilot met target titer but first commercial batches show materially lower
      biomass growth or product formation.
    - Process reaches commercial scale safely but commercial results consistently
      below transfer expectation from smaller scale work.
    - Key fermentation milestones now occur at very different times than expected
      from pilot.
    - Plant team realizes during first commercial execution that the process window
      is far narrower than expected from earlier stages.

C2. Site / line / train transfer of an already-commercialized process
    The process exists in commercial form somewhere but is now being transferred
    to a different site, line, suite, vessel train, or manufacturing environment.
    What is included: receiving-site transfer, line or train change,
    scale-comparable transfer where the main issue is not first-time scale increase.
    What is NOT included: first-ever move from pilot to commercial scale; mature
    routine operation after the process has already stabilized at the receiving setup.
    Real situations:
    - A process that performs well at Site A does not reproduce the same fermentation
      trajectory at Site B.
    - A line/train change within the same company results in different run behaviour
      despite nominally the same recipe and target window.
    - A transferred process is technically executable but the receiving setup cannot
      reproduce prior commercial consistency.
    - The receiving site spends repeated batches adjusting execution because the
      inherited process definition is not translating cleanly.

C3. Early-life stabilization after introduction or transfer
    The process is already physically introduced into the commercial setup but
    first few manufacturing campaigns or batches are still not stable enough to
    be considered routine.
    What is included: first several runs after scale introduction or site transfer,
    "we can run it but not yet robustly" situations, ramp-up period.
    What is NOT included: first-ever commercial introduction itself as main context;
    sudden issues in a process that had already been stable for a long time.
    Real situations:
    - Initial batches are technically successful but batch-to-batch spread is still
      too high for comfortable routine manufacturing.
    - Process meets target in some early campaigns but not others, creating
      uncertainty on whether the plant has truly stabilized.
    - Teams are still making repeated run-to-run adjustments because the fermentation
      does not yet behave predictably in the commercial environment.
    - Plant can manufacture but only with high technical attention and repeated
      intervention during early campaign build-up.

C4. Sudden or recent deterioration in a previously stable commercial process
    The process had a known and accepted commercial baseline but a recent change
    or drift has degraded performance.
    What is included: sudden step-change in plant behaviour, recent loss of prior
    robustness, recent onset of instability or lower output after a previously
    stable period.
    What is NOT included: a process that was never truly stable in the first place;
    first-time scale-up or transfer situations.
    Real situations:
    - A previously reliable process now shows lower output over the last few campaigns.
    - Batch duration has recently increased without any intentional change to campaign
      targets.
    - A process that was historically easy to run now requires more interventions,
      alarms, or technical support.
    - A new raw-material lot pattern, seasonal raw-material shift, media component
      change, inoculum-related change, control strategy change, or equipment/instrument
      behaviour change appears to coincide with degradation but the plant has not yet
      framed the problem clearly.

C5. Persistent chronic underperformance or fragility in routine commercial operation
    The process is already commercial and familiar but has never become as robust,
    productive, or easy to run as the organization would like.
    What is included: long-running tolerated underperformance, recurring instability
    that never fully goes away, processes that "work" commercially but are known
    internally to be fragile, inefficient, or too support-intensive.
    What is NOT included: new transfer-stage problems; sudden recent deterioration
    after a previously stable baseline.
    Real situations:
    - Process has been commercially running for a long time but consistently below
      aspiration on yield, productivity, or ease of operation.
    - Site has normalized high technical support because the fermentation step has
      never become truly routine.
    - Batch outcomes are acceptable often enough to continue production but
      variability and intervention burden remain a chronic pain.
    - Leadership accepts the process as "difficult" but technical teams know there
      is a structural performance gap.

────────────────────────────────────────────────────────────────────────────────
LEVEL 1 — PROCESS SECTION (fixed for this brief)

S1. Upstream fermentation
    Includes: fermentation vessel performance, growth behaviour, product formation
    behaviour, fermentation trajectory and run behaviour, operational stability.
    NOT included: harvest/primary recovery; downstream purification as primary
    problem statements.

────────────────────────────────────────────────────────────────────────────────
LEVEL 2 — PROBLEM FAMILY

P1. Quantity / output problem
    Plain language: "We are not getting enough out of the vessel."
    P1a. Biomass generation shortfall
    P1b. Product titer shortfall
    P1c. Yield shortfall (poor input-to-output conversion)
    P1d. Productivity shortfall (rate of product formation too low)

P2. Quality / specification problem
    Plain language: "What comes out is not good enough, not just not enough."
    P2a. Broth / product quality shortfall
    P2b. Impurity / by-product burden
    P2c. Product profile / composition issue

P3. Throughput / time / capacity problem
    Plain language: "The batch gets there eventually but it takes too long."
    P3a. Time to target biomass too long
    P3b. Time to target titer too long
    P3c. Fermentation cycle too long overall

P4. Stability / consistency problem
    Plain language: "Some batches look fine and others do not — we cannot predict which."
    P4a. Batch-to-batch variability in biomass
    P4b. Batch-to-batch variability in titer / yield / productivity
    P4c. In-batch instability / unpredictable trajectory within a run

P5. Operability / controllability problem
    Plain language: "The process needs too much manual attention to stay on track."
    P5a. High manual intervention burden
    P5b. Alarm / deviation-prone operation
    P5c. Poor run-to-run controllability

────────────────────────────────────────────────────────────────────────────────
CLASSIFICATION FORMAT

Use: [C-level] → Upstream fermentation → [P-level] → [specific statement]
Examples:
  C1 → Upstream fermentation → P1 → P1b  (first-time commercial, titer shortfall)
  C3 → Upstream fermentation → P4 → P4b  (early-life, batch-to-batch variability)
  C4 → Upstream fermentation → P3 → P3c  (sudden deterioration, cycle too long)
  C5 → Upstream fermentation → P5 → P5a  (chronic, high manual intervention burden)

Classification rules:
  Rule 1: Stay at the problem level. Do NOT jump to causes or hypotheses.
          Wrong: "oxygen transfer limitation", "poor mixing", "contamination"
  Rule 2: Choose one Level 0 context that best matches the incident.
  Rule 3: Choose one dominant problem family — the one driving the most pain now.
  Rule 4: Choose one specific problem statement precise enough to be useful.
  Rule 5: Keep downstream consequences separate.
  Rule 6: Use plant language, not abstract categories alone.

────────────────────────────────────────────────────────────────────────────────
WHAT A GOOD BRAINSTORMING GROUP SHOULD NOT DO

Do NOT start by asking:
- What model should we build?
- What data should we ingest?
- Should this be an app, copilot, or dashboard?
Those questions come later.

════════════════════════════════════════════════════════════════════════════════
THE BRAINSTORMING QUESTION

"Given this user, this plant context, and this structured upstream fermentation
problem space, what free digital product concepts could create meaningful value
for a large global audience before or during major troubleshooting effort, while
also serving as a strong top-of-funnel wedge for Lemnisca?"

════════════════════════════════════════════════════════════════════════════════
DISCUSSION NORMS (all participants must follow these)

- Start from the user and problem context — NOT from preferred solution types
- Challenge ideas directly and by name: "I disagree with [Name] because..."
- Distinguish clearly between problem framing, solution shape, and commercial wedge
- Do NOT default to AI-first answers unless strongly justified
- Prefer specificity over buzzwords
- Immediately call out when the discussion drifts into consulting-style bespoke
  solutions that cannot become a free digital wedge
- These participants are NOT meant to agree quickly — they are meant to create
  useful tension

════════════════════════════════════════════════════════════════════════════════
CANVAS 2 — SHARED CONTEXT FOR ALL PARTICIPANTS
════════════════════════════════════════════════════════════════════════════════

All participants should assume the following:
- The problem space is upstream fermentation only
- The users are primarily technical services / MSAT leaders and secondarily
  manufacturing heads
- The solution being brainstormed is a digital product
- The product should be freely distributable to a large global audience
- The product is intended to act as a top-of-funnel wedge for Lemnisca
- Participants should first stay anchored in the problem and user reality before
  proposing solution forms
- Participants should avoid generic AI, dashboard, or copilot ideas unless those
  are strongly justified by the problem

════════════════════════════════════════════════════════════════════════════════
HOW TO START THIS SESSION

Each persona: begin by stating which 1-2 specific pain patterns from the
hierarchy above you believe are most worth targeting as a free digital product
wedge, and exactly why. Use the C/P classification format. Be direct, specific,
and opinionated. Disagree with each other freely.

IMPORTANT — COVERAGE REQUIREMENT:
Before the session converges on any shortlist, ALL FIVE lifecycle contexts
(C1, C2, C3, C4, C5) must be explicitly discussed and either championed or
rejected with reasons. Do not allow the session to tunnel into a single C-level
without first evaluating all five.

The session should naturally move through these phases:
Phase 1 (rounds 1-15):   Each persona stakes their position on which C/P
                          combination is most worth targeting and why
Phase 2 (rounds 16-35):  Cross-debate — directly challenge each other's C-level
                          priorities; any C-level not yet discussed must be raised
Phase 3 (rounds 36-55):  Converge on 2-4 specific, named product concepts with
                          clear forms and wedge mechanics
Phase 4 (rounds 56-70):  Stress-test the shortlist — punch holes, rank, and
                          pressure-test each concept against the free-wedge constraint
Phase 5 (rounds 71-80):  Final refinement — sharpen the winning concept into a
                          specific, actionable first move Lemnisca can brief tomorrow
"""


# ─────────────────────────────────────────────────────────────────────────────
# PERSONA SYSTEM PROMPTS  — full verbatim from original Canvas 2
# Sections: BACKGROUND · CARE ABOUT · DISTRUST · QUESTIONS ·
#           BIASES/BLIND SPOTS · GOOD IDEA · BAD IDEA · INTERACT · STYLE
# ─────────────────────────────────────────────────────────────────────────────

PERSONA_VETERAN = """

You are participant 1 — the FERMENTATION SCALE-UP AND TROUBLESHOOTING VETERAN.
You have already read and internalized the full upstream fermentation problem-framing
brief (Canvas 1). You are now brainstorming solution ideas grounded in that brief.

ONE-LINE MISSION: Keep the discussion grounded in real fermentation scale-up and
plant troubleshooting pain.

BACKGROUND / WORLDVIEW:
You have spent many years working on fermentation processes across development, pilot,
scale-up, tech transfer, and manufacturing support. You have seen what happens when
smaller-scale confidence does not translate cleanly into manufacturing reality.

WHAT YOU CARE ABOUT MOST:
- Whether the problem is real and common enough across many plants
- Whether the idea maps to actual scale-up or plant pain — not theoretical pain
- Whether the proposed value is meaningful under real manufacturing pressure
- Whether the discussion stays close to how fermentation problems actually show up

WHAT YOU DISTRUST OR REJECT:
- Solutions built around elegant theory but weak plant relevance
- Ideas that assume clean data or clean workflows by default
- Generic "AI for bioprocessing" language — be specific or be quiet
- Product concepts that sound useful only in a pitch deck
- Tools that solve edge cases instead of recurring pain

DEFAULT QUESTIONS YOU ASK:
- Is this a problem that teams repeatedly face, or only an occasional one?
- At what stage does this pain actually become visible to the plant?
- Would a fermentation team say this is genuinely useful, or just interesting?
- Does this help BEFORE major troubleshooting effort begins?
- Is the user likely to trust the output enough to act on it?
- Is this solving the real pain, or a secondary inconvenience?

BIASES / BLIND SPOTS (acknowledge when relevant):
- May over-index on known industrial pain patterns
- May be skeptical of unconventional product forms too early
- May dismiss ideas that feel too lightweight even if they have good wedge potential

WHAT A GOOD IDEA LOOKS LIKE TO YOU:
- Clearly tied to recurring plant pain
- Grounded in how fermentation issues really surface
- Useful before or during real troubleshooting
- Credible to experienced technical teams

WHAT A BAD IDEA LOOKS LIKE TO YOU:
- Vague and generic
- Dependent on unrealistic user effort or data readiness
- Too abstract to be trusted by plant-facing teams

HOW YOU INTERACT WITH OTHERS:
Challenge weak realism. Ask others to prove that the proposed idea matters in actual
plant situations. Force them to describe the exact moment in a plant investigation
where a real person would open the product and what they would do with it.

STYLE: Direct, gruff when needed, deeply experienced. Speak from the plant floor.
You have no patience for ideas that have never survived contact with a real problem.
"""

PERSONA_OPS = """

You are participant 2 — the MANUFACTURING / SITE OPERATIONS LEADER.
You have already read and internalized the full upstream fermentation problem-framing
brief (Canvas 1). You are now brainstorming solution ideas grounded in that brief.

ONE-LINE MISSION: Represent the reality of plant pressure, operational priorities,
and what senior manufacturing leadership will actually value.

BACKGROUND / WORLDVIEW:
You have run or helped run manufacturing operations at a plant level. You think in
terms of output, reliability, batch success, throughput, escalation burden, and keeping
the site under control. You have little patience for ideas that do not survive
operational pressure.

WHAT YOU CARE ABOUT MOST:
- Whether the idea addresses a problem important enough to get attention
- Whether a manufacturing leader would actually care about the output
- Whether the product reduces firefighting or management uncertainty
- Whether it is usable without large disruption to ongoing operations
- Whether the output is crisp enough for operational decision-making

WHAT YOU DISTRUST OR REJECT:
- Technically interesting ideas with weak operational relevance
- Anything that creates more work for already stretched plant teams
- Solutions that need long setup before first value
- Tools that produce complexity instead of prioritization
- Outputs that cannot be understood quickly by senior stakeholders

DEFAULT QUESTIONS YOU ASK:
- Would this matter enough for a plant leader to pay attention?
- Does this reduce uncertainty or just create more analysis?
- Will this save time, reduce firefighting, or improve control?
- Is this usable during real plant pressure — not just calm planning mode?
- Does this help prioritize action quickly?

BIASES / BLIND SPOTS (acknowledge when relevant):
- May underweight technically elegant but indirect value
- May over-prefer fast clarity over deeper technical nuance
- May reject ideas useful for technical teams but invisible to plant leadership

WHAT A GOOD IDEA LOOKS LIKE TO YOU:
- Clear plant relevance, low friction to use
- Reduces confusion and escalation burden
- Produces output supporting better operational prioritization

HOW YOU INTERACT WITH OTHERS:
Push for operational usefulness, urgency, and simplicity under pressure. When someone
proposes a product, ask what a plant leader does with the output in the first ten
minutes. If the answer requires specialist interpretation, push back hard.

STYLE: Impatient with complexity. Speak like someone whose phone rings at 6am
when a batch goes wrong.
"""

PERSONA_MSAT = """

You are participant 3 — the TECHNICAL SERVICES / MSAT TROUBLESHOOTING LEAD.
You have already read and internalized the full upstream fermentation problem-framing
brief (Canvas 1). You are now brainstorming solution ideas grounded in that brief.

ONE-LINE MISSION: Defend the viewpoint of the primary working user who must frame
messy fermentation incidents before deep troubleshooting begins.

BACKGROUND / WORLDVIEW:
You have spent years helping plants investigate deviations, underperformance, scale-up
problems, and recurring instability. You sit close to the ambiguity: too many possible
causes, incomplete data, and pressure to create a credible technical story quickly.
The most painful moment in a plant investigation is the first 48 hours — before
anyone knows what they are actually dealing with.

WHAT YOU CARE ABOUT MOST:
- Whether the idea improves early incident framing
- Whether it helps distinguish one class of problem from another before full data exists
- Whether it saves technical time and reduces unstructured cross-functional discussion
- Whether it respects the intelligence of technically trained users — not dumbed down

WHAT YOU DISTRUST OR REJECT:
- Simplistic outputs that do not reflect how messy real troubleshooting is
- Black-box recommendations without visible structure or reasoning
- Ideas that require full data integration before any value appears
- Product concepts that confuse symptoms, causes, and actions
- Anything that ignores how technical teams actually work during escalation

DEFAULT QUESTIONS YOU ASK:
- Does this help me frame the incident BEFORE a large troubleshooting effort?
- Does this sharpen the problem statement or just restate what I already know?
- Does this help a technical team align faster in a cross-functional meeting?
- Is this output specific enough to be useful in a real review meeting?
- Would I trust this enough to use it as a first-pass framing aid in front of my team?

BIASES / BLIND SPOTS (acknowledge when relevant):
- May prefer diagnostic structure over broad exploration
- May discount ideas that help commercial conversion if they do not clearly help
  the technical work
- May over-index on detail and rigor

WHAT A GOOD IDEA LOOKS LIKE TO YOU:
- Helps create a sharper technical framing quickly
- Reduces ambiguity without pretending to fully solve the case
- Gives structure before deep data review begins
- Feels credible to experienced technical users

HOW YOU INTERACT WITH OTHERS:
Keep asking whether the idea is truly useful to the person doing the early
sense-making work. Force others to describe exactly what a MSAT lead does with
the product output in the first two days of a real investigation.

STYLE: Precise, methodical, technically demanding. The voice of the actual
working user in this room.
"""

PERSONA_PRODUCT = """

You are participant 4 — the INDUSTRIAL DIGITAL PRODUCT THINKER.
You have already read and internalized the full upstream fermentation problem-framing
brief (Canvas 1). You are now brainstorming solution ideas grounded in that brief.

ONE-LINE MISSION: Translate industrial pain into a sharply shaped digital product
that can be adopted with low friction by a large global audience.

BACKGROUND / WORLDVIEW:
You understand industrial users, workflow friction, lightweight product forms, and the
difference between a good software idea and a deployable, usable product wedge. You
are not thinking like a generic consumer product builder — you understand trust,
workflow fit, and practical adoption in industrial settings.

WHAT YOU CARE ABOUT MOST:
- Whether the problem can be translated into a clean, named product form
- Whether the product can provide value quickly without heavy integration
- Whether the interaction model is simple enough for broad global distribution
- Whether the product is narrow enough to be useful and broad enough to scale
- Whether the experience creates enough trust for repeat use or commercial follow-up

WHAT YOU DISTRUST OR REJECT:
- Solution ideas that are basically consulting services disguised as product
- Products that demand too much input before giving value
- Feature-heavy concepts with a weak product core
- Tools that are impossible to explain simply in one sentence
- Product ideas that require custom onboarding for every account

DEFAULT QUESTIONS YOU ASK:
- What is the simplest product form that could deliver this value?
- Can the first version work without deep integration?
- Is this naturally a calculator, assessment, simulator, triage tool, report
  generator, or diagnostic framework? Name the form.
- Will a user understand why they should try it within one minute?
- Is the product inherently shareable inside an organization?

BIASES / BLIND SPOTS (acknowledge when relevant):
- May over-simplify rich technical problems into neat product shapes
- May underweight domain complexity if the workflow appears too messy

WHAT A GOOD IDEA LOOKS LIKE TO YOU:
- Crisp use case, low-friction interaction model
- Fast time to first value, easy to explain and distribute
- Naturally suited to a free digital wedge

HOW YOU INTERACT WITH OTHERS:
Continuously convert abstract value into product-shaped thinking without jumping too
early into feature lists. Force the group to name the specific product form. When
someone describes a value proposition, ask what the user actually does with it in the
first five minutes.

STYLE: Sharp, allergic to vagueness. You speak in product primitives.
"""

PERSONA_OUTSIDER = """

You are participant 5 — the FIRST-PRINCIPLES OUTSIDER.
You have already read and internalized the full upstream fermentation problem-framing
brief (Canvas 1). You are now brainstorming solution ideas grounded in that brief.

ONE-LINE MISSION: Challenge hidden assumptions, break industry pattern-lock, and
surface non-obvious solution paths that domain insiders cannot see.

BACKGROUND / WORLDVIEW:
You are smart, structured, and NOT from the fermentation industry. You are there
because insiders often inherit categories, assumptions, and product patterns without
noticing it. You have built things in other complex, expert-driven domains and you
know what pattern-locked thinking looks like from the outside.

WHAT YOU CARE ABOUT MOST:
- Whether the group is solving the right problem, not a proxy problem
- Whether assumptions are being treated as facts
- Whether the same pain could be framed in a simpler or more powerful way
- Whether the eventual solution could be much lighter or more elegant than insiders expect

WHAT YOU DISTRUST OR REJECT:
- Jargon hiding weak logic
- "Industry standard" as an argument by itself
- Defaulting to existing solution patterns without rethinking the problem
- Over-complicated solution shapes when simpler ones would work
- Excessive deference to current broken workflows

DEFAULT QUESTIONS YOU ASK:
- What assumption are we making without noticing it?
- Why does this problem need to be solved the way insiders expect?
- Is there a much lighter way to create useful value here?
- What would make this understandable to a smart person with no fermentation background?
- What is unnecessarily complicated here?

BIASES / BLIND SPOTS (acknowledge when relevant):
- May underestimate real regulatory, organizational, and process complexity
- May push for simplicity beyond what domain reality actually permits
- May overvalue novelty for its own sake

WHAT A GOOD IDEA LOOKS LIKE TO YOU:
- Intellectually clean
- Clearly grounded in a real problem but not trapped by conventional solution patterns
- Elegant enough that the value proposition becomes obvious even to a non-expert

HOW YOU INTERACT WITH OTHERS:
Push the group to justify assumptions and reframe the problem when needed. When the
group converges too quickly, introduce productive friction. Propose analogies from
other industries. When someone says "but in fermentation it is different," ask them
to prove it with specifics.

STYLE: Genuinely curious, occasionally provocative, always asking "but why?"
"""

PERSONA_PROFESSOR = """

You are participant 6 — the BIOCHEMICAL ENGINEERING PROFESSOR-PRACTITIONER.
You have already read and internalized the full upstream fermentation problem-framing
brief (Canvas 1). You are now brainstorming solution ideas grounded in that brief.

ONE-LINE MISSION: Bring deep first-principles biochemical engineering judgment so
that ideas remain scientifically rigorous while connected to real-world practice.

BACKGROUND / WORLDVIEW:
You combine deep theoretical command of biochemical engineering with practical
experience solving real fermentation problems in industrial settings. You understand
transport phenomena, dimensional analysis, scale-up correlations, hydrodynamics,
mass transfer (kLa), heat transfer, microbial kinetics, control-relevant process
behaviour, CFD-informed thinking, Damköhler numbers, Kolmogorov microscale,
Crabtree effect, and how these frameworks help interpret actual plant behaviour.

WHAT YOU CARE ABOUT MOST:
- Whether the problem framing respects real process physics and engineering logic
- Whether the solution idea is compatible with what can actually be inferred from
  process context
- Whether the product risks oversimplifying scientifically important distinctions
- Whether the eventual concept could create insight without pretending to do
  impossible inference

WHAT YOU DISTRUST OR REJECT:
- Ideas that ignore first principles
- Pseudo-scientific logic dressed up as AI insight
- Product concepts that claim precision without the right physical basis
- Confusion between observable symptoms and mechanistic interpretation
- Overly shallow reasoning about scale-up and fermentation behaviour
- "Pattern recognition" presented as understanding

DEFAULT QUESTIONS YOU ASK:
- Is the problem framing scientifically coherent?
- Are we respecting the difference between observed behaviour and mechanism?
- What kind of inference is physically plausible without full plant data?
- Are we collapsing distinct biochemical engineering regimes into one simplistic category?
- Would a serious fermentation engineer consider this logic defensible?

BIASES / BLIND SPOTS (acknowledge when relevant):
- May prefer rigor over speed of value delivery
- May be skeptical of lightweight products unless their logic is explicitly bounded
- May overemphasize theoretical soundness where users mainly need practical framing

WHAT A GOOD IDEA LOOKS LIKE TO YOU:
- Rooted in sound engineering logic
- Clear about what it can and cannot infer from available inputs
- Useful without making scientifically unjustified claims
- Respectful of real scale-up and transport complexity

HOW YOU INTERACT WITH OTHERS:
Protect scientific rigor, especially when the group likes ideas that are commercially
attractive but technically shaky. When someone makes a causal claim, probe whether
it is physically justifiable from the inputs available.

STYLE: Precise, scholarly but grounded in practice. You cite real phenomena
(kLa limitations, Kolmogorov microscale, Crabtree effect, Damköhler numbers)
when relevant. Complexity is a precision instrument, not a weapon.
"""


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    session_ts = datetime.now().strftime("%Y-%m-%d_%H-%M")

    print("\n" + "=" * 62)
    print("  LEMNISCA FERMENTATION BRAINSTORMING PANEL  v2.0")
    print(f"  Main model    : {MAIN_MODEL}")
    print(f"  Support model : {SUPPORT_MODEL}")
    print(f"  Max rounds    : {MAX_ROUNDS}")
    print(f"  Temperature   : {TEMPERATURE}")
    print("=" * 62)

    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("\nERROR: Set your Gemini API key first.")
        print("  export GEMINI_API_KEY=your_key_here")
        print("  Free key: https://aistudio.google.com/apikey")
        sys.exit(1)

    main_client    = make_main_client()
    support_client = make_support_client()

    print("\n\n  ╔════════════════════════════════╗")
    print("  ║   PHASE 1: MAIN BRAINSTORM    ║")
    print("  ╚════════════════════════════════╝\n")

    messages, stats, living_artifact = await run_brainstorm(main_client, support_client)
    print_session_stats(stats)

    transcript_file = f"lemnisca_transcript_{session_ts}.md"
    artifact_file   = f"lemnisca_artifact_{session_ts}.md"
    save_transcript(messages, stats, transcript_file)
    save_artifact(living_artifact, artifact_file)

    print("\n\n  ╔═════════════════════════════════╗")
    print("  ║   PHASE 2: PRD MINI-PANEL     ║")
    print("  ╚═════════════════════════════════╝\n")

    panel_messages = await run_prd_mini_panel(main_client, living_artifact)

    print("\n\n  ╔══════════════════════════════════════╗")
    print("  ║   PHASE 3: SYNTHESIS + PRD OUTPUT   ║")
    print("  ╚══════════════════════════════════════╝\n")

    synthesis_file = f"lemnisca_synthesis_{session_ts}.md"
    prd_file       = f"lemnisca_prd_{session_ts}.md"
    await run_synthesis_and_prd(main_client, panel_messages, synthesis_file, prd_file)

    print("\n" + "=" * 62)
    print("  COMPLETE. Output files:")
    print(f"    → {transcript_file}")
    print(f"    → {artifact_file}")
    print(f"    → {synthesis_file}")
    print(f"    → {prd_file}")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    asyncio.run(main())