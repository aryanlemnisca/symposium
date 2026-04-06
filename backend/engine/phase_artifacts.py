"""Phase artifact generation — structured per-phase output for all brainstorm modes."""

import asyncio
from typing import Optional
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken


_PHASE_ARTIFACT_PROMPT = """\
Write the Phase {number} review artifact for this brainstorm session.

Phase name: {name}
Focus question: {focus_question}
Rounds: {start_round} to {end_round}

Agent discussion (full phase):
{phase_messages}

{carry_forward_section}

{document_section}

Produce the artifact using this EXACT structure:

## Phase {number}: {name}

### Confirmed
- [item] — [evidence from discussion] — [accept]

### Contested
- [claim] — [objection] — [who raised it] — [status: accept|revise|reopen|defer]

### Must Address
- [blocking issues requiring resolution before proceeding]

### Open Questions
- [specific question] — [why it matters]

### Cross-Phase Carry-Forward
- [items from previous phases that were revisited or affected]

{cross_doc_section}

RULES:
- Be specific — name agents, quote specific claims and arguments
- No vague summaries
- Every finding must cite evidence from the discussion
- Tag each finding with a decision status: [accept] [revise] [reopen] [defer]
- The artifact must be decision-useful — a reader who wasn't in the session must \
know exactly what was found and what must change\
"""

_CROSS_DOC_SECTION = """\
### Cross-Document Contradictions
- [contradiction between documents] — [which documents] — [what the conflict is] — [status]\
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


async def generate_phase_artifact(
    support_agent: AssistantAgent,
    phase: dict,
    phase_messages: list,
    agent_names: list[str],
    carry_forward: Optional[dict] = None,
    documents: Optional[list[dict]] = None,
) -> str:
    """Generate a structured per-phase artifact from the discussion.

    Args:
        support_agent: LLM agent used for generation.
        phase: Phase dict with keys like number, name, focus_question, start_round, end_round.
        phase_messages: Messages from this phase's discussion.
        agent_names: Names of all participating agents.
        carry_forward: Optional dict with confirmed/contested/open_questions from prior phases.
        documents: Optional list of document dicts (stress test mode only).

    Returns:
        Markdown-formatted artifact string.
    """
    # Build phase discussion text (last 40 messages, truncated)
    relevant_msgs = [
        m for m in phase_messages
        if getattr(m, "source", "") in agent_names
        or getattr(m, "source", "") == "Overseer"
    ]
    phase_text = "\n\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:500]}"
        for m in relevant_msgs[-40:]
    )

    # Carry-forward section
    carry_forward_section = ""
    if carry_forward:
        parts = []
        if carry_forward.get("confirmed"):
            parts.append("Previously confirmed: " + "; ".join(carry_forward["confirmed"]))
        if carry_forward.get("contested"):
            parts.append("Previously contested: " + "; ".join(carry_forward["contested"]))
        if carry_forward.get("open_questions"):
            parts.append("Previously open: " + "; ".join(carry_forward["open_questions"]))
        if parts:
            carry_forward_section = "CARRY-FORWARD FROM PREVIOUS PHASES:\n" + "\n".join(parts)

    # Document section (stress test only)
    document_section = ""
    if documents:
        doc_names = []
        phase_doc_ids = phase.get("document_ids", [])
        for doc in documents:
            if not phase_doc_ids or doc.get("id") in phase_doc_ids:
                doc_names.append(doc.get("filename", "unknown"))
        if doc_names:
            document_section = f"Documents reviewed: {', '.join(doc_names)}"

    # Cross-document contradictions section (stress test only)
    cross_doc_section = _CROSS_DOC_SECTION if documents else ""

    prompt = _PHASE_ARTIFACT_PROMPT.format(
        number=phase.get("number", "?"),
        name=phase.get("name", "?"),
        focus_question=phase.get("focus_question", ""),
        start_round=phase.get("start_round", "?"),
        end_round=phase.get("end_round", "?"),
        phase_messages=phase_text,
        carry_forward_section=carry_forward_section,
        document_section=document_section,
        cross_doc_section=cross_doc_section,
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(
        _call, label=f"artifact_p{phase.get('number', '?')}"
    )
    if response and response.chat_message:
        return response.chat_message.content
    return f"## Phase {phase.get('number', '?')}: {phase.get('name', '?')}\n\n_Artifact generation failed._"
