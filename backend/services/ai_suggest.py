"""AI suggestion service — problem statement + persona review + agent suggestions."""

import os
import json
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.clients import make_client

SUPPORT_MODEL = "gemini-2.5-flash"


async def _ask(system: str, user_prompt: str, api_key: str) -> str:
    client = make_client(model=SUPPORT_MODEL, api_key=api_key, temperature=0.3)
    agent = AssistantAgent(name="Suggester", system_message=system, model_client=client)
    response = await agent.on_messages(
        [TextMessage(content=user_prompt, source="user")], CancellationToken()
    )
    return response.chat_message.content if response and response.chat_message else ""


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
    system = "You are a brainstorming session design expert."
    prompt = (
        f'Review this problem statement for a multi-agent AI discussion session:\n\n'
        f'"{text}"\n\n'
        f'Return JSON:\n'
        f'{{\n'
        f'  "clarity": "Low|Medium|High",\n'
        f'  "clarity_reason": "one sentence",\n'
        f'  "missing": ["list of missing elements"],\n'
        f'  "suggestions": ["2-3 specific improvement suggestions"],\n'
        f'  "rewrite": "improved version of the problem statement"\n'
        f'}}'
    )
    raw = await _ask(system, prompt, api_key)
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return {"clarity": "Unknown", "clarity_reason": raw, "missing": [], "suggestions": [], "rewrite": ""}


async def review_persona(agent_name: str, persona_text: str, other_agents: list, api_key: str) -> dict:
    system = "You are an expert in designing AI agent personas for structured debate."
    others_summary = "\n".join(f"- {a.get('name', '?')}: {a.get('persona', '')[:100]}" for a in other_agents)
    prompt = (
        f'Review this agent persona:\n\n'
        f'Name: {agent_name}\n'
        f'Persona: {persona_text}\n\n'
        f'Other agents on this panel:\n{others_summary}\n\n'
        f'Return JSON:\n'
        f'{{\n'
        f'  "missing_sections": ["list of missing must-contain sections"],\n'
        f'  "distinctiveness": "High|Medium|Low",\n'
        f'  "distinctiveness_reason": "one sentence",\n'
        f'  "suggestions": ["2-3 specific improvement suggestions"]\n'
        f'}}'
    )
    raw = await _ask(system, prompt, api_key)
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return {"missing_sections": [], "distinctiveness": "Unknown", "distinctiveness_reason": raw, "suggestions": []}


async def suggest_agents(problem_statement: str, mode: str, api_key: str) -> list:
    system = "You are an expert in designing multi-agent brainstorming panels."
    prompt = (
        f'Based on this problem statement, suggest 4 agent archetypes that would '
        f'create productive tension and cover the most important perspectives.\n\n'
        f'Problem: "{problem_statement}"\n'
        f'Mode: {mode}\n\n'
        f'Return a JSON array of 4 agents:\n'
        f'[{{\n'
        f'  "name": "short descriptive name (use underscores, no spaces)",\n'
        f'  "mission": "one sentence mission",\n'
        f'  "persona": "full persona text",\n'
        f'  "model": "gemini-3.1-pro-preview",\n'
        f'  "role_tag": "short role label",\n'
        f'  "rationale": "one sentence — why this agent adds value"\n'
        f'}}]'
    )
    raw = await _ask(system, prompt, api_key)
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return []
