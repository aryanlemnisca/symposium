"""Stress test AI services — phase inference, re-interpret, agent suggestion."""

import json
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.clients import make_client

SUPPORT_MODEL = "gemini-2.5-flash"


async def _ask(system: str, prompt: str, api_key: str) -> str:
    client = make_client(model=SUPPORT_MODEL, api_key=api_key, temperature=0.3)
    agent = AssistantAgent(name="StressSuggester", system_message=system, model_client=client)
    response = await agent.on_messages(
        [TextMessage(content=prompt, source="user")], CancellationToken()
    )
    return response.chat_message.content if response and response.chat_message else ""


def _parse_json(raw: str):
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return None


async def analyse_documents(
    documents: list[dict],
    problem_statement: str,
    api_key: str,
) -> dict:
    """Propose phase breakdown + review instructions from documents."""
    system = (
        "You are an expert document reviewer designing a multi-phase stress-test review session. "
        "You sequence phases so dependency-heavy sections are reviewed before things that depend on them."
    )
    doc_summaries = "\n\n".join(
        f"[{d['filename']}] ({d['size_bytes']} bytes):\n{d['content_text']}"
        for d in documents
    )
    prompt = (
        f"You are analysing a set of documents that a user wants to stress-test using a multi-agent review board.\n\n"
        f"Problem statement:\n{problem_statement}\n\n"
        f"Documents uploaded:\n{doc_summaries}\n\n"
        f"Propose a logical phase breakdown for the review. Each phase should:\n"
        f"- Focus on a coherent subset of the documents\n"
        f"- Have a clear question to answer\n"
        f"- Be sequenced so earlier phases inform later ones\n"
        f"- Sequence dependency-heavy sections before things that depend on them\n"
        f"- Flag cross-document dependencies explicitly in subquestions\n"
        f"- Take approximately 20-30 rounds of agent debate to exhaust\n\n"
        f"For EACH phase, also design a specific ARTIFACT SCHEMA — the sections that the phase's "
        f"output document must contain. Different phases need different artifact formats:\n"
        f"- An alignment/charter phase needs: objective, scope, criteria, roles, rules\n"
        f"- A logic review phase needs: strengths (with evidence), weaknesses (with evidence), "
        f"challenged assumptions [accept|revise|reopen|defer], missing logic, next-step implication\n"
        f"- A consistency phase needs: contradiction table (issue, documents affected, severity, resolution)\n"
        f"- A final verdict phase needs: overall verdict, preserved strengths, issues to fix, locked decisions, revision brief\n"
        f"Design each phase's artifact schema to match what that specific phase is reviewing.\n\n"
        f"Also generate a REVIEW INSTRUCTIONS block specific to these documents.\n"
        f"What should every reviewer check for given this type of work product?\n"
        f"Include domain-specific checks (not generic quality checks).\n\n"
        f"Return JSON:\n"
        f'{{\n'
        f'  "phases": [\n'
        f'    {{\n'
        f'      "number": 1,\n'
        f'      "name": "short phase name",\n'
        f'      "document_ids": ["doc_id_1", "doc_id_2"],\n'
        f'      "focus_question": "the primary question this phase must answer",\n'
        f'      "key_subquestions": ["subquestion 1", "subquestion 2", "subquestion 3"],\n'
        f'      "artifact_schema": ["Section 1 heading", "Section 2 heading", "..."],\n'
        f'      "rationale": "why these documents and this question go together"\n'
        f'    }}\n'
        f'  ],\n'
        f'  "review_instructions": "full review instructions block tailored to these documents",\n'
        f'  "suggested_min_rounds_per_phase": 20\n'
        f'}}'
    )

    raw = await _ask(system, prompt, api_key)
    result = _parse_json(raw)
    if result and isinstance(result, dict) and "phases" in result:
        return result
    return {"phases": [], "review_instructions": "", "suggested_min_rounds_per_phase": 20}


async def reinterpret_phases(
    current_phases: list[dict],
    documents: list[dict],
    problem_statement: str,
    api_key: str,
) -> dict:
    """Re-interpret phases after user edits."""
    system = (
        "You are an expert document reviewer. The user has edited your proposed phase plan. "
        "Reinterpret and return an updated version that respects their edits while maintaining "
        "logical sequencing and dependency ordering."
    )
    doc_summaries = "\n\n".join(
        f"[{d['filename']}]: {d['content_text']}"
        for d in documents
    )
    phases_text = json.dumps(current_phases, indent=2)
    prompt = (
        f"Problem statement:\n{problem_statement}\n\n"
        f"Documents:\n{doc_summaries}\n\n"
        f"User's edited phase plan:\n{phases_text}\n\n"
        f"Reinterpret this plan. Return updated JSON with the same structure:\n"
        f'{{\n'
        f'  "phases": [...same structure as input...],\n'
        f'  "changes_explanation": "brief explanation of what you adjusted and why"\n'
        f'}}'
    )

    raw = await _ask(system, prompt, api_key)
    result = _parse_json(raw)
    if result and isinstance(result, dict) and "phases" in result:
        return result
    return {"phases": current_phases, "changes_explanation": "No changes made."}


async def suggest_stress_test_agents(
    documents: list[dict],
    phases: list[dict],
    problem_statement: str,
    api_key: str,
) -> list:
    """Suggest agents for stress test based on documents and phases."""
    system = (
        "You are designing a review board for a multi-agent stress-test session. "
        "Every panel MUST have: a domain expert, a logic challenger, an execution realist, "
        "and a scope guardian. Each agent has a 'lens' — what they specifically look for."
    )
    doc_summaries = "\n".join(f"- {d['filename']}: {d['content_text'][:1500]}" for d in documents)
    phases_text = "\n".join(
        f"- Phase {p.get('number', '?')}: {p.get('name', '?')} — {p.get('focus_question', '?')}"
        for p in phases
    )
    prompt = (
        f"Documents being reviewed:\n{doc_summaries}\n\n"
        f"Confirmed phases:\n{phases_text}\n\n"
        f"Problem statement:\n{problem_statement}\n\n"
        f"Suggest 4-6 agents. Each MUST have a distinct review lens.\n\n"
        f"Mandatory roles:\n"
        f"1. Domain expert — knows the subject matter\n"
        f"2. Logic challenger — finds contradictions, weak reasoning\n"
        f"3. Execution realist — challenges whether plans can actually be done\n"
        f"4. Scope guardian — checks if documents cover what they claim\n\n"
        f"Return JSON array:\n"
        f'[{{\n'
        f'  "name": "Agent_Name",\n'
        f'  "role_tag": "2-3 word label",\n'
        f'  "mission": "one sentence",\n'
        f'  "lens": "what this agent specifically looks for in documents",\n'
        f'  "persona": "full structured persona (200-400 words)",\n'
        f'  "model": "gemini-3.1-pro-preview",\n'
        f'  "rationale": "why this agent creates productive tension"\n'
        f'}}]'
    )

    raw = await _ask(system, prompt, api_key)
    result = _parse_json(raw)
    if result and isinstance(result, list):
        return result
    return []
