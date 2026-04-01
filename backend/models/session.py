import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON, Enum as SAEnum
from backend.database import Base
import enum


class SessionStatus(str, enum.Enum):
    draft = "draft"
    running = "running"
    complete = "complete"
    error = "error"


class SessionMode(str, enum.Enum):
    product = "product"
    problem_discussion = "problem_discussion"


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    mode = Column(SAEnum(SessionMode), nullable=False, default=SessionMode.product)
    problem_statement = Column(Text, nullable=False, default="")
    document_ids = Column(JSON, default=list)
    agents = Column(JSON, nullable=False, default=list)
    settings = Column(JSON, nullable=False, default=dict)
    status = Column(SAEnum(SessionStatus), nullable=False, default=SessionStatus.draft)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    transcript = Column(Text, nullable=True)
    artifact = Column(JSON, nullable=True)
    outputs = Column(JSON, nullable=True)
    canvas_state = Column(JSON, default=dict)
