"""Session runner — routes to mode-specific engines, emits events to session manager buffer."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DBSession

from backend.models.session import Session, SessionStatus
from backend.engine.config import EngineConfig
from backend.engine.product_brainstorm import run_product_session
from backend.engine.problem_brainstorm import run_problem_session
from backend.engine.stress_brainstorm import run_stress_test
from backend.engine.outputs import build_transcript
from backend.services.session_manager import RunningSession


class SessionRunner:
    def __init__(self, running: RunningSession, session: Session, db: DBSession, api_key: str):
        self.running = running
        self.session = session
        self.db = db
        self.api_key = api_key

    async def emit(self, event_type: str, data: dict):
        self.running.emit({"type": event_type, **data})

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
            prd_panel_names=settings.get("prd_panel_names", []),
            stress_test_min_rounds_per_phase=settings.get("stress_test_min_rounds_per_phase", 20),
        )

        phases = session.phases or []

        session.status = SessionStatus.running
        self.db.commit()

        try:
            mode = config.mode

            if mode == "stress_test":
                documents = session.uploaded_documents or []
                review_instructions = session.stress_review_instructions or ""

                async def _receive():
                    await asyncio.sleep(999999)
                    return {"action": "auto_advance"}

                all_messages, stats, final_phases, verdict_text, exec_summary = await run_stress_test(
                    config, phases, documents, review_instructions,
                    self.emit, _receive,
                )

                transcript = build_transcript(
                    all_messages,
                    {**stats, "model": config.main_model, "max_rounds": config.max_rounds, "mode": "stress_test"},
                    config.agent_names,
                )

                outputs = {"transcript.md": transcript}
                for phase in final_phases:
                    if phase.get("artifact"):
                        outputs[f"phase_{phase['number']}_artifact.md"] = phase["artifact"]
                outputs["verdict.md"] = verdict_text or "Verdict not generated."
                outputs["executive_summary.md"] = exec_summary or "Executive summary not generated."

                session.phases = final_phases
                session.outputs = outputs
                session.status = SessionStatus.complete
                session.completed_at = datetime.now(timezone.utc)
                self.db.commit()

                await self.emit("session_complete", {
                    "terminated_by": stats.get("terminated_by", "verdict"),
                    "outputs": list(outputs.keys()),
                })

            elif mode == "product":
                all_messages, stats, outputs = await run_product_session(
                    config, phases, self.emit,
                )

                session.phases = phases
                session.outputs = outputs
                session.status = SessionStatus.complete
                session.completed_at = datetime.now(timezone.utc)
                self.db.commit()

                await self.emit("session_complete", {
                    "terminated_by": stats.get("terminated_by", "max_rounds"),
                    "outputs": list(outputs.keys()),
                })

            elif mode == "problem_discussion":
                all_messages, stats, outputs = await run_problem_session(
                    config, phases, self.emit,
                )

                session.phases = phases
                session.outputs = outputs
                session.status = SessionStatus.complete
                session.completed_at = datetime.now(timezone.utc)
                self.db.commit()

                await self.emit("session_complete", {
                    "terminated_by": stats.get("terminated_by", "max_rounds"),
                    "outputs": list(outputs.keys()),
                })

            else:
                raise ValueError(f"Unknown session mode: {mode}")

            # Auto-generate session name if still the default placeholder
            if session.status == SessionStatus.complete:
                current_name = (session.name or "").strip().lower()
                if current_name in ("", "untitled", "new session"):
                    try:
                        from backend.services.ai_suggest import generate_session_title
                        title = await generate_session_title(
                            session.problem_statement or "", self.api_key
                        )
                        if title:
                            mode_label = {
                                "product": "Product Mode",
                                "problem_discussion": "Problem Mode",
                                "stress_test": "Stress Test Mode",
                            }.get(mode, mode.replace("_", " ").title() + " Mode")
                            full_title = f"{title} - {mode_label}"
                            session.name = full_title
                            self.db.commit()
                            await self.emit("session_renamed", {"name": full_title})
                    except Exception:
                        pass

        except asyncio.CancelledError:
            # Session was stopped by user
            session.status = SessionStatus.error
            self.db.commit()
            await self.emit("session_stopped", {"message": "Session stopped by user"})
        except Exception as e:
            session.status = SessionStatus.error
            self.db.commit()
            await self.emit("error", {"message": str(e)})
