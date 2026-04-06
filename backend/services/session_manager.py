"""Session manager — runs sessions as background tasks, buffers events for WebSocket observers."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("symposium")


@dataclass
class RunningSession:
    """Tracks a running session's state and event buffer."""
    session_id: str
    task: asyncio.Task
    events: list[dict] = field(default_factory=list)
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    finished: bool = False

    def emit(self, event: dict):
        """Add event to buffer and notify all subscribers."""
        self.events.append(event)
        for queue in self.subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # subscriber too slow, skip

    def subscribe(self) -> asyncio.Queue:
        """Create a new subscriber queue and replay buffered events."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        # Replay all buffered events for reconnecting clients
        for event in self.events:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                break
        self.subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Remove a subscriber queue."""
        if queue in self.subscribers:
            self.subscribers.remove(queue)


class SessionManager:
    """Singleton manager for background session tasks."""

    def __init__(self):
        self._sessions: dict[str, RunningSession] = {}

    def is_running(self, session_id: str) -> bool:
        entry = self._sessions.get(session_id)
        return entry is not None and not entry.finished

    def get(self, session_id: str) -> Optional[RunningSession]:
        return self._sessions.get(session_id)

    def start(self, session_id: str, coro) -> RunningSession:
        """Start a session as a background task."""
        if self.is_running(session_id):
            return self._sessions[session_id]

        entry = RunningSession(
            session_id=session_id,
            task=asyncio.create_task(self._run_wrapper(session_id, coro)),
        )
        self._sessions[session_id] = entry
        return entry

    async def _run_wrapper(self, session_id: str, coro):
        """Wrapper that marks session as finished when done."""
        try:
            await coro
        except Exception as e:
            logger.error(f"Session {session_id} failed: {e}")
            entry = self._sessions.get(session_id)
            if entry:
                entry.emit({"type": "error", "message": str(e)})
        finally:
            entry = self._sessions.get(session_id)
            if entry:
                entry.finished = True

    def cleanup(self, session_id: str):
        """Remove a finished session from tracking."""
        entry = self._sessions.get(session_id)
        if entry and entry.finished:
            del self._sessions[session_id]


# Global singleton
session_manager = SessionManager()
