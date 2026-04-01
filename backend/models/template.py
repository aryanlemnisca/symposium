import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON, Boolean
from backend.database import Base


class Template(Base):
    __tablename__ = "templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    agents = Column(JSON, nullable=False, default=list)
    settings = Column(JSON, nullable=False, default=dict)
    mode = Column(String, nullable=True)
    problem_statement_template = Column(Text, nullable=True)
    canvas_state = Column(JSON, default=dict)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
