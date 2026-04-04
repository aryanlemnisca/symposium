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
        f"Return JSON. EVERY phase MUST include artifact_schema — this is NOT optional:\n"
        f'{{\n'
        f'  "phases": [\n'
        f'    {{\n'
        f'      "number": 1,\n'
        f'      "name": "short phase name",\n'
        f'      "document_ids": ["doc_id_1", "doc_id_2"],\n'
        f'      "focus_question": "the primary question this phase must answer",\n'
        f'      "key_subquestions": ["subquestion 1", "subquestion 2", "subquestion 3"],\n'
        f'      "artifact_schema": [\n'
        f'        "Section heading 1 — e.g. Strengths found (with document evidence)",\n'
        f'        "Section heading 2 — e.g. Weaknesses found (with document evidence)",\n'
        f'        "Section heading 3 — e.g. Challenged assumptions [accept|revise|reopen|defer]",\n'
        f'        "Section heading 4",\n'
        f'        "Section heading 5"\n'
        f'      ],\n'
        f'      "rationale": "why these documents and this question go together"\n'
        f'    }}\n'
        f'  ],\n'
        f'  "review_instructions": "full review instructions block tailored to these documents",\n'
        f'  "suggested_min_rounds_per_phase": 20\n'
        f'}}\n\n'
        f"CRITICAL: artifact_schema must be an array of 4-6 strings per phase. Each string is a section heading.\n"
        f"Different phases need DIFFERENT schemas. Do NOT use the same schema for every phase.\n"
        f"The first phase should be an alignment/charter artifact. Middle phases should be review memos. The final phase should be a verdict."
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
        "You are an expert at designing review boards for structured document stress-test sessions. "
        "Your job is to read the documents and problem statement, identify what DOMAIN this is, "
        "then design agents whose expertise matches that domain.\n\n"
        "You are NOT limited to any specific field. You must adapt to whatever the documents are about — "
        "biotech roadmaps, financial models, research papers, product specs, policy documents, "
        "engineering designs, strategy packs, or anything else.\n\n"
        "Your design process:\n"
        "1. Read the documents and identify the DOMAIN (what field, what type of work product)\n"
        "2. Identify what EXPERTISE is needed to genuinely stress-test these documents\n"
        "3. Design agents whose knowledge would be required on a real review board for this type of work\n"
        "4. Ensure agents create PRODUCTIVE TENSION — they must disagree on priorities and catch each other's blind spots\n"
        "5. Always include a Red-Team Skeptic whose job is to find contradictions, hidden assumptions, and overconfidence"
    )
    doc_summaries = "\n".join(f"- {d['filename']}: {d['content_text'][:1500]}" for d in documents)
    phases_text = "\n".join(
        f"- Phase {p.get('number', '?')}: {p.get('name', '?')} — {p.get('focus_question', '?')}"
        for p in phases
    )
    prompt = (
        f"Documents being reviewed:\n{doc_summaries}\n\n"
        f"Confirmed review phases:\n{phases_text}\n\n"
        f"Problem statement:\n{problem_statement}\n\n"
        f"Design 5-7 review agents for this stress-test board.\n\n"
        f"MANDATORY STRUCTURE for every board (adapt the specific expertise to the domain):\n\n"
        f"1. DOMAIN EXPERT AGENTS (2-3 agents)\n"
        f"   Each must cover a distinct technical area relevant to the documents.\n"
        f"   Their expertise must be specific to this domain — not generic.\n"
        f"   Example: for a biotech roadmap, you'd want a strain engineering expert, "
        f"a bioprocess expert, and an analytics expert — NOT generic 'Science Reviewer'.\n"
        f"   Example: for a financial model, you'd want a unit economics expert, "
        f"a market sizing expert, and a risk modeling expert.\n\n"
        f"2. STRATEGY / SCOPE REVIEWER (1 agent)\n"
        f"   Checks whether the work is focused on the right things, whether scope is defensible, "
        f"whether trade-offs are explicit.\n\n"
        f"3. EXECUTION / OPERATIONS REVIEWER (1 agent)\n"
        f"   Checks whether what's written can actually be done — timelines, resources, "
        f"dependencies, operational realism.\n\n"
        f"4. RED-TEAM SKEPTIC (1 agent, ALWAYS required)\n"
        f"   Assumes the documents are too optimistic. Finds contradictions, hidden assumptions, "
        f"circular logic, weak gates, missing risks. Attacks overconfidence.\n\n"
        f"Each agent MUST have:\n"
        f"- A name that reflects their specific expertise (e.g. 'Scale_Up_Reviewer' not 'Reviewer_2')\n"
        f"- A lens: what specifically they look for in documents\n"
        f"- A bias: what they are naturally skeptical of\n"
        f"- Distrust patterns: what specific failure modes they watch for\n\n"
        f"Each agent's full persona MUST follow this structure:\n\n"
        f"You are [Agent_Name] — the [TITLE].\n\n"
        f"ONE-LINE MISSION: [what this agent exists to do in this review]\n\n"
        f"REVIEW LENS: [what this agent specifically looks for in the documents]\n\n"
        f"BACKGROUND: [2-3 sentences — specific expertise that qualifies them for this review]\n\n"
        f"WHAT YOU CARE ABOUT MOST:\n- [4-5 bullet points specific to this review]\n\n"
        f"WHAT YOU DISTRUST OR REJECT:\n- [4-5 bullet points — specific failure modes in these documents]\n\n"
        f"DEFAULT QUESTIONS YOU ASK:\n- [4-5 questions only this agent would ask about these documents]\n\n"
        f"BIASES / BLIND SPOTS:\n- [2-3 honest limitations of this agent's worldview]\n\n"
        f"HOW YOU INTERACT WITH OTHERS:\n[2-3 sentences — specific behaviours, aggression level]\n\n"
        f"STYLE: [1-2 sentences — voice, tone]\n\n"
        f"IMPORTANT:\n"
        f"- Agents must refer to each other by NAME, never by number.\n"
        f"- Agent names must be SIMPLE and descriptive: Role_Noun format.\n"
        f"  GOOD: Strain_Reviewer, Process_Lead, Analytics_Reviewer, Strategy_Lead, Ops_Reviewer, Red_Team\n"
        f"  BAD: Dr_Genevieve_Strain, Professor_Ben_Carter, Dr_Doubt_Fire, Ms_Vision_Scope\n"
        f"  No titles (Dr, Prof, Mr, Ms), no clever wordplay, no character names.\n\n"
        f"Return JSON array:\n"
        f'[{{\n'
        f'  "name": "Simple_Role_Name (e.g. Strain_Reviewer, Process_Lead, Red_Team — short, clear, no fancy names like Dr_Doubt_Fire)",\n'
        f'  "role_tag": "2-3 word label",\n'
        f'  "mission": "one sentence",\n'
        f'  "lens": "what this agent specifically looks for in the documents",\n'
        f'  "persona": "FULL persona following the structure above (300-500 words)",\n'
        f'  "model": "gemini-3.1-pro-preview",\n'
        f'  "rationale": "why this agent creates productive tension on THIS specific review board"\n'
        f'}}]'
    )

    raw = await _ask(system, prompt, api_key)
    result = _parse_json(raw)
    if result and isinstance(result, list):
        return result
    return []
