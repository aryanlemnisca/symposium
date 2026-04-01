"""Session runner — wraps engine, emits WebSocket events."""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import WebSocket
from sqlalchemy.orm import Session as DBSession

from backend.models.session import Session, SessionStatus
from backend.engine.config import EngineConfig
from backend.engine.brainstorm import run_brainstorm
from backend.engine.prd_panel import run_prd_mini_panel
from backend.engine.conclusion import generate_conclusion
from backend.engine.synthesis import generate_synthesis_and_prd
from backend.engine.outputs import build_transcript, build_artifact


class SessionRunner:
    def __init__(self, websocket: WebSocket, session: Session, db: DBSession, api_key: str):
        self.ws = websocket
        self.session = session
        self.db = db
        self.api_key = api_key

    async def emit(self, event_type: str, data: dict):
        await self.ws.send_json({"type": event_type, **data})

    async def run(self):
        session = self.session
        settings = session.settings or {}

        config = EngineConfig(
            gemini_api_key=self.api_key,
            problem_statement=session.problem_statement,
            agents=session.agents or [],
            mode=session.mode.value if hasattr(session.mode, "value") else str(session.mode),
            max_rounds=settings.get("max_rounds", 50),
            temperature=settings.get("temperature", 0.70),
            gate_start_round=settings.get("gate_start_round", 10),
            overseer_interval=settings.get("overseer_interval", 10),
            min_rounds_before_convergence=settings.get("min_rounds_before_convergence", 45),
            prd_panel_rounds=settings.get("prd_panel_rounds", 10),
        )

        session.status = SessionStatus.running
        self.db.commit()

        try:
            messages, stats, living_artifact = await run_brainstorm(config, self.emit)

            mode = config.mode
            if mode == "product":
                panel_messages = await run_prd_mini_panel(config, living_artifact, self.emit)
                synthesis_text, prd_text = await generate_synthesis_and_prd(
                    config.main_model, config.gemini_api_key, config.temperature,
                    panel_messages,
                )
                outputs = {
                    "transcript.md": build_transcript(messages, {**stats, "model": config.main_model, "max_rounds": config.max_rounds}, config.agent_names),
                    "artifact.md": build_artifact(living_artifact),
                    "synthesis.md": f"# Final Synthesis Report\n\n{synthesis_text}",
                    "prd.md": prd_text,
                }
            else:
                conclusion_text = await generate_conclusion(config, messages, living_artifact, self.emit)
                outputs = {
                    "transcript.md": build_transcript(messages, {**stats, "model": config.main_model, "max_rounds": config.max_rounds}, config.agent_names),
                    "artifact.md": build_artifact(living_artifact),
                    "conclusion.md": conclusion_text,
                }

            session.status = SessionStatus.complete
            session.completed_at = datetime.now(timezone.utc)
            session.transcript = outputs.get("transcript.md", "")
            session.artifact = living_artifact
            session.outputs = outputs
            self.db.commit()

            await self.emit("session_complete", {
                "terminated_by": stats["terminated_by"],
                "outputs": list(outputs.keys()),
            })

        except Exception as e:
            session.status = SessionStatus.error
            self.db.commit()
            await self.emit("error", {"message": str(e)})
