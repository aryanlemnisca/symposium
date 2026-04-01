from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from backend.database import get_db
from backend.auth import require_auth
from backend.models.session import Session, SessionStatus
from backend.models.schemas import (
    SessionCreate, SessionUpdate, SessionResponse, AgentConfig, SessionSettings,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"], dependencies=[Depends(require_auth)])


def _session_to_response(s: Session) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "mode": s.mode.value if hasattr(s.mode, "value") else str(s.mode),
        "problem_statement": s.problem_statement or "",
        "agents": s.agents or [],
        "settings": s.settings or {},
        "status": s.status.value if hasattr(s.status, "value") else str(s.status),
        "created_at": s.created_at.isoformat() if s.created_at else "",
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        "canvas_state": s.canvas_state or {},
        "document_ids": s.document_ids or [],
        "outputs": s.outputs,
    }


@router.get("")
def list_sessions(db: DBSession = Depends(get_db)):
    sessions = db.query(Session).order_by(Session.created_at.desc()).all()
    return [_session_to_response(s) for s in sessions]


@router.post("", status_code=201)
def create_session(req: SessionCreate, db: DBSession = Depends(get_db)):
    session = Session(
        name=req.name,
        mode=req.mode,
        problem_statement=req.problem_statement,
        agents=[a.model_dump() for a in req.agents],
        settings=req.settings.model_dump(),
        canvas_state=req.canvas_state,
        document_ids=req.document_ids,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_to_response(session)


@router.get("/{session_id}")
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_response(session)


@router.patch("/{session_id}")
def update_session(session_id: str, req: SessionUpdate, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    update_data = req.model_dump(exclude_unset=True)
    if "agents" in update_data and update_data["agents"] is not None:
        update_data["agents"] = [a.model_dump() if isinstance(a, AgentConfig) else a for a in update_data["agents"]]
    if "settings" in update_data and update_data["settings"] is not None:
        update_data["settings"] = update_data["settings"].model_dump() if isinstance(update_data["settings"], SessionSettings) else update_data["settings"]
    for key, value in update_data.items():
        setattr(session, key, value)
    db.commit()
    db.refresh(session)
    return _session_to_response(session)


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, db: DBSession = Depends(get_db)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
