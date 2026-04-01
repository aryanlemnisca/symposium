import os
from fastapi import APIRouter, Depends, HTTPException
from backend.auth import require_auth
from backend.models.schemas import ReviewRequest, AgentSuggestionRequest
from backend.services import ai_suggest

router = APIRouter(prefix="/api/suggest", tags=["suggest"], dependencies=[Depends(require_auth)])


def _get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    return key


@router.post("/inline")
async def inline_suggestion(body: dict):
    text = body.get("text", "")
    if not text:
        return {"suggestion": "NONE"}
    result = await ai_suggest.inline_suggestion(text, _get_api_key())
    return {"suggestion": result}


@router.post("/review")
async def review(req: ReviewRequest):
    api_key = _get_api_key()
    if req.review_type == "problem_statement":
        result = await ai_suggest.review_problem_statement(req.text, api_key)
    elif req.review_type == "persona":
        result = await ai_suggest.review_persona(
            req.other_agents[0].get("name", "") if req.other_agents else "",
            req.text,
            req.other_agents,
            api_key,
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid review_type")
    return {"result": result}


@router.post("/agents")
async def suggest_agents(req: AgentSuggestionRequest):
    result = await ai_suggest.suggest_agents(req.problem_statement, req.mode, _get_api_key())
    return {"agents": result}
