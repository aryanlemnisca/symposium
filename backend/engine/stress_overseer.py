"""StressOverseer — stateful phase controller for stress test sessions."""

import asyncio
import json
from typing import Optional
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken


_SUB_PHASES = [
    (0.20, "Comprehend", "Read the phase documents. State what each document claims. Identify key assertions. No challenges yet."),
    (0.45, "Challenge", "Poke holes. Find weak logic, unsupported claims, missing evidence, contradictions. Be adversarial."),
    (0.65, "Cross-examine", "Respond to challenges raised. Defend or concede specific points. Force resolution per claim."),
    (0.85, "Synthesize", "Build the confirmed/contested/open list. What is sound? What is not?"),
    (1.00, "Conclude", "Final positions. Each agent states their verdict on the focus question. No new challenges — commit."),
]

_PHASE_DIRECTIVE_TEMPLATE = """\
[PHASE {number} NOW ACTIVE]

Focus: {name}
Primary question: {focus_question}

Key questions to resolve this phase:
{subquestions}

{carry_forward_text}

Do not re-open confirmed items unless you find a direct contradiction
in the current phase documents. Stay focused on Phase {number}.\
"""

_DRIFT_CHECK_PROMPT = """\
You are monitoring a stress-test review session.

Current phase: {phase_name}
Focus question: {focus_question}
Current sub-phase: {sub_phase} — {sub_phase_directive}

Last 5 agent messages:
{recent_messages}

Is the discussion on track for the current sub-phase?
If agents are drifting off the focus question or doing the wrong thing for this sub-phase
(e.g. challenging during Comprehend, or raising new issues during Conclude):
→ Return a one-sentence redirect.

If on track:
→ Return exactly: ON_TRACK

Return only the redirect sentence or ON_TRACK. Nothing else.\
"""

_PHASE_EVAL_PROMPT = """\
You are evaluating phase progress in a stress-test review session.

Current phase: {phase_name}
Focus question: {focus_question}
Key subquestions: {subquestions}
Rounds completed this phase: {round_count}
Minimum required: {min_rounds}

Recent messages (last 10):
{recent_messages}

Evaluate:
1. Has the focus question been substantially answered? (yes/partial/no)
2. Which subquestions are resolved? Which are still open?
3. Is the discussion still generating new insights or repeating?
4. Has minimum round count been reached? (yes/no)

If all subquestions are addressed AND minimum rounds reached AND discussion is repeating:
→ Return action: "suggest_advance"

Otherwise:
→ Return action: "continue"

Return JSON:
{{
  "action": "suggest_advance" or "continue",
  "confirmed": ["item 1", "item 2"],
  "contested": ["item 1"],
  "open_questions": ["question 1"],
  "continue_reason": "what still needs debate (if continue)",
  "summary": "2-3 sentence summary of phase findings (if suggest_advance)"
}}\
"""

_PHASE_ARTIFACT_PROMPT = """\
Write the Phase {number} review artifact for a stress-test session.

Phase name: {name}
Documents reviewed: {docs}
Focus question: {focus_question}

Agent discussion (full phase):
{phase_messages}

Produce the artifact in this exact format:

PHASE {number} — {name}
Documents reviewed: {docs}
Rounds: {start_round} to {end_round}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONFIRMED SOUND
[Each item: specific claim · why confirmed · which agents agreed]

CONTESTED
[Each item: specific claim · what the objection is · who raised it · not yet resolved]

MUST FIX BEFORE NEXT PHASE
[Blocking issues that must be resolved before the session can credibly proceed]

OPEN QUESTIONS
[Specific questions that emerged · why they matter · what answering them would change]

CROSS-DOCUMENT CONTRADICTIONS FOUND
[Any place where one document's claims conflict with another]

Be specific — name documents, name agents, quote specific claims. No vague summaries.\
"""

_FINAL_VERDICT_PROMPT = """\
You are producing the final readiness verdict for a stress-test review session.

The following phase artifacts were produced during the session:
{all_phase_artifacts}

Produce the final verdict in this exact format:

STRESS TEST — FINAL READINESS VERDICT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OVERALL VERDICT
READY / NOT READY / CONDITIONALLY READY

[One paragraph explaining the verdict]

BLOCKING ISSUES
[Must be resolved before the next step — specific, actionable]
· [issue]: [what must change]

NON-BLOCKING ISSUES
[Should be addressed but do not block progress]
· [issue]: [recommendation]

CONFIRMED SOUND — DO NOT REVISIT
[Items that survived stress-testing across all phases]
· [item]

CROSS-PHASE CONTRADICTIONS
[Places where findings in one phase conflict with another]
· [contradiction]: [which phases · what the conflict is]

RECOMMENDED FIRST ACTION
[The single most important thing to do before proceeding]

Be direct. Do not hedge. This verdict will be used to make a real decision.\
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


class StressOverseer:
    def __init__(
        self,
        support_agent: AssistantAgent,
        phases: list[dict],
        documents: list[dict],
        min_rounds_per_phase: int,
        agent_names: list[str],
    ):
        self.support_agent = support_agent
        self.phases = phases
        self.documents = documents
        self.min_rounds_per_phase = min_rounds_per_phase
        self.agent_names = agent_names
        self.phase_round_counts: dict[int, int] = {i: 0 for i in range(len(phases))}
        self.carry_forward: dict[str, list[str]] = {
            "confirmed": [],
            "contested": [],
            "open_questions": [],
        }

    def get_sub_phase(self, phase_round_count: int) -> tuple[str, str]:
        """Return (sub_phase_name, sub_phase_directive) based on progress."""
        pct = phase_round_count / max(self.min_rounds_per_phase, 1)
        for threshold, name, directive in _SUB_PHASES:
            if pct <= threshold:
                return name, directive
        return _SUB_PHASES[-1][1], _SUB_PHASES[-1][2]

    def get_selector_context(self, phase_index: int) -> dict:
        """Build stress_context dict for the phase-aware selector."""
        phase = self.phases[phase_index]
        phase_round_count = self.phase_round_counts.get(phase_index, 0)
        sub_phase, sub_directive = self.get_sub_phase(phase_round_count)
        return {
            "phase_name": phase["name"],
            "focus_question": phase.get("focus_question", ""),
            "sub_phase": sub_phase,
            "sub_phase_directive": sub_directive,
        }

    def generate_phase_directive(self, phase_index: int) -> TextMessage:
        """Build the [PHASE N NOW ACTIVE] message."""
        phase = self.phases[phase_index]
        subquestions = "\n".join(f"· {q}" for q in phase.get("key_subquestions", []))

        carry_parts = []
        if self.carry_forward["confirmed"]:
            carry_parts.append("Carried forward from previous phases:")
            carry_parts.append("CONFIRMED: " + "; ".join(self.carry_forward["confirmed"]))
        if self.carry_forward["contested"]:
            carry_parts.append("CONTESTED: " + "; ".join(self.carry_forward["contested"]))
        carry_forward_text = "\n".join(carry_parts) if carry_parts else ""

        content = _PHASE_DIRECTIVE_TEMPLATE.format(
            number=phase["number"],
            name=phase["name"],
            focus_question=phase.get("focus_question", ""),
            subquestions=subquestions,
            carry_forward_text=carry_forward_text,
        )
        return TextMessage(content=content, source="Overseer")

    def check_keyword_drift(self, phase_index: int, messages: list) -> Optional[TextMessage]:
        """Zero-cost keyword drift check. Returns redirect or None."""
        phase = self.phases[phase_index]
        focus_words = set()
        for word in phase.get("focus_question", "").lower().split():
            if len(word) > 3:
                focus_words.add(word)
        for sq in phase.get("key_subquestions", []):
            for word in sq.lower().split():
                if len(word) > 3:
                    focus_words.add(word)

        if not focus_words:
            return None

        recent = [
            m for m in messages[-5:]
            if getattr(m, "source", "") in self.agent_names
        ][-3:]

        if not recent:
            return None

        for m in recent:
            content_lower = getattr(m, "content", "").lower()
            if any(w in content_lower for w in focus_words):
                return None  # On track

        return TextMessage(
            content=f"[OVERSEER] Stay focused on: {phase.get('focus_question', '')}",
            source="Overseer",
        )

    async def check_drift(self, phase_index: int, messages: list, round_num: int) -> Optional[TextMessage]:
        """LLM drift check (Flash call). Returns redirect or None."""
        phase = self.phases[phase_index]
        phase_round_count = self.phase_round_counts.get(phase_index, 0)
        sub_phase, sub_directive = self.get_sub_phase(phase_round_count)

        recent = [
            m for m in messages[-8:]
            if getattr(m, "source", "") in self.agent_names
        ][-5:]
        recent_text = "\n".join(
            f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:200]}"
            for m in recent
        )

        prompt = _DRIFT_CHECK_PROMPT.format(
            phase_name=phase["name"],
            focus_question=phase.get("focus_question", ""),
            sub_phase=sub_phase,
            sub_phase_directive=sub_directive,
            recent_messages=recent_text,
        )

        async def _call():
            return await self.support_agent.on_messages(
                [TextMessage(content=prompt, source="system")], CancellationToken()
            )

        response = await _call_with_retry(_call, label="drift_check")
        if response and response.chat_message:
            content = response.chat_message.content.strip()
            if content != "ON_TRACK" and content:
                return TextMessage(content=f"[OVERSEER] {content}", source="Overseer")
        return None

    async def evaluate_phase(self, phase_index: int, messages: list, round_num: int) -> dict:
        """Full phase evaluation every 5 rounds."""
        phase = self.phases[phase_index]
        phase_round_count = self.phase_round_counts.get(phase_index, 0)

        recent = [
            m for m in messages[-15:]
            if getattr(m, "source", "") in self.agent_names
            or getattr(m, "source", "") == "Overseer"
        ][-10:]
        recent_text = "\n".join(
            f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:300]}"
            for m in recent
        )
        subquestions = "\n".join(f"· {q}" for q in phase.get("key_subquestions", []))

        prompt = _PHASE_EVAL_PROMPT.format(
            phase_name=phase["name"],
            focus_question=phase.get("focus_question", ""),
            subquestions=subquestions,
            round_count=phase_round_count,
            min_rounds=self.min_rounds_per_phase,
            recent_messages=recent_text,
        )

        async def _call():
            return await self.support_agent.on_messages(
                [TextMessage(content=prompt, source="system")], CancellationToken()
            )

        response = await _call_with_retry(_call, label="phase_eval")
        if response and response.chat_message:
            parsed = _parse_json_safe(response.chat_message.content)
            if parsed:
                # Enforce minimum rounds
                if phase_round_count < self.min_rounds_per_phase:
                    parsed["action"] = "continue"
                    parsed["continue_reason"] = f"Minimum rounds ({self.min_rounds_per_phase}) not reached ({phase_round_count})"
                return parsed

        return {
            "action": "continue",
            "confirmed": [],
            "contested": [],
            "open_questions": [],
            "continue_reason": "Evaluation failed, continuing",
            "summary": "",
        }

    async def write_phase_artifact(self, phase_index: int, messages: list) -> str:
        """Write structured artifact when phase closes."""
        phase = self.phases[phase_index]
        phase_msgs = [
            m for m in messages
            if getattr(m, "source", "") in self.agent_names
            or getattr(m, "source", "") == "Overseer"
        ]
        phase_text = "\n\n".join(
            f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:500]}"
            for m in phase_msgs[-40:]
        )
        doc_names = []
        for doc in self.documents:
            if doc.get("id") in phase.get("document_ids", []):
                doc_names.append(doc["filename"])

        prompt = _PHASE_ARTIFACT_PROMPT.format(
            number=phase["number"],
            name=phase["name"],
            docs=", ".join(doc_names) or "All documents",
            focus_question=phase.get("focus_question", ""),
            phase_messages=phase_text,
            start_round=phase.get("start_round", "?"),
            end_round=phase.get("end_round", "?"),
        )

        async def _call():
            return await self.support_agent.on_messages(
                [TextMessage(content=prompt, source="system")], CancellationToken()
            )

        response = await _call_with_retry(_call, label=f"artifact_p{phase['number']}")
        artifact = ""
        if response and response.chat_message:
            artifact = response.chat_message.content

        # Update carry-forward
        eval_result = await self.evaluate_phase(phase_index, messages, 0)
        self.carry_forward["confirmed"].extend(eval_result.get("confirmed", []))
        self.carry_forward["contested"].extend(eval_result.get("contested", []))
        self.carry_forward["open_questions"].extend(eval_result.get("open_questions", []))

        return artifact

    def evaluate_session_close(self, total_rounds: int) -> bool:
        """Check if all phases complete and min total rounds reached."""
        min_total = len(self.phases) * self.min_rounds_per_phase
        all_complete = all(
            p.get("status") == "complete" for p in self.phases
        )
        return all_complete and total_rounds >= min_total

    async def generate_final_verdict(self) -> str:
        """Generate final readiness verdict from all phase artifacts."""
        all_artifacts = "\n\n---\n\n".join(
            p.get("artifact", "No artifact") for p in self.phases if p.get("artifact")
        )
        prompt = _FINAL_VERDICT_PROMPT.format(all_phase_artifacts=all_artifacts)

        async def _call():
            return await self.support_agent.on_messages(
                [TextMessage(content=prompt, source="system")], CancellationToken()
            )

        response = await _call_with_retry(_call, label="final_verdict")
        if response and response.chat_message:
            return response.chat_message.content
        return "Verdict generation failed."


def _parse_json_safe(raw: str):
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except Exception:
        return None
