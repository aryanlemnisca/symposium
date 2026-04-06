"""AI suggestion service — problem statement + persona review + agent suggestions."""

import os
import json
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.clients import make_client

SUPPORT_MODEL = "gemini-2.5-flash"

_PERSONA_STRUCTURE = """\
The persona MUST follow this exact structure (ALL sections mandatory):

You are [AGENT_NAME] — the [TITLE IN CAPS].
You have already read and internalized the problem statement. You are now brainstorming
solution ideas grounded in that brief.

IMPORTANT: Never refer to other agents by number. Always use their NAME when addressing
or referencing other agents.

ONE-LINE MISSION: [single sentence — what this agent exists to do]

BACKGROUND / WORLDVIEW:
[2-4 sentences. Must be specific enough to generate distinctive outputs.
 Must NOT be generic like "experienced professional".]

WHAT YOU CARE ABOUT MOST:
- [4-6 bullet points. Each must be specific and testable.
   No generic values like "impact" or "quality" alone.]

WHAT YOU DISTRUST OR REJECT:
- [4-6 bullet points. Each must name a specific failure mode, not a vague category.
   At least one must name something other agents on the panel might propose.]

DEFAULT QUESTIONS YOU ASK:
- [4-6 questions. Each specific enough that only THIS agent would ask it.
   At least one scenario question ("what happens when...").
   At least one that challenges a metric or measurement assumption.]

BIASES / BLIND SPOTS (acknowledge when relevant):
- [2-4 bullet points. Must be honest, not flattering.
   Must be plausible failures of this specific worldview.]

WHAT A GOOD IDEA LOOKS LIKE TO YOU:
- [3-5 bullet points. Specific to this persona's lens.
   Another agent should be able to predict what this agent will champion.]

WHAT A BAD IDEA LOOKS LIKE TO YOU:
- [3-5 bullet points. MANDATORY — often missing.
   Must name specific failure modes this agent will call out.
   Should create productive tension with at least one other agent.]

HOW YOU INTERACT WITH OTHERS:
[3-5 sentences. Must describe specific behaviours — what triggers this agent to speak,
 what they do when challenged. Must specify aggression level.
 Must NOT say "I seek to redirect" or "I aim to balance" — these are passive and useless.]

STYLE: [2-3 sentences. Tone, register, speech patterns.
 One specific verbal habit or signature phrase.]"""


async def _ask(system: str, user_prompt: str, api_key: str) -> str:
    client = make_client(model=SUPPORT_MODEL, api_key=api_key, temperature=0.3)
    agent = AssistantAgent(name="Suggester", system_message=system, model_client=client)
    response = await agent.on_messages(
        [TextMessage(content=user_prompt, source="user")], CancellationToken()
    )
    return response.chat_message.content if response and response.chat_message else ""


def _parse_json(raw: str) -> dict | list | None:
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return None


async def review_stress_test_problem(text: str, api_key: str) -> dict:
    """Review and enhance a stress test problem statement."""
    system = (
        "You are an expert at designing document stress-test review sessions. "
        "A good stress test problem statement must clearly define: what documents are being reviewed, "
        "what decision the review supports, what a good review outcome looks like, "
        "what is out of scope, and the specific questions the review must answer."
    )
    prompt = (
        f'Review and enhance this stress test problem statement:\n\n'
        f'"{text}"\n\n'
        f'Return JSON:\n'
        f'{{\n'
        f'  "clarity": "Low|Medium|High",\n'
        f'  "clarity_reason": "one sentence",\n'
        f'  "missing": ["list of missing elements — e.g. review questions, scope boundaries, success criteria"],\n'
        f'  "suggestions": ["2-3 specific improvements"],\n'
        f'  "rewrite": "Enhanced version that:\\n'
        f'    - Preserves the user\'s original intent\\n'
        f'    - Clearly states WHAT is being reviewed (the documents/work product)\\n'
        f'    - States WHAT DECISION this review supports\\n'
        f'    - Lists the SPECIFIC QUESTIONS the review must answer\\n'
        f'    - Defines WHAT A GOOD OUTCOME looks like\\n'
        f'    - States WHAT IS OUT OF SCOPE\\n'
        f'    - Uses structured formatting"\n'
        f'}}'
    )
    raw = await _ask(system, prompt, api_key)
    result = _parse_json(raw)
    if result and isinstance(result, dict):
        return result
    return {"clarity": "Unknown", "clarity_reason": raw, "missing": [], "suggestions": [], "rewrite": ""}


async def inline_suggestion(text: str, api_key: str) -> str:
    system = "You are a brainstorming session design assistant. Be concise and specific."
    prompt = (
        f'The user is writing a problem statement for a multi-agent AI brainstorming session.\n'
        f'Current text: "{text}"\n'
        f'Identify the single most important missing element or improvement.\n'
        f'Return ONE short suggestion (max 15 words). If the text is already strong, return "NONE".'
    )
    return await _ask(system, prompt, api_key)


async def review_problem_statement(text: str, api_key: str) -> dict:
    system = (
        "You are an expert at designing structured multi-agent brainstorming sessions. "
        "A good problem statement should clearly define: the target user, the context, "
        "the problem space (what is in scope and out of scope), why this problem matters, "
        "and what kind of output the session should produce. It should NOT jump into "
        "solutions — it should frame the problem so agents can brainstorm effectively."
    )
    prompt = (
        f'Review and enhance this problem statement for a multi-agent brainstorming session:\n\n'
        f'"{text}"\n\n'
        f'Return JSON:\n'
        f'{{\n'
        f'  "clarity": "Low|Medium|High",\n'
        f'  "clarity_reason": "one sentence",\n'
        f'  "missing": ["list of missing elements — e.g. target user, scope, constraints, context"],\n'
        f'  "suggestions": ["2-3 specific improvement suggestions"],\n'
        f'  "rewrite": "A complete enhanced problem statement that:\\n'
        f'    - Preserves the user\'s original intent\\n'
        f'    - Adds clear SCOPE (in scope / out of scope)\\n'
        f'    - Defines the TARGET USER if missing\\n'
        f'    - Adds CONTEXT section if missing\\n'
        f'    - Adds WHY THIS MATTERS section\\n'
        f'    - Uses structured formatting with section headers\\n'
        f'    - Ends with a clear CORE QUESTION for agents to address\\n'
        f'    - Is detailed enough for agents to brainstorm without extra context"\n'
        f'}}'
    )
    raw = await _ask(system, prompt, api_key)
    result = _parse_json(raw)
    if result and isinstance(result, dict):
        return result
    return {"clarity": "Unknown", "clarity_reason": raw, "missing": [], "suggestions": [], "rewrite": ""}


async def review_problem_discussion(text: str, api_key: str) -> dict:
    system = (
        "You are an expert at framing complex problems for structured multi-agent discussion. "
        "A good problem framing for discussion is different from a product brief — it should "
        "define the problem space without prescribing solutions, surface the tensions and "
        "tradeoffs, identify what 'progress' looks like, and invite multiple perspectives."
    )
    prompt = (
        f'Review and enhance this problem statement for a Problem Discussion session:\n\n'
        f'"{text}"\n\n'
        f'Return JSON:\n'
        f'{{\n'
        f'  "clarity": "Low|Medium|High",\n'
        f'  "clarity_reason": "one sentence",\n'
        f'  "missing": ["list of missing elements"],\n'
        f'  "suggestions": ["2-3 specific improvement suggestions"],\n'
        f'  "rewrite": "A complete enhanced problem statement that:\\n'
        f'    - Preserves the user\'s original intent\\n'
        f'    - Opens with PROBLEM CONTEXT (what is happening, why it matters, who is affected)\\n'
        f'    - Adds DIMENSIONS TO EXPLORE (2-4 lenses through which to examine the problem — e.g. technical, organizational, economic, ethical)\\n'
        f'    - Defines WHAT SOLVED LOOKS LIKE (observable outcomes, not solutions — how would we know progress was made?)\\n'
        f'    - Adds KNOWN CONSTRAINTS (budget, time, political, technical — what limits the solution space?)\\n'
        f'    - Adds TENSIONS & TRADEOFFS (what competing priorities exist? where are the hard choices?)\\n'
        f'    - Lists PERSPECTIVES NEEDED (whose viewpoint must be represented for a robust discussion?)\\n'
        f'    - Ends with CORE QUESTION (the single question the panel must answer)\\n'
        f'    - Does NOT propose solutions — only frames the problem clearly\\n'
        f'    - Uses structured formatting with section headers"\n'
        f'}}'
    )
    raw = await _ask(system, prompt, api_key)
    result = _parse_json(raw)
    if result and isinstance(result, dict):
        return result
    return {"clarity": "Unknown", "clarity_reason": raw, "missing": [], "suggestions": [], "rewrite": ""}


async def review_persona(agent_name: str, persona_text: str, other_agents: list, api_key: str) -> dict:
    system = (
        "You are an expert in designing AI agent personas for structured multi-agent debate. "
        "A strong persona has these sections: ONE-LINE MISSION, BACKGROUND/WORLDVIEW, "
        "WHAT YOU CARE ABOUT MOST, WHAT YOU DISTRUST OR REJECT, DEFAULT QUESTIONS YOU ASK, "
        "BIASES/BLIND SPOTS, WHAT A GOOD IDEA LOOKS LIKE, HOW YOU INTERACT WITH OTHERS, STYLE."
    )
    others_summary = "\n".join(f"- {a.get('name', '?')}: {a.get('persona', '')[:100]}" for a in other_agents)
    prompt = (
        f'Review this agent persona for a brainstorming panel:\n\n'
        f'Name: {agent_name}\n'
        f'Persona:\n{persona_text}\n\n'
        f'Other agents on this panel:\n{others_summary}\n\n'
        f'Required sections: ONE-LINE MISSION, BACKGROUND/WORLDVIEW, WHAT YOU CARE ABOUT MOST, '
        f'WHAT YOU DISTRUST OR REJECT, DEFAULT QUESTIONS YOU ASK, BIASES/BLIND SPOTS, '
        f'WHAT A GOOD IDEA LOOKS LIKE, HOW YOU INTERACT WITH OTHERS, STYLE.\n\n'
        f'Return JSON:\n'
        f'{{\n'
        f'  "missing_sections": ["list of missing required sections"],\n'
        f'  "distinctiveness": "High|Medium|Low",\n'
        f'  "distinctiveness_reason": "one sentence — how distinct from other agents",\n'
        f'  "suggestions": ["2-3 specific improvement suggestions"]\n'
        f'}}'
    )
    raw = await _ask(system, prompt, api_key)
    result = _parse_json(raw)
    if result and isinstance(result, dict):
        return result
    return {"missing_sections": [], "distinctiveness": "Unknown", "distinctiveness_reason": raw, "suggestions": []}


async def enhance_persona(name: str, persona: str, role_tag: str, other_agents: list, api_key: str) -> str:
    system = (
        "You are an expert in designing AI agent personas for structured multi-agent debate. "
        "You produce rich, structured personas that drive productive disagreement."
    )
    others_summary = "\n".join(
        f"- {a.get('name', '?')} ({a.get('role_tag', '')}): {a.get('persona', '')[:150]}"
        for a in other_agents
    )
    prompt = (
        f'Enhance this agent persona into a fully structured format.\n\n'
        f'Name: {name}\n'
        f'Role: {role_tag or "not set"}\n'
        f'Current persona (may be rough/incomplete):\n{persona}\n\n'
        f'Other agents on the panel:\n{others_summary or "None yet"}\n\n'
        f'{_PERSONA_STRUCTURE}\n\n'
        f'Return ONLY the enhanced persona text. No explanation or wrapping.\n'
        f'The first line MUST be: "You are {name} — the [TITLE IN CAPS]."\n'
        f'NEVER use "participant N" — always use the agent\'s actual name.\n'
        f'Make sure this agent is clearly DISTINCT from the other agents listed above.\n'
        f'The persona should be 200-400 words.'
    )
    return await _ask(system, prompt, api_key)


async def suggest_prd_panel(agents: list, problem_statement: str, api_key: str) -> list:
    """Suggest which agents should be on the PRD panel. Always includes a product-focused agent."""
    system = (
        "You select which agents from a brainstorming panel should participate in "
        "a focused PRD co-authoring session. The PRD panel should have 3-5 agents "
        "who can debate product specification. A product-focused agent is MANDATORY."
    )
    agents_desc = "\n".join(
        f"- {a.get('name', '?')} (role: {a.get('role_tag', 'none')}): {a.get('persona', '')[:200]}"
        for a in agents
    )
    prompt = (
        f'These agents just completed a brainstorm on:\n"{problem_statement[:300]}"\n\n'
        f'Available agents:\n{agents_desc}\n\n'
        f'Select 3-5 agents for the PRD co-authoring panel. The panel MUST include:\n'
        f'1. A product-focused agent (product form, scope, interaction model)\n'
        f'2. A user advocate (someone who defends the end user\'s needs)\n'
        f'3. A challenger or technical rigor agent\n\n'
        f'If no agent has a clear "product" role, pick the closest one.\n\n'
        f'Return a JSON object:\n'
        f'{{\n'
        f'  "selected": ["Agent_Name_1", "Agent_Name_2", ...],\n'
        f'  "rationale": {{"Agent_Name_1": "why selected", ...}},\n'
        f'  "product_agent": "which agent fills the mandatory product role"\n'
        f'}}'
    )
    raw = await _ask(system, prompt, api_key)
    result = _parse_json(raw)
    if result and isinstance(result, dict) and "selected" in result:
        return result
    # Fallback: first 4
    return {"selected": [a.get("name", "") for a in agents[:4]], "rationale": {}, "product_agent": ""}


async def suggest_agents(problem_statement: str, mode: str, api_key: str) -> list:
    system = (
        "You are an expert in designing multi-agent brainstorming panels. "
        "You create panels where agents have genuine productive tension — "
        "complementary expertise but different priorities that force rigorous debate."
    )
    prompt = (
        f'Design a 5-6 agent brainstorming panel for this problem:\n\n'
        f'Problem statement:\n{problem_statement}\n\n'
        f'Mode: {mode}\n\n'
        f'The panel MUST include these roles:\n'
        f'1. A Subject/Domain Expert — deep expertise in the specific domain of the problem\n'
        f'2. A Researcher — finds data, benchmarks, prior art, market context (will have web search access)\n'
        f'3. A User/Customer Advocate — defends end-user needs and practical usability\n'
        f'4. A Challenger — pokes holes, questions assumptions, plays devil\'s advocate\n'
        f'5. A Product/Strategy lead — translates ideas into concrete actionable form\n'
        f'6. (Optional) A specialist relevant to this specific problem\n\n'
        f'Each agent needs a FULL structured persona following this format:\n\n'
        f'{_PERSONA_STRUCTURE}\n\n'
        f'Return a JSON array of 5-6 agents:\n'
        f'[{{\n'
        f'  "name": "Simple_First_Name (e.g. Arjun, Maya, Raj — use underscores, no spaces, keep it short)",\n'
        f'  "mission": "one sentence — what this agent exists to do",\n'
        f'  "persona": "FULL persona text following the structure above (200-400 words)",\n'
        f'  "model": "gemini-3.1-pro-preview",\n'
        f'  "role_tag": "short 1-2 word role label",\n'
        f'  "rationale": "one sentence — why this agent creates productive tension"\n'
        f'}}]\n\n'
        f'NAMING RULES:\n'
        f'- Use simple first names only (e.g. Arjun, Maya, Priya, Raj) — NOT descriptive names like "Market_Analyst"\n'
        f'- The role_tag describes their role, not the name\n\n'
        f'The agents MUST create tension: they should disagree on priorities, '
        f'question each other\'s assumptions, and force the discussion to be rigorous. '
        f'Do NOT create agents that will just agree with each other.\n\n'
        f'IMPORTANT: Each persona MUST start with "You are [Name] — the [TITLE]." '
        f'NEVER use "participant N". Agents must refer to each other by NAME, not number.'
    )
    raw = await _ask(system, prompt, api_key)
    result = _parse_json(raw)
    if result and isinstance(result, list):
        # Auto-enable web_search for researcher agents
        for agent in result:
            role = (agent.get("role_tag", "") or "").lower()
            if "research" in role:
                agent["tools"] = ["web_search"]
        return result
    return []
