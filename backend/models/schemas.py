from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class SessionMode(str, Enum):
    product = "product"
    problem_discussion = "problem_discussion"
    stress_test = "stress_test"


class PhaseStatus(str, Enum):
    pending = "pending"
    active = "active"
    complete = "complete"


class UploadedDocument(BaseModel):
    id: str
    filename: str
    filetype: str
    content_text: str
    size_bytes: int
    uploaded_at: str


class Phase(BaseModel):
    number: int
    name: str
    document_ids: list[str] = []
    focus_question: str = ""
    key_subquestions: list[str] = []
    rationale: str = ""
    status: PhaseStatus = PhaseStatus.pending
    start_round: Optional[int] = None
    end_round: Optional[int] = None
    artifact: Optional[str] = None
    confirmed: list[str] = []
    contested: list[str] = []
    open_questions: list[str] = []


class AgentConfig(BaseModel):
    id: str
    name: str
    model: str = "gemini-3.1-pro-preview"
    persona: str = ""
    tools: list[str] = []
    role_tag: Optional[str] = None
    canvas_position: dict = Field(default_factory=lambda: {"x": 0, "y": 0})


class SessionSettings(BaseModel):
    max_rounds: int = 50
    temperature: float = 0.70
    gate_start_round: int = 10
    overseer_interval: int = 10
    min_rounds_before_convergence: int = 45
    prd_panel_rounds: int = 10
    prd_panel_names: list[str] = []
    stress_test_min_rounds_per_phase: int = 20


class SessionCreate(BaseModel):
    name: str
    mode: SessionMode = SessionMode.product
    problem_statement: str = ""
    agents: list[AgentConfig] = []
    settings: SessionSettings = Field(default_factory=SessionSettings)
    canvas_state: dict = Field(default_factory=dict)
    document_ids: list[str] = []


class SessionUpdate(BaseModel):
    name: Optional[str] = None
    mode: Optional[SessionMode] = None
    problem_statement: Optional[str] = None
    agents: Optional[list[AgentConfig]] = None
    settings: Optional[SessionSettings] = None
    canvas_state: Optional[dict] = None
    document_ids: Optional[list[str]] = None
    phases: Optional[list[Phase]] = None
    uploaded_documents: Optional[list[UploadedDocument]] = None
    stress_review_instructions: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    name: str
    mode: str
    problem_statement: str
    agents: list[dict]
    settings: dict
    status: str
    created_at: str
    completed_at: Optional[str]
    canvas_state: dict
    document_ids: list[str]
    outputs: Optional[dict] = None
    phases: Optional[list[dict]] = None
    uploaded_documents: Optional[list[dict]] = None
    stress_review_instructions: Optional[str] = None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    agents: list[AgentConfig] = []
    settings: SessionSettings = Field(default_factory=SessionSettings)
    mode: Optional[str] = None
    problem_statement_template: Optional[str] = None
    canvas_state: dict = Field(default_factory=dict)


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    agents: list[dict]
    settings: dict
    mode: Optional[str]
    problem_statement_template: Optional[str]
    canvas_state: dict
    is_default: bool
    created_at: str

    class Config:
        from_attributes = True


class ReviewRequest(BaseModel):
    text: str
    review_type: str
    other_agents: list[dict] = []


class ReviewResponse(BaseModel):
    result: dict


class AgentSuggestionRequest(BaseModel):
    problem_statement: str
    mode: str = "product"


class AgentSuggestionResponse(BaseModel):
    agents: list[dict]
