import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer, Enum as SAEnum
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
    stress_test = "stress_test"


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
    phases = Column(JSON, nullable=True)
    current_phase_index = Column(Integer, nullable=True)
    uploaded_documents = Column(JSON, nullable=True)
    stress_review_instructions = Column(Text, nullable=True)
