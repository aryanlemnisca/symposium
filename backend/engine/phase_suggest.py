"""AI-powered phase suggestions for Product and Problem Discussion modes."""

import json
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.clients import make_client

SUPPORT_MODEL = "gemini-2.5-flash"

# ── Default templates ────────────────────────────────────────────────────────

PRODUCT_PHASES = [
    {
        "number": 1,
        "name": "Problem & User Understanding",
        "focus_question": "What is the core problem and who experiences it?",
        "key_subquestions": [
            "Who is the primary user?",
            "What pain or friction do they face today?",
            "What workaround exists today?",
            "Why hasn't this been solved already?",
        ],
        "artifact_schema": ["Confirmed", "Contested", "Must Address", "Open Questions"],
        "critical": False,
        "rationale": "Starting with problem clarity ensures the team solves the right thing.",
    },
    {
        "number": 2,
        "name": "Research & Landscape",
        "focus_question": "What does the competitive and market landscape look like?",
        "key_subquestions": [
            "Who are the main competitors and what do they offer?",
            "What benchmarks or data points matter?",
            "Are there adjacent markets or analogies to learn from?",
            "What trends are shaping this space?",
        ],
        "artifact_schema": ["Key Findings", "Competitor Matrix", "Data Gaps", "Opportunities"],
        "critical": False,
        "rationale": "Research grounds ideation in reality and prevents reinventing the wheel.",
    },
    {
        "number": 3,
        "name": "Solution Ideation",
        "focus_question": "What solution concepts best address the problem given what we know?",
        "key_subquestions": [
            "What are 3-5 distinct solution directions?",
            "Which research findings should each solution leverage?",
            "What is the simplest version of each concept?",
            "What would delight the user vs. merely satisfy them?",
        ],
        "artifact_schema": ["Proposed Concepts", "Pros & Cons", "User Impact", "Open Questions"],
        "critical": False,
        "rationale": "Generating multiple options before converging prevents premature commitment.",
    },
    {
        "number": 4,
        "name": "Feasibility & Critique",
        "focus_question": "Which ideas survive scrutiny on technical and business viability?",
        "key_subquestions": [
            "What are the hardest technical challenges for each concept?",
            "What is the estimated cost and timeline?",
            "What business model assumptions need validation?",
            "What could go catastrophically wrong?",
        ],
        "artifact_schema": ["Feasible", "Risky", "Killed", "Needs Investigation"],
        "critical": True,
        "rationale": "Rigorous critique before convergence prevents wasted effort on unviable paths.",
    },
]

PROBLEM_PHASES = [
    {
        "number": 1,
        "name": "Problem Decomposition",
        "focus_question": "What are the key dimensions and sub-problems?",
        "key_subquestions": [
            "What are the distinct facets of this problem?",
            "Which dimensions are most important?",
            "What assumptions are embedded in the framing?",
            "What is in scope vs. out of scope?",
        ],
        "artifact_schema": ["Confirmed", "Contested", "Must Address", "Open Questions"],
        "critical": False,
        "rationale": "Breaking the problem into dimensions ensures nothing important is missed.",
    },
    {
        "number": 2,
        "name": "Research & Context",
        "focus_question": "What prior work, data, and case studies inform this problem?",
        "key_subquestions": [
            "What has been tried before?",
            "What data or evidence is available?",
            "What case studies or analogies are relevant?",
            "What do experts in this domain say?",
        ],
        "artifact_schema": ["Key Findings", "Evidence Base", "Knowledge Gaps", "Sources"],
        "critical": False,
        "rationale": "Grounding discussion in evidence prevents opinion-driven conclusions.",
    },
    {
        "number": 3,
        "name": "Perspective Exploration",
        "focus_question": "What do different frameworks and viewpoints reveal?",
        "key_subquestions": [
            "What do different stakeholders prioritize?",
            "What frameworks or lenses apply?",
            "Where do perspectives conflict?",
            "What blind spots does each perspective have?",
        ],
        "artifact_schema": ["Perspectives Map", "Points of Agreement", "Points of Conflict", "Blind Spots"],
        "critical": False,
        "rationale": "Multiple viewpoints surface insights that a single perspective would miss.",
    },
    {
        "number": 4,
        "name": "Tension Resolution",
        "focus_question": "How do we resolve the key disagreements and find common ground?",
        "key_subquestions": [
            "What are the strongest arguments on each side?",
            "Where is compromise possible vs. where must we choose?",
            "What evidence would change minds?",
            "What principles should guide resolution?",
        ],
        "artifact_schema": ["Resolved", "Compromised", "Irreconcilable", "Decision Criteria"],
        "critical": True,
        "rationale": "Directly resolving tensions produces stronger conclusions than avoiding disagreement.",
    },
    {
        "number": 5,
        "name": "Synthesis & Recommendations",
        "focus_question": "What are our final positions and actionable recommendations?",
        "key_subquestions": [
            "What conclusions does the evidence support?",
            "What are the top 3-5 recommendations?",
            "What confidence level does each recommendation carry?",
            "What should be investigated further?",
        ],
        "artifact_schema": ["Key Conclusions", "Recommendations", "Confidence Levels", "Next Steps"],
        "critical": False,
        "rationale": "Clear synthesis with confidence levels makes the output actionable.",
    },
]


def _default_phases(mode: str) -> list[dict]:
    if mode == "product":
        return [dict(p) for p in PRODUCT_PHASES]
    return [dict(p) for p in PROBLEM_PHASES]


def _parse_json(raw: str) -> list | None:
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        parsed = json.loads(raw.strip())
        if isinstance(parsed, list):
            return parsed
        return None
    except (json.JSONDecodeError, IndexError):
        return None


async def suggest_phases(
    problem_statement: str,
    mode: str,
    api_key: str,
) -> list[dict]:
    """Generate AI-customized phase suggestions for product or problem discussion mode.

    Returns a list of phase dicts with number, name, focus_question, key_subquestions,
    artifact_schema, critical, and rationale fields.
    Falls back to default templates if LLM call fails.
    """
    defaults = _default_phases(mode)
    if not problem_statement.strip():
        return defaults

    template_json = json.dumps(defaults, indent=2)
    mode_label = "product brainstorm" if mode == "product" else "problem discussion"

    system = (
        "You are an expert facilitator who designs structured multi-agent brainstorming sessions. "
        "You customize discussion phases to match the specific problem being discussed. "
        "You always return valid JSON and nothing else."
    )
    prompt = (
        f"A team is about to run a {mode_label} session on this problem:\n\n"
        f'"{problem_statement}"\n\n'
        f"Here is the default phase template:\n\n"
        f"{template_json}\n\n"
        f"Customize the phases for this specific problem. Rules:\n"
        f"- Keep the same number of phases ({len(defaults)}) and the same phase names.\n"
        f"- Keep the same artifact_schema and critical flags.\n"
        f"- Rewrite focus_question to be specific to this problem.\n"
        f"- Rewrite key_subquestions (keep 3-5 per phase) to be specific to this problem.\n"
        f"- Rewrite rationale to explain why this phase matters for THIS problem.\n"
        f"- The subquestions should reference concrete aspects of the problem statement.\n\n"
        f"Return ONLY a JSON array of phase objects. Each object must have exactly these fields:\n"
        f"  number (int), name (str), focus_question (str), key_subquestions (list[str]),\n"
        f"  artifact_schema (list[str]), critical (bool), rationale (str)\n\n"
        f"No markdown, no explanation — just the JSON array."
    )

    try:
        client = make_client(model=SUPPORT_MODEL, api_key=api_key, temperature=0.3)
        agent = AssistantAgent(
            name="PhaseSuggester",
            system_message=system,
            model_client=client,
        )
        response = await agent.on_messages(
            [TextMessage(content=prompt, source="user")], CancellationToken()
        )
        raw = response.chat_message.content if response and response.chat_message else ""
        phases = _parse_json(raw)
        if phases and len(phases) == len(defaults):
            # Validate structure of each phase
            required_keys = {"number", "name", "focus_question", "key_subquestions", "artifact_schema", "critical", "rationale"}
            for phase in phases:
                if not isinstance(phase, dict) or not required_keys.issubset(phase.keys()):
                    return defaults
            return phases
    except Exception:
        pass

    return defaults
