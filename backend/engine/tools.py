"""Agent tools — web search via Gemini grounding."""

import os
import httpx


async def web_search(query: str) -> str:
    """Search the web for current information. Use this when you need recent data, facts, statistics, or real-world context to support your arguments."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return "Web search unavailable: no API key configured."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": query}]}],
        "tools": [{"google_search": {}}],
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Extract grounded answer
        candidates = data.get("candidates", [])
        if not candidates:
            return "No search results found."

        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [p["text"] for p in parts if "text" in p]
        answer = "\n".join(text_parts) if text_parts else "No results."

        return answer
    except Exception as e:
        return f"Web search failed: {str(e)}"


# Registry of available tools
TOOL_REGISTRY = {
    "web_search": web_search,
}


def get_tools_for_agent(tool_names: list[str]) -> list:
    """Return callable tool functions for the given tool names."""
    return [TOOL_REGISTRY[name] for name in tool_names if name in TOOL_REGISTRY]
