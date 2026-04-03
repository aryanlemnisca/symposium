from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class SessionMode(str, Enum):
    product = "product"
    problem_discussion = "problem_discussion"


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
