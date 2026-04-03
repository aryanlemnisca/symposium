import os
import asyncio
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlalchemy.orm import Session as DBSession
from backend.database import get_db
from backend.auth import require_auth
from backend.models.session import Session, SessionStatus
from backend.models.schemas import (
    SessionCreate, SessionUpdate, SessionResponse, AgentConfig, SessionSettings,
)
from backend.services.session_runner import SessionRunner
from backend.services.export import create_zip

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


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
        "phases": s.phases,
        "uploaded_documents": s.uploaded_documents,
        "stress_review_instructions": s.stress_review_instructions,
    }


@router.get("")
def list_sessions(db: DBSession = Depends(get_db), _=Depends(require_auth)):
    sessions = db.query(Session).order_by(Session.created_at.desc()).all()
    return [_session_to_response(s) for s in sessions]


@router.post("", status_code=201)
def create_session(req: SessionCreate, db: DBSession = Depends(get_db), _=Depends(require_auth)):
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
def get_session(session_id: str, db: DBSession = Depends(get_db), _=Depends(require_auth)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_response(session)


@router.patch("/{session_id}")
def update_session(session_id: str, req: SessionUpdate, db: DBSession = Depends(get_db), _=Depends(require_auth)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    update_data = req.model_dump(exclude_unset=True)
    if "agents" in update_data and update_data["agents"] is not None:
        update_data["agents"] = [a.model_dump() if isinstance(a, AgentConfig) else a for a in update_data["agents"]]
    if "settings" in update_data and update_data["settings"] is not None:
        update_data["settings"] = update_data["settings"].model_dump() if isinstance(update_data["settings"], SessionSettings) else update_data["settings"]
    if "uploaded_documents" in update_data and update_data["uploaded_documents"] is not None:
        update_data["uploaded_documents"] = [d.model_dump() if hasattr(d, 'model_dump') else d for d in update_data["uploaded_documents"]]
    if "phases" in update_data and update_data["phases"] is not None:
        update_data["phases"] = [p.model_dump() if hasattr(p, 'model_dump') else p for p in update_data["phases"]]
    for key, value in update_data.items():
        setattr(session, key, value)
    db.commit()
    db.refresh(session)
    return _session_to_response(session)


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, db: DBSession = Depends(get_db), _=Depends(require_auth)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()


@router.post("/{session_id}/run")
def start_session_run(session_id: str, db: DBSession = Depends(get_db), _=Depends(require_auth)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.agents:
        raise HTTPException(status_code=400, detail="No agents configured")
    if not session.problem_statement:
        raise HTTPException(status_code=400, detail="No problem statement")
    return {"ws_url": f"/api/sessions/{session_id}/ws"}


@router.websocket("/{session_id}/ws")
async def session_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()

    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            await websocket.send_json({"type": "error", "message": "Session not found"})
            await websocket.close()
            return

        api_key = os.environ.get("GEMINI_API_KEY", "")
        try:
            init_msg = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
            if init_msg.get("api_key"):
                api_key = init_msg["api_key"]
        except (asyncio.TimeoutError, Exception):
            pass

        if not api_key:
            await websocket.send_json({"type": "error", "message": "No GEMINI_API_KEY configured"})
            await websocket.close()
            return

        command_queue = asyncio.Queue()

        async def receive_loop():
            while True:
                try:
                    msg = await websocket.receive_json()
                    await command_queue.put(msg)
                except WebSocketDisconnect:
                    await command_queue.put({"action": "disconnected"})
                    break
                except Exception:
                    await command_queue.put({"action": "disconnected"})
                    break

        receive_task = asyncio.create_task(receive_loop())

        try:
            runner = SessionRunner(websocket, session, db, api_key)
            await runner.run(receive=command_queue.get)
        finally:
            receive_task.cancel()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        db.close()


@router.get("/{session_id}/export")
def export_session(session_id: str, format: str = "json", db: DBSession = Depends(get_db), _=Depends(require_auth)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.outputs:
        raise HTTPException(status_code=400, detail="Session has no outputs")
    if format == "zip":
        zip_bytes = create_zip(session.outputs, session.name or "session")
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={session.name or 'session'}.zip"},
        )
    return {"outputs": session.outputs}
