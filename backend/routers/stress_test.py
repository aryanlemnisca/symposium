"""Stress test specific endpoints."""

import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session as DBSession
from backend.database import get_db
from backend.auth import require_auth
from backend.models.session import Session
from backend.services.doc_extract import extract_text
from backend.services import stress_suggest

router = APIRouter(prefix="/api", tags=["stress-test"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".xlsx", ".csv"}
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB


@router.post("/upload/stress-test")
async def upload_stress_test_document(
    file: UploadFile = File(...),
    _=Depends(require_auth),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max {MAX_UPLOAD_SIZE // (1024*1024)}MB")

    try:
        content_text = extract_text(content, file.filename or "document")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    doc = {
        "id": str(uuid.uuid4()),
        "filename": file.filename or "document",
        "filetype": ext.lstrip("."),
        "content_text": content_text,
        "size_bytes": len(content),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "id": doc["id"],
        "filename": doc["filename"],
        "filetype": doc["filetype"],
        "size_bytes": doc["size_bytes"],
        "preview": content_text[:500],
        "uploaded_at": doc["uploaded_at"],
        "document": doc,
    }


def _get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    return key


@router.post("/sessions/{session_id}/stress/analyse-documents")
async def analyse_documents(
    session_id: str,
    db: DBSession = Depends(get_db),
    _=Depends(require_auth),
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.uploaded_documents:
        raise HTTPException(status_code=400, detail="No documents uploaded")
    if not session.problem_statement:
        raise HTTPException(status_code=400, detail="No problem statement")

    result = await stress_suggest.analyse_documents(
        session.uploaded_documents,
        session.problem_statement,
        _get_api_key(),
    )
    return result


@router.post("/sessions/{session_id}/stress/reinterpret-phases")
async def reinterpret_phases(
    session_id: str,
    body: dict,
    db: DBSession = Depends(get_db),
    _=Depends(require_auth),
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await stress_suggest.reinterpret_phases(
        body.get("phases", []),
        session.uploaded_documents or [],
        session.problem_statement or "",
        _get_api_key(),
    )
    return result


@router.post("/sessions/{session_id}/stress/confirm-phases")
async def confirm_phases(
    session_id: str,
    body: dict,
    db: DBSession = Depends(get_db),
    _=Depends(require_auth),
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    phases = body.get("phases", [])
    review_instructions = body.get("review_instructions", "")

    for p in phases:
        p["status"] = "pending"
        p["start_round"] = None
        p["end_round"] = None
        p["artifact"] = None
        p["confirmed"] = []
        p["contested"] = []
        p["open_questions"] = []

    session.phases = phases
    session.current_phase_index = 0
    session.stress_review_instructions = review_instructions
    db.commit()

    return {"status": "confirmed", "phase_count": len(phases)}


@router.post("/sessions/{session_id}/stress/suggest-agents")
async def suggest_agents(
    session_id: str,
    db: DBSession = Depends(get_db),
    _=Depends(require_auth),
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.phases:
        raise HTTPException(status_code=400, detail="Phases not confirmed yet")

    result = await stress_suggest.suggest_stress_test_agents(
        session.uploaded_documents or [],
        session.phases,
        session.problem_statement or "",
        _get_api_key(),
    )
    return {"agents": result}


@router.get("/sessions/{session_id}/stress/phases")
def get_phases(
    session_id: str,
    db: DBSession = Depends(get_db),
    _=Depends(require_auth),
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"phases": session.phases or [], "current_phase_index": session.current_phase_index}


@router.get("/sessions/{session_id}/stress/artifacts")
def get_artifacts(
    session_id: str,
    db: DBSession = Depends(get_db),
    _=Depends(require_auth),
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    artifacts = []
    for phase in (session.phases or []):
        if phase.get("artifact"):
            artifacts.append({
                "phase_number": phase["number"],
                "phase_name": phase["name"],
                "artifact": phase["artifact"],
            })
    return {"artifacts": artifacts}
