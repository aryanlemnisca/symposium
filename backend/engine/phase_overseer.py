"""PhaseOverseer — generalized phase controller for all brainstorm modes."""

import asyncio
import json
from typing import Optional
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.phase_artifacts import generate_phase_artifact


_SUB_PHASES = [
    (0.20, "Comprehend", "Read and state assertions from the material. Identify key claims. No challenges yet."),
    (0.45, "Challenge", "Poke holes — ask hard questions, flag gaps, find weak logic and unsupported claims."),
    (0.65, "Cross-examine", "Defend or concede points raised. Cite evidence. Force resolution per claim."),
    (0.85, "Synthesize", "Build the confirmed / contested / open-question list. What is sound? What is not?"),
    (1.00, "Conclude", "Lock final positions. Each agent states their verdict. No new challenges — commit."),
]

_PHASE_DIRECTIVE_TEMPLATE = """\
[PHASE {number} NOW ACTIVE]

Focus: {name}
Primary question: {focus_question}

Key questions to resolve this phase:
{subquestions}

THIS PHASE MUST PRODUCE AN ARTIFACT WITH THESE SECTIONS:
{artifact_schema_text}

Every contribution should work toward populating one of these sections.
During Comprehend: gather evidence for each section.
During Challenge: test claims that will go into each section.
During Synthesize: draft positions for each section.
During Conclude: finalize each section with explicit decisions [accept | revise | reopen | defer].

{carry_forward_text}

{document_context}

Do not re-open confirmed items unless you find a direct contradiction. \
Stay focused on Phase {number}.\
"""

_DRIFT_CHECK_PROMPT = """\
You are monitoring a brainstorm review session.

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
You are evaluating phase progress in a brainstorm session.

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


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    """Retry an async callable with exponential backoff."""
    import logging
    logger = logging.getLogger("symposium")
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            logger.warning(f"[{label}] attempt {attempt+1}/{max_retries+1} failed: {e}")
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    logger.error(f"[{label}] all {max_retries+1} attempts failed")
    return None


def _parse_json_safe(raw: str) -> Optional[dict]:
    """Extract and parse JSON from LLM output that may contain markdown fences."""
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except Exception:
        return None


class PhaseOverseer:
    """Generalized phase controller for product, problem, and stress test modes.

    Unlike StressOverseer, this class does not assume documents exist.
    Document context is only included when explicitly provided.
    """

    def __init__(
        self,
        support_agent: AssistantAgent,
        phases: list[dict],
        agent_names: list[str],
        documents: Optional[list[dict]] = None,
        min_rounds_per_phase: int = 10,
    ):
        self.support_agent = support_agent
        self.phases = phases
        self.agent_names = agent_names
        self.documents = documents
        self.min_rounds_per_phase = min_rounds_per_phase
        self.phase_round_counts: dict[int, int] = {i: 0 for i in range(len(phases))}
        self.carry_forward: dict[str, list[str]] = {
            "confirmed": [],
            "contested": [],
            "open_questions": [],
        }

    def get_sub_phase(self, phase_round_count: int) -> tuple[str, str]:
        """Return (sub_phase_name, sub_phase_directive) based on progress percentage."""
        pct = phase_round_count / max(self.min_rounds_per_phase, 1)
        for threshold, name, directive in _SUB_PHASES:
            if pct <= threshold:
                return name, directive
        return _SUB_PHASES[-1][1], _SUB_PHASES[-1][2]

    def get_selector_context(self, phase_index: int) -> dict:
        """Build context dict for the hybrid selector."""
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
        """Build the [PHASE N NOW ACTIVE] directive message."""
        phase = self.phases[phase_index]
        subquestions = "\n".join(
            f"· {q}" for q in phase.get("key_subquestions", [])
        )

        artifact_schema = phase.get("artifact_schema", [])
        if artifact_schema:
            artifact_schema_text = "\n".join(
                f"  {i+1}. {s}" for i, s in enumerate(artifact_schema)
            )
        else:
            artifact_schema_text = (
                "  (Use standard format: Confirmed / Contested / Open Questions)"
            )

        # Carry-forward from previous phases
        carry_parts = []
        if self.carry_forward["confirmed"]:
            carry_parts.append(
                "Carried forward from previous phases:"
            )
            carry_parts.append(
                "CONFIRMED: " + "; ".join(self.carry_forward["confirmed"])
            )
        if self.carry_forward["contested"]:
            carry_parts.append(
                "CONTESTED: " + "; ".join(self.carry_forward["contested"])
            )
        carry_forward_text = "\n".join(carry_parts) if carry_parts else ""

        # Document context (only for stress test / document-based modes)
        document_context = ""
        if self.documents:
            phase_doc_ids = phase.get("document_ids", [])
            doc_names = []
            for doc in self.documents:
                if not phase_doc_ids or doc.get("id") in phase_doc_ids:
                    doc_names.append(doc.get("filename", "unknown"))
            if doc_names:
                document_context = (
                    f"Documents in scope for this phase: {', '.join(doc_names)}\n"
                    "Reference the documents by name when citing evidence."
                )

        content = _PHASE_DIRECTIVE_TEMPLATE.format(
            number=phase["number"],
            name=phase["name"],
            focus_question=phase.get("focus_question", ""),
            subquestions=subquestions,
            artifact_schema_text=artifact_schema_text,
            carry_forward_text=carry_forward_text,
            document_context=document_context,
        )
        return TextMessage(content=content, source="Overseer")

    def check_keyword_drift(
        self, phase_index: int, messages: list
    ) -> Optional[TextMessage]:
        """Zero-cost keyword drift check using phase focus keywords.

        Returns a redirect TextMessage if the last 3 agent messages contain
        none of the focus keywords, or None if on track.
        """
        phase = self.phases[phase_index]

        # Build keyword set from focus question and subquestions
        focus_words: set[str] = set()
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

    async def check_drift(
        self, phase_index: int, messages: list, round_num: int
    ) -> Optional[TextMessage]:
        """LLM drift check. Returns a redirect TextMessage or None if on track."""
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
                return TextMessage(
                    content=f"[OVERSEER] {content}", source="Overseer"
                )
        return None

    async def evaluate_phase(
        self, phase_index: int, messages: list, round_num: int
    ) -> dict:
        """Full phase evaluation. Returns action dict with confirmed/contested/open items."""
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
        subquestions = "\n".join(
            f"· {q}" for q in phase.get("key_subquestions", [])
        )

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
                # Enforce minimum rounds only on critical phases
                is_critical = phase.get("critical", False)
                if is_critical and phase_round_count < self.min_rounds_per_phase:
                    parsed["action"] = "continue"
                    parsed["continue_reason"] = (
                        f"Minimum rounds ({self.min_rounds_per_phase}) "
                        f"not reached ({phase_round_count})"
                    )
                return parsed

        return {
            "action": "continue",
            "confirmed": [],
            "contested": [],
            "open_questions": [],
            "continue_reason": "Evaluation failed, continuing",
            "summary": "",
        }

    async def write_phase_artifact(
        self, phase_index: int, messages: list
    ) -> str:
        """Write structured artifact when phase closes and update carry-forward."""
        phase = self.phases[phase_index]

        artifact = await generate_phase_artifact(
            support_agent=self.support_agent,
            phase=phase,
            phase_messages=messages,
            agent_names=self.agent_names,
            carry_forward=self.carry_forward if self.carry_forward["confirmed"] or self.carry_forward["contested"] else None,
            documents=self.documents,
        )

        # Update carry-forward state
        eval_result = await self.evaluate_phase(phase_index, messages, 0)
        self.carry_forward["confirmed"].extend(eval_result.get("confirmed", []))
        self.carry_forward["contested"].extend(eval_result.get("contested", []))
        self.carry_forward["open_questions"].extend(
            eval_result.get("open_questions", [])
        )

        return artifact
