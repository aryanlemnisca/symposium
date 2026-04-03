# Symposium — Full Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Symposium — a general-purpose multi-agent AI brainstorming web app that wraps the existing `lemnisca_panel.py` engine into a React + FastAPI application with a visual canvas, live streaming, and structured output generation.

**Architecture:** FastAPI backend serves a REST API + WebSocket endpoint. The brainstorming engine (modularized from `Example Run/lemnisca_panel.py`) runs sessions asynchronously, streaming agent messages over WebSocket. React frontend (Vite + TypeScript) uses React Flow for the canvas, Zustand for state, and a WebSocket hook for live streaming. SQLite via SQLAlchemy for persistence.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, SQLite, AutoGen v0.4, Gemini API (via OpenAI-compatible client), React 18, Vite, TypeScript, React Flow, Zustand, TailwindCSS

**Reference files:**
- PRD: `prd.md` (Sections 1-12)
- Working engine: `Example Run/lemnisca_panel.py` (1907 lines — the source of truth for all brainstorming logic)
- Example outputs: `Example Run/lemnisca_transcript_*.md`, `lemnisca_artifact_*.md`, `lemnisca_synthesis_*.md`, `lemnisca_prd_*.md`

---

## File Structure

```
symposium/
├── backend/
│   ├── main.py                        # FastAPI app, CORS, lifespan, mount routers
│   ├── auth.py                        # password check middleware + token generation
│   ├── database.py                    # SQLAlchemy engine, session factory, Base
│   ├── models/
│   │   ├── __init__.py
│   │   ├── session.py                 # Session ORM model
│   │   ├── template.py               # Template ORM model
│   │   └── schemas.py                # Pydantic request/response schemas
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth_router.py            # POST /api/auth/login
│   │   ├── sessions.py               # CRUD + run + export for sessions
│   │   ├── templates.py              # CRUD for templates
│   │   ├── suggest.py                # AI suggestion endpoints
│   │   └── upload.py                 # Document upload endpoint
│   ├── services/
│   │   ├── __init__.py
│   │   ├── session_runner.py         # Wraps engine, emits WebSocket events
│   │   ├── ai_suggest.py             # Problem statement + persona review
│   │   └── export.py                 # ZIP generation
│   └── engine/
│       ├── __init__.py
│       ├── config.py                  # SessionConfig dataclass, defaults
│       ├── clients.py                 # Gemini OpenAI-compatible client factory
│       ├── gate.py                    # Speech gate logic
│       ├── selector.py                # Hybrid selector (rotation + LLM)
│       ├── overseer.py                # Overseer constraint reminder
│       ├── artifact.py                # Living artifact builder
│       ├── convergence.py             # Convergence detection + consensus termination
│       ├── summary.py                 # Rolling summary
│       ├── brainstorm.py              # Main brainstorm loop
│       ├── prd_panel.py               # PRD mini-panel (Product mode)
│       ├── conclusion.py              # Conclusion report (Problem Discussion mode)
│       ├── synthesis.py               # Synthesis + PRD/Conclusion output generation
│       └── outputs.py                 # Transcript, artifact, synthesis file builders
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── src/
│   │   ├── main.tsx                   # React root
│   │   ├── App.tsx                    # Router setup
│   │   ├── api/
│   │   │   └── client.ts             # Fetch wrapper with auth token
│   │   ├── store/
│   │   │   ├── authStore.ts           # Auth state (token, login/logout)
│   │   │   ├── sessionStore.ts        # Active session state
│   │   │   └── canvasStore.ts         # Canvas nodes/edges state
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts        # WebSocket connection + message handling
│   │   │   ├── useSession.ts          # Session CRUD hooks
│   │   │   └── useAISuggest.ts        # AI suggestion debounce hook
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Sessions.tsx
│   │   │   ├── Canvas.tsx             # Setup + live view
│   │   │   └── Results.tsx
│   │   ├── components/
│   │   │   ├── canvas/
│   │   │   │   ├── AgentNode.tsx       # Custom React Flow node
│   │   │   │   ├── AgentDrawer.tsx     # Slide-in agent config panel
│   │   │   │   └── AgentLibrary.tsx    # Right sidebar with agent cards
│   │   │   ├── session/
│   │   │   │   ├── LiveFeed.tsx        # Streaming message feed
│   │   │   │   ├── ArtifactPanel.tsx   # Living artifact display
│   │   │   │   └── StatsBar.tsx        # Round counter, gate skips, etc.
│   │   │   ├── setup/
│   │   │   │   ├── ProblemStatement.tsx # Problem text area + suggestions
│   │   │   │   ├── ModeSelector.tsx    # Product / Problem Discussion toggle
│   │   │   │   └── AdvancedSettings.tsx # Gate round, overseer interval, temp
│   │   │   └── shared/
│   │   │       ├── MarkdownRenderer.tsx # Renders MD content
│   │   │       └── ReviewPanel.tsx      # AI review structured feedback
│   │   └── styles/
│   │       └── globals.css             # Tailwind imports + dark theme vars
│   └── public/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Phase 1: Backend Foundation

### Task 1: Project scaffolding and dependencies

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `backend/__init__.py` (empty)
- Create: `backend/models/__init__.py` (empty)
- Create: `backend/routers/__init__.py` (empty)
- Create: `backend/services/__init__.py` (empty)
- Create: `backend/engine/__init__.py` (empty)

- [ ] **Step 1: Create requirements.txt**

```txt
fastapi==0.115.12
uvicorn[standard]==0.34.2
sqlalchemy==2.0.40
python-multipart==0.0.20
python-dotenv==1.1.0
pydantic==2.11.1
pyautogen==0.4.7
autogen-ext[openai]==0.4.7
aiofiles==24.1.0
python-jose[cryptography]==3.4.0
```

- [ ] **Step 2: Create .env.example**

```bash
SYMPOSIUM_PASSWORD=symposium2025
GEMINI_API_KEY=your_key_here
DATABASE_URL=sqlite:///./symposium.db
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
MAX_UPLOAD_SIZE_MB=10
```

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.env
*.db
uploads/
outputs/
node_modules/
dist/
.vite/
```

- [ ] **Step 4: Create empty __init__.py files**

Create empty files at:
- `backend/__init__.py`
- `backend/models/__init__.py`
- `backend/routers/__init__.py`
- `backend/services/__init__.py`
- `backend/engine/__init__.py`

- [ ] **Step 5: Install dependencies and verify**

Run: `cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium && pip install -r requirements.txt`
Expected: All packages install successfully

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example .gitignore backend/
git commit -m "feat: project scaffolding with dependencies and package structure"
```

---

### Task 2: Database setup and ORM models

**Files:**
- Create: `backend/database.py`
- Create: `backend/models/session.py`
- Create: `backend/models/template.py`
- Create: `backend/models/schemas.py`

- [ ] **Step 1: Create backend/database.py**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./symposium.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 2: Create backend/models/session.py**

```python
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
    agents = Column(JSON, nullable=False, default=list)  # list of AgentConfig dicts
    settings = Column(JSON, nullable=False, default=dict)
    status = Column(SAEnum(SessionStatus), nullable=False, default=SessionStatus.draft)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    transcript = Column(Text, nullable=True)
    artifact = Column(JSON, nullable=True)
    outputs = Column(JSON, nullable=True)  # {filename: content}
    canvas_state = Column(JSON, default=dict)  # {node_id: {x, y}}
```

- [ ] **Step 3: Create backend/models/template.py**

```python
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
```

- [ ] **Step 4: Create backend/models/schemas.py**

```python
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
    review_type: str  # "problem_statement" or "persona"
    other_agents: list[dict] = []


class ReviewResponse(BaseModel):
    result: dict


class AgentSuggestionRequest(BaseModel):
    problem_statement: str
    mode: str = "product"


class AgentSuggestionResponse(BaseModel):
    agents: list[dict]
```

- [ ] **Step 5: Verify models import correctly**

Run: `cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium && python -c "from backend.database import Base, init_db; from backend.models.session import Session; from backend.models.template import Template; from backend.models.schemas import SessionCreate, AgentConfig; print('Models OK')"`
Expected: `Models OK`

- [ ] **Step 6: Commit**

```bash
git add backend/database.py backend/models/
git commit -m "feat: database setup and ORM models for sessions and templates"
```

---

### Task 3: Auth middleware

**Files:**
- Create: `backend/auth.py`

- [ ] **Step 1: Create backend/auth.py**

```python
import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

SECRET_KEY = os.environ.get("JWT_SECRET", secrets.token_hex(32))
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer()


def verify_password(password: str) -> bool:
    expected = os.environ.get("SYMPOSIUM_PASSWORD", "symposium2025")
    return secrets.compare_digest(password, expected)


def create_token() -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"exp": expire, "sub": "symposium_user"}, SECRET_KEY, algorithm=ALGORITHM)


def require_auth(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
```

- [ ] **Step 2: Verify auth module**

Run: `cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium && python -c "from backend.auth import verify_password, create_token; assert verify_password('symposium2025'); t = create_token(); print(f'Token: {t[:20]}...'); print('Auth OK')"`
Expected: `Token: eyJ...` followed by `Auth OK`

- [ ] **Step 3: Commit**

```bash
git add backend/auth.py
git commit -m "feat: simple shared-password auth with JWT tokens"
```

---

### Task 4: Auth router

**Files:**
- Create: `backend/routers/auth_router.py`

- [ ] **Step 1: Create backend/routers/auth_router.py**

```python
from fastapi import APIRouter, HTTPException
from backend.auth import verify_password, create_token
from backend.models.schemas import LoginRequest, LoginResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    if not verify_password(req.password):
        raise HTTPException(status_code=401, detail="Wrong password")
    return LoginResponse(token=create_token())
```

- [ ] **Step 2: Commit**

```bash
git add backend/routers/auth_router.py
git commit -m "feat: login endpoint"
```

---

### Task 5: Sessions CRUD router

**Files:**
- Create: `backend/routers/sessions.py`

- [ ] **Step 1: Create backend/routers/sessions.py**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/routers/sessions.py
git commit -m "feat: sessions CRUD endpoints"
```

---

### Task 6: Templates router

**Files:**
- Create: `backend/routers/templates.py`

- [ ] **Step 1: Create backend/routers/templates.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from backend.database import get_db
from backend.auth import require_auth
from backend.models.template import Template
from backend.models.schemas import TemplateCreate

router = APIRouter(prefix="/api/templates", tags=["templates"], dependencies=[Depends(require_auth)])


def _template_to_response(t: Template) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "agents": t.agents or [],
        "settings": t.settings or {},
        "mode": t.mode,
        "problem_statement_template": t.problem_statement_template,
        "canvas_state": t.canvas_state or {},
        "is_default": t.is_default,
        "created_at": t.created_at.isoformat() if t.created_at else "",
    }


@router.get("")
def list_templates(db: DBSession = Depends(get_db)):
    templates = db.query(Template).order_by(Template.created_at.desc()).all()
    return [_template_to_response(t) for t in templates]


@router.post("", status_code=201)
def create_template(req: TemplateCreate, db: DBSession = Depends(get_db)):
    template = Template(
        name=req.name,
        description=req.description,
        agents=[a.model_dump() for a in req.agents],
        settings=req.settings.model_dump(),
        mode=req.mode,
        problem_statement_template=req.problem_statement_template,
        canvas_state=req.canvas_state,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _template_to_response(template)


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: str, db: DBSession = Depends(get_db)):
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default template")
    db.delete(template)
    db.commit()
```

- [ ] **Step 2: Commit**

```bash
git add backend/routers/templates.py
git commit -m "feat: templates CRUD endpoints"
```

---

### Task 7: Upload router

**Files:**
- Create: `backend/routers/upload.py`

- [ ] **Step 1: Create backend/routers/upload.py**

```python
import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from backend.auth import require_auth

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")
MAX_UPLOAD_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "10")) * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

router = APIRouter(prefix="/api/upload", tags=["upload"], dependencies=[Depends(require_auth)])


@router.post("")
async def upload_document(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed. Allowed: {ALLOWED_EXTENSIONS}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max {MAX_UPLOAD_SIZE // (1024*1024)}MB")

    doc_id = str(uuid.uuid4())
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")

    async with aiofiles.open(filepath, "wb") as f:
        await f.write(content)

    return {"doc_id": doc_id, "filename": file.filename, "size": len(content)}
```

- [ ] **Step 2: Commit**

```bash
git add backend/routers/upload.py
git commit -m "feat: document upload endpoint"
```

---

### Task 8: FastAPI main app

**Files:**
- Create: `backend/main.py`

- [ ] **Step 1: Create backend/main.py**

```python
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db
from backend.routers import auth_router, sessions, templates, upload


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Seed default template if not exists
    from backend.database import SessionLocal
    from backend.models.template import Template
    db = SessionLocal()
    try:
        default = db.query(Template).filter(Template.is_default == True).first()
        if not default:
            from backend.engine.default_personas import LEMNISCA_DEFAULT_AGENTS
            db.add(Template(
                name="Lemnisca Default",
                description="6-agent fermentation brainstorming panel",
                agents=LEMNISCA_DEFAULT_AGENTS,
                settings={
                    "max_rounds": 50,
                    "temperature": 0.70,
                    "gate_start_round": 10,
                    "overseer_interval": 10,
                    "min_rounds_before_convergence": 45,
                    "prd_panel_rounds": 10,
                },
                mode="product",
                is_default=True,
            ))
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="Symposium", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(sessions.router)
app.include_router(templates.router)
app.include_router(upload.router)
```

- [ ] **Step 2: Create backend/engine/default_personas.py** (extract from lemnisca_panel.py)

This file holds the 6 Lemnisca default agent configs. Extract the persona strings from `Example Run/lemnisca_panel.py` lines 1504-1843 and structure them as a list of dicts.

```python
"""Default Lemnisca agent configurations — extracted from lemnisca_panel_v7.py."""

PERSONA_VETERAN = """You are the FERMENTATION SCALE-UP AND TROUBLESHOOTING VETERAN...."""  # Full text from lemnisca_panel.py:1504-1562

PERSONA_OPS = """You are the MANUFACTURING / SITE OPERATIONS LEADER...."""  # Full text from lemnisca_panel.py:1564-1617

PERSONA_MSAT = """You are the TECHNICAL SERVICES / MSAT TROUBLESHOOTING LEAD...."""  # Full text from lemnisca_panel.py:1619-1674

PERSONA_PRODUCT = """You are the INDUSTRIAL DIGITAL PRODUCT THINKER...."""  # Full text from lemnisca_panel.py:1676-1729

PERSONA_OUTSIDER = """You are the FIRST-PRINCIPLES OUTSIDER...."""  # Full text from lemnisca_panel.py:1731-1783

PERSONA_PROFESSOR = """You are the BIOCHEMICAL ENGINEERING PROFESSOR-PRACTITIONER...."""  # Full text from lemnisca_panel.py:1785-1843

# IMPORTANT: When implementing, copy the FULL verbatim persona text from
# Example Run/lemnisca_panel.py for each persona variable above.
# The abbreviated text here is just a placeholder for the plan.

LEMNISCA_DEFAULT_AGENTS = [
    {
        "id": "default_veteran",
        "name": "Fermentation_Veteran",
        "model": "gemini-3.1-pro-preview",
        "persona": PERSONA_VETERAN,
        "tools": [],
        "role_tag": "Domain Expert",
        "canvas_position": {"x": 100, "y": 200},
    },
    {
        "id": "default_ops",
        "name": "Ops_Leader",
        "model": "gemini-3.1-pro-preview",
        "persona": PERSONA_OPS,
        "tools": [],
        "role_tag": "Operations",
        "canvas_position": {"x": 300, "y": 100},
    },
    {
        "id": "default_msat",
        "name": "MSAT_Lead",
        "model": "gemini-3.1-pro-preview",
        "persona": PERSONA_MSAT,
        "tools": [],
        "role_tag": "User Advocate",
        "canvas_position": {"x": 500, "y": 200},
    },
    {
        "id": "default_product",
        "name": "Product_Thinker",
        "model": "gemini-3.1-pro-preview",
        "persona": PERSONA_PRODUCT,
        "tools": [],
        "role_tag": "Product",
        "canvas_position": {"x": 300, "y": 400},
    },
    {
        "id": "default_outsider",
        "name": "First_Principles_Outsider",
        "model": "gemini-3.1-pro-preview",
        "persona": PERSONA_OUTSIDER,
        "tools": [],
        "role_tag": "Challenger",
        "canvas_position": {"x": 100, "y": 400},
    },
    {
        "id": "default_professor",
        "name": "BioChem_Professor",
        "model": "gemini-3.1-pro-preview",
        "persona": PERSONA_PROFESSOR,
        "tools": [],
        "role_tag": "Scientific Rigor",
        "canvas_position": {"x": 500, "y": 400},
    },
]
```

- [ ] **Step 3: Verify server starts**

Run: `cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium && python -m uvicorn backend.main:app --port 8000 &` then `sleep 2 && curl http://localhost:8000/docs` then kill the server.
Expected: FastAPI Swagger UI HTML response

- [ ] **Step 4: Commit**

```bash
git add backend/main.py backend/engine/default_personas.py
git commit -m "feat: FastAPI app with CORS, lifespan, default template seeding"
```

---

## Phase 2: Engine Modularization

This phase extracts the brainstorming engine from `Example Run/lemnisca_panel.py` into the `backend/engine/` package. Each module maps directly to a section of the original file.

### Task 9: Engine config and client factory

**Files:**
- Create: `backend/engine/config.py`
- Create: `backend/engine/clients.py`

- [ ] **Step 1: Create backend/engine/config.py**

```python
"""Session configuration — replaces hardcoded constants from lemnisca_panel.py:57-100."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EngineConfig:
    """All configurable parameters for a brainstorming session."""
    gemini_api_key: str
    problem_statement: str
    agents: list[dict]  # list of AgentConfig dicts
    mode: str = "product"  # "product" or "problem_discussion"

    max_rounds: int = 50
    temperature: float = 0.70
    main_model: str = "gemini-3.1-pro-preview"
    support_model: str = "gemini-2.5-flash"

    gate_start_round: int = 10
    overseer_interval: int = 10
    min_rounds_before_convergence: int = 45
    rolling_summary_threshold: int = 70
    prd_panel_rounds: int = 10

    # Derived at runtime
    agent_names: list[str] = field(default_factory=list)
    prd_panel_names: list[str] = field(default_factory=list)

    # Artifact schedule: {round_num: (section_name, section_num)}
    artifact_schedule: dict = field(default_factory=lambda: {
        20: ("C-Level Verdicts", 1),
        40: ("Product Concepts Proposed and Killed", 2),
        55: ("Architectural Decisions", 3),
        65: ("Physics and Logic Engine Constraints", 4),
        75: ("Design Constraints and Rejections", 5),
    })

    convergence_keywords: list[str] = field(default_factory=lambda: [
        "i agree", "exactly right", "well said", "nothing to add",
        "session complete", "spec is locked", "build it", "we are done",
        "meeting adjourned", "lock the spec", "stop brainstorming", "get this built",
    ])

    consensus_phrases: list[str] = field(default_factory=lambda: [
        "spec is locked", "session complete", "build it", "we are done here",
        "meeting adjourned", "get this built", "stop brainstorming", "start coding",
    ])

    def __post_init__(self):
        self.agent_names = [a["name"] for a in self.agents]
        # Default PRD panel: first 4 agents, or all if fewer than 4
        if not self.prd_panel_names:
            self.prd_panel_names = self.agent_names[:4]
        # Scale artifact schedule to session length
        if self.max_rounds <= 30:
            self.artifact_schedule = {
                10: ("C-Level Verdicts", 1),
                20: ("Key Decisions", 2),
            }
        elif self.max_rounds <= 60:
            self.artifact_schedule = {
                15: ("C-Level Verdicts", 1),
                30: ("Product Concepts Proposed and Killed", 2),
                45: ("Architectural Decisions", 3),
            }
```

- [ ] **Step 2: Create backend/engine/clients.py**

```python
"""Gemini model client factory — from lemnisca_panel.py:106-122."""

from autogen_ext.models.openai import OpenAIChatCompletionClient


def make_client(
    model: str,
    api_key: str,
    temperature: float = 0.70,
) -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model=model,
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        temperature=temperature,
        model_capabilities={"vision": False, "function_calling": False, "json_output": False},
    )
```

- [ ] **Step 3: Commit**

```bash
git add backend/engine/config.py backend/engine/clients.py
git commit -m "feat: engine config dataclass and Gemini client factory"
```

---

### Task 10: Gate, selector, convergence modules

**Files:**
- Create: `backend/engine/gate.py`
- Create: `backend/engine/selector.py`
- Create: `backend/engine/convergence.py`

- [ ] **Step 1: Create backend/engine/gate.py**

Extracted from `lemnisca_panel.py:148-212`. The speech gate asks an LLM whether an agent has a new contribution. Returns `(should_speak: bool, claim: str)`.

```python
"""Speech gate — pre-commit: state specific claim or SKIP.
Extracted from lemnisca_panel.py:148-212."""

import asyncio
from typing import Tuple
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

_GATE_PROMPT = """\
You are {agent_name} in an expert brainstorming panel.

Recent discussion (last 10 messages):
{recent_messages}

Before speaking, state in ONE SENTENCE the specific new argument, challenge,
refinement, or counter-example you will contribute that has NOT already been
clearly made above.

A valid contribution must be:
  · A genuinely new angle or specific challenge
  · Tied to YOUR persona's specific expertise and role
  · Something not already said or clearly implied above

These do NOT qualify:
  · "I agree and want to add..." (validation loop)
  · Restating someone else's point in different words
  · General endorsement of the current direction

If you cannot honestly identify a new contribution, respond exactly:
SKIP

Your one sentence (or SKIP):\
"""


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt < max_retries:
                wait = delays[min(attempt, len(delays) - 1)]
                await asyncio.sleep(wait)
            else:
                pass
    return None


async def run_speech_gate(
    support_agent: AssistantAgent,
    agent_name: str,
    messages: list,
    all_agent_names: list[str],
) -> Tuple[bool, str]:
    recent = [
        m for m in messages[-12:]
        if isinstance(getattr(m, "content", ""), str)
        and getattr(m, "source", "") not in ["system"]
    ]
    recent_text = "\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:200]}"
        for m in recent
    )
    prompt = _GATE_PROMPT.format(agent_name=agent_name, recent_messages=recent_text)

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label=f"gate_{agent_name}")
    if response is None:
        return True, ""

    claim = (response.chat_message.content or "").strip() if response.chat_message else ""
    if not claim or claim.upper().startswith("SKIP"):
        return False, ""

    # Lightweight 5-word overlap check
    recent_lower = " ".join(getattr(m, "content", "").lower() for m in recent)
    words = claim.lower().split()
    if len(words) >= 6:
        for i in range(len(words) - 4):
            if " ".join(words[i: i + 5]) in recent_lower:
                return False, claim

    return True, claim
```

- [ ] **Step 2: Create backend/engine/selector.py**

Extracted from `lemnisca_panel.py:250-332`. Hybrid selector: rotation floor + LLM contextual pick.

```python
"""Hybrid selector — rotation floor + LLM contextual pick.
Extracted from lemnisca_panel.py:250-332."""

import asyncio
from typing import Optional
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

_SELECTOR_PROMPT = """\
Select the next speaker from these eligible candidates:
{candidates}

Last speaker: {last_speaker}
Last message (first 200 chars): "{last_message_preview}"
Current phase: {phase_context}

Choose who adds the most value right now:
  · Strong claim just made       → select someone who challenges it
  · Product concept proposed     → prefer product/operations thinkers
  · Discussion too abstract      → prefer domain experts
  · Converging too fast          → prefer challengers/outsiders
  · Technical/mechanistic claim  → prefer scientific rigor agents

Respond with ONLY the exact name of one candidate. No explanation.\
"""


def _phase_context(turn: int, max_rounds: int) -> str:
    pct = turn / max(max_rounds, 1)
    if pct <= 0.2:
        return "Phase 1 — stake positions, raise all perspectives"
    elif pct <= 0.45:
        return "Phase 2 — cross-debate, force disagreement"
    elif pct <= 0.65:
        return "Phase 3 — converge on 2-4 named concepts"
    elif pct <= 0.85:
        return "Phase 4 — stress-test shortlist, punch holes, rank"
    else:
        return "Phase 5 — final refinement, nail interaction model and output format"


def _last_persona_speaker(messages: list, agent_names: list[str]) -> Optional[str]:
    for m in reversed(messages):
        if getattr(m, "source", "") in agent_names:
            return getattr(m, "source")
    return None


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


async def hybrid_selector(
    support_agent: AssistantAgent,
    messages: list,
    last_spoke: dict,
    turn_counter: int,
    agent_names: list[str],
    max_rounds: int,
    forced_next: Optional[str] = None,
) -> str:
    if forced_next and forced_next in agent_names:
        last_spoke[forced_next] = turn_counter
        return forced_next

    last_speaker = _last_persona_speaker(messages, agent_names)
    candidates = [p for p in agent_names if p != last_speaker]

    # Rotation floor: mandatory if waiting 4+ turns
    mandatory = [p for p in candidates if (turn_counter - last_spoke.get(p, 0)) >= 4]
    if mandatory:
        chosen = min(mandatory, key=lambda p: last_spoke.get(p, 0))
        last_spoke[chosen] = turn_counter
        return chosen

    sorted_cands = sorted(candidates, key=lambda p: last_spoke.get(p, 0))

    last_preview = ""
    for m in reversed(messages):
        if getattr(m, "source", "") in agent_names:
            last_preview = getattr(m, "content", "")[:200].replace("\n", " ")
            break

    prompt = _SELECTOR_PROMPT.format(
        candidates="\n".join(f"- {c}" for c in sorted_cands),
        last_speaker=last_speaker or "none",
        last_message_preview=last_preview,
        phase_context=_phase_context(turn_counter, max_rounds),
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label="selector")
    if response and response.chat_message:
        raw = response.chat_message.content.strip()
        for persona in sorted_cands:
            if persona.lower() in raw.lower():
                last_spoke[persona] = turn_counter
                return persona

    chosen = sorted_cands[0]
    last_spoke[chosen] = turn_counter
    return chosen
```

- [ ] **Step 3: Create backend/engine/convergence.py**

Extracted from `lemnisca_panel.py:218-243`.

```python
"""Convergence detection and consensus termination.
Extracted from lemnisca_panel.py:218-243."""


def check_convergence(
    messages: list,
    agent_names: list[str],
    convergence_keywords: list[str],
    window: int = 3,
) -> bool:
    recent = [
        m for m in messages[-(window * 2):]
        if getattr(m, "source", "") in agent_names
    ][-window:]
    if len(recent) < window:
        return False
    return sum(
        1 for m in recent
        if any(kw in getattr(m, "content", "").lower() for kw in convergence_keywords)
    ) >= window


def check_consensus_termination(
    messages: list,
    round_num: int,
    c_coverage: dict,
    agent_names: list[str],
    consensus_phrases: list[str],
    min_rounds: int,
) -> bool:
    if round_num < min_rounds:
        return False
    if c_coverage and not all(c_coverage.values()):
        return False
    signalling = set()
    for m in messages:
        src = getattr(m, "source", "")
        content = getattr(m, "content", "").lower()
        if src in agent_names and any(p in content for p in consensus_phrases):
            signalling.add(src)
    return len(signalling) >= 3
```

- [ ] **Step 4: Commit**

```bash
git add backend/engine/gate.py backend/engine/selector.py backend/engine/convergence.py
git commit -m "feat: speech gate, hybrid selector, and convergence detection modules"
```

---

### Task 11: Overseer, artifact, summary modules

**Files:**
- Create: `backend/engine/overseer.py`
- Create: `backend/engine/artifact.py`
- Create: `backend/engine/summary.py`

- [ ] **Step 1: Create backend/engine/overseer.py**

Extracted from `lemnisca_panel.py:352-425`. Generates constraint reminder messages at regular intervals.

```python
"""Overseer middleware — constraint reminder every N rounds.
Extracted from lemnisca_panel.py:352-425."""

import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

_OVERSEER_PROMPT = """\
You are a background session monitor for a brainstorming panel.
Write a terse structured context reminder for round {round_num}. Max 180 words.

Coverage status:
{coverage_status}

Recent messages (last 8):
{recent_messages}

Phase: {phase_context}

Output in this EXACT format:

[OVERSEER — Round {round_num}]

KEY CONSTRAINTS (from problem statement):
  - Remind agents of the core constraints from the problem statement
  - Keep agents focused on the defined scope

COVERAGE STATUS:
{coverage_status}

PHASE DIRECTIVE: {phase_context}

REMINDER: Challenge specifically. Disagree by name.
State something your persona uniquely sees — or stay silent.\
"""


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


def _format_coverage(coverage: dict) -> str:
    if not coverage:
        return "  No specific coverage tracking for this session."
    return "\n".join(
        f"  {k}: {'Covered' if v else 'NOT YET — must be addressed'}"
        for k, v in coverage.items()
    )


async def generate_overseer_reminder(
    support_agent: AssistantAgent,
    messages: list,
    round_num: int,
    coverage: dict,
    phase_context: str,
    agent_names: list[str],
) -> TextMessage:
    recent = [
        m for m in messages[-10:]
        if getattr(m, "source", "") not in ["system", "Overseer"]
        and isinstance(getattr(m, "content", ""), str)
    ]
    recent_text = "\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:150]}"
        for m in recent
    )
    coverage_status = _format_coverage(coverage)
    prompt = _OVERSEER_PROMPT.format(
        round_num=round_num,
        coverage_status=coverage_status,
        recent_messages=recent_text,
        phase_context=phase_context,
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label="overseer")
    if response and response.chat_message:
        content = response.chat_message.content
    else:
        content = (
            f"[OVERSEER — Round {round_num}]\n\n"
            f"COVERAGE STATUS:\n{coverage_status}\n\n"
            "REMINDER: Challenge specifically. Disagree by name."
        )
    return TextMessage(content=content, source="Overseer")
```

- [ ] **Step 2: Create backend/engine/artifact.py**

Extracted from `lemnisca_panel.py:428-522`. Builds the Living Artifact progressively at milestone rounds.

```python
"""Living Artifact — built progressively at milestone rounds.
Extracted from lemnisca_panel.py:428-522."""

import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

_ARTIFACT_PROMPT = """\
Build Section {section_num} of the session Living Artifact.
Section: {section_name} | Written at round: {round_num}

Do NOT repeat content from existing sections.

Relevant agent discussion (last 25 messages):
{relevant_excerpt}

Existing artifact:
{existing_artifact}

Output ONLY this new section (max 300 words):

SECTION {section_num} — {section_name} (Round {round_num})
──────────────────────────────────────────────────────────
[Each item: label · decision/status · who said it · one-line reason]
[Be specific. Include persona names. No vague summaries.]\
"""

_FINALIZE_PROMPT = """\
Write the final section of the Living Artifact.

Recent discussion:
{recent_text}

SECTION {section_num} — UNRESOLVED QUESTIONS (Session End)
──────────────────────────────────────────────────────────
List 3-5 specific open questions that:
  · Remain genuinely unanswered
  · Would materially change direction if answered differently
  · Are specific enough to be actionable research tasks

Format:
Q[n]: [question]
  Why it matters: [one sentence]
  Who raised it: [persona name]

Max 3-5 questions. No generic filler.\
"""


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


async def update_living_artifact(
    support_agent: AssistantAgent,
    messages: list,
    living_artifact: dict,
    round_num: int,
    artifact_schedule: dict,
    agent_names: list[str],
) -> dict:
    section_info = artifact_schedule.get(round_num)
    if not section_info:
        return living_artifact

    section_name, section_num = section_info
    agent_msgs = [
        m for m in messages
        if getattr(m, "source", "") in agent_names
        and isinstance(getattr(m, "content", ""), str)
    ]
    relevant = agent_msgs[max(0, len(agent_msgs) - 25):]
    relevant_text = "\n\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:350]}"
        for m in relevant
    )
    existing = "\n\n".join(living_artifact.values()) if living_artifact else "None yet."
    prompt = _ARTIFACT_PROMPT.format(
        section_num=section_num, section_name=section_name, round_num=round_num,
        relevant_excerpt=relevant_text, existing_artifact=existing,
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label=f"artifact_s{section_num}")
    if response and response.chat_message:
        living_artifact[section_name] = response.chat_message.content
    return living_artifact


async def finalize_artifact(
    support_agent: AssistantAgent,
    messages: list,
    living_artifact: dict,
    agent_names: list[str],
) -> dict:
    recent_agent = [m for m in messages[-20:] if getattr(m, "source", "") in agent_names]
    recent_text = "\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:250]}"
        for m in recent_agent
    )
    section_num = len(living_artifact) + 1
    prompt = _FINALIZE_PROMPT.format(recent_text=recent_text, section_num=section_num)

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label="artifact_final")
    if response and response.chat_message:
        living_artifact["Unresolved Questions"] = response.chat_message.content
    return living_artifact
```

- [ ] **Step 3: Create backend/engine/summary.py**

Extracted from `lemnisca_panel.py:526-570`. Rolling summary for long sessions.

```python
"""Rolling summary — auto-activates above threshold rounds.
Extracted from lemnisca_panel.py:526-570."""

import asyncio
from typing import Optional
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


async def generate_rolling_summary(
    support_agent: AssistantAgent,
    messages: list,
    agent_names: list[str],
    n: int = 30,
) -> str:
    agent_msgs = [m for m in messages if getattr(m, "source", "") in agent_names][:n]
    text = "\n\n".join(
        f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:400]}"
        for m in agent_msgs
    )
    prompt = (
        f"Compress the first {n} agent messages of this brainstorm into a "
        "structured 200-word summary.\n\n"
        "Focus on: key positions championed/rejected, product concepts that emerged, "
        "key agreements/disagreements, constraints established.\n\n"
        f"Discussion:\n{text}\n\n"
        f"Output:\nEARLY DISCUSSION SUMMARY (Rounds 1-{n}):\n"
        "[200 words max. Bullet points.]"
    )

    async def _call():
        return await support_agent.on_messages(
            [TextMessage(content=prompt, source="system")], CancellationToken()
        )

    response = await _call_with_retry(_call, label="rolling_summary")
    if response and response.chat_message:
        return response.chat_message.content
    return ""


def build_agent_context(
    messages: list,
    rolling_summary: Optional[str],
    agent_names: list[str],
) -> list:
    if not rolling_summary:
        return messages
    agent_msgs = [m for m in messages if getattr(m, "source", "") in agent_names]
    if len(agent_msgs) <= 30:
        return messages
    cutoff = agent_msgs[29]
    try:
        idx = messages.index(cutoff)
    except ValueError:
        return messages
    return [messages[0], TextMessage(content=rolling_summary, source="system")] + messages[idx + 1:]
```

- [ ] **Step 4: Commit**

```bash
git add backend/engine/overseer.py backend/engine/artifact.py backend/engine/summary.py
git commit -m "feat: overseer, living artifact, and rolling summary engine modules"
```

---

### Task 12: Main brainstorm loop

**Files:**
- Create: `backend/engine/brainstorm.py`

- [ ] **Step 1: Create backend/engine/brainstorm.py**

This is the core loop from `lemnisca_panel.py:577-714`, refactored to:
1. Accept an `EngineConfig` instead of globals
2. Accept a `callback` function for WebSocket events instead of `print()`
3. Be fully async

```python
"""Main brainstorm loop — extracted from lemnisca_panel.py:577-714.

Key change: all print() calls replaced with an async callback function
that emits structured events (for WebSocket streaming)."""

import asyncio
from typing import Optional, Callable, Awaitable
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client
from backend.engine.gate import run_speech_gate
from backend.engine.selector import hybrid_selector, _phase_context
from backend.engine.convergence import check_convergence, check_consensus_termination
from backend.engine.overseer import generate_overseer_reminder
from backend.engine.artifact import update_living_artifact, finalize_artifact
from backend.engine.summary import generate_rolling_summary, build_agent_context

# Type for the event callback: async fn(event_type: str, data: dict)
EventCallback = Callable[[str, dict], Awaitable[None]]


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


def _build_agents(config: EngineConfig):
    """Build AutoGen AssistantAgent instances from config agent dicts."""
    agents = []
    for agent_conf in config.agents:
        client = make_client(
            model=agent_conf["model"],
            api_key=config.gemini_api_key,
            temperature=config.temperature,
        )
        agents.append(AssistantAgent(
            name=agent_conf["name"],
            description=agent_conf.get("role_tag", agent_conf["name"]),
            system_message=agent_conf["persona"],
            model_client=client,
        ))
    return agents


def _update_coverage(coverage: dict, content: str):
    """Track which C-levels have been mentioned."""
    for key in list(coverage.keys()):
        if key in content:
            coverage[key] = True


async def run_brainstorm(
    config: EngineConfig,
    emit: EventCallback,
) -> tuple[list, dict, dict]:
    """Run the main brainstorming session.

    Args:
        config: Session configuration
        emit: Async callback for streaming events

    Returns:
        (messages, stats, living_artifact)
    """
    agents = _build_agents(config)
    agent_map = {a.name: a for a in agents}

    support_client = make_client(
        model=config.support_model,
        api_key=config.gemini_api_key,
        temperature=0.3,
    )
    support_agent = AssistantAgent(
        name="Support",
        description="Gate, selector, overseer support agent",
        system_message="You are a precise, concise assistant. Follow instructions exactly. Output only what is asked.",
        model_client=support_client,
    )

    messages = [TextMessage(content=config.problem_statement, source="user")]
    last_spoke = {name: 0 for name in config.agent_names}
    persona_turns = {name: 0 for name in config.agent_names}
    # Initialize coverage tracking (empty dict if no specific coverage needed)
    c_coverage = {}
    living_artifact = {}
    rolling_summary = None

    turn_counter = 0
    gate_skips = 0
    overseer_injections = 0
    convergence_triggers = 0
    forced_next = None

    await emit("session_started", {"max_rounds": config.max_rounds})

    while turn_counter < config.max_rounds:

        # ── OVERSEER INJECTION
        if turn_counter > 0 and turn_counter % config.overseer_interval == 0:
            phase = _phase_context(turn_counter, config.max_rounds)
            overseer_msg = await generate_overseer_reminder(
                support_agent, messages, turn_counter, c_coverage, phase, config.agent_names,
            )
            messages.append(overseer_msg)
            overseer_injections += 1
            await emit("overseer", {
                "content": overseer_msg.content,
                "round": turn_counter,
            })

        # ── ROLLING SUMMARY
        if turn_counter > config.rolling_summary_threshold and rolling_summary is None:
            rolling_summary = await generate_rolling_summary(
                support_agent, messages, config.agent_names,
            )

        # ── HYBRID SELECTOR
        chosen = await hybrid_selector(
            support_agent, messages, last_spoke, turn_counter,
            config.agent_names, config.max_rounds, forced_next,
        )
        forced_next = None

        # ── SPEECH GATE
        if turn_counter >= config.gate_start_round:
            should_speak, claim = await run_speech_gate(
                support_agent, chosen, messages, config.agent_names,
            )
            if not should_speak:
                gate_skips += 1
                await emit("gate_skip", {"agent": chosen, "round": turn_counter})
                last_speaker = None
                for m in reversed(messages):
                    if getattr(m, "source", "") in config.agent_names:
                        last_speaker = getattr(m, "source")
                        break
                fallback = sorted(
                    [p for p in config.agent_names if p != chosen and p != last_speaker],
                    key=lambda p: last_spoke.get(p, 0),
                )
                chosen = fallback[0] if fallback else chosen

        # ── AGENT CALL
        agent = agent_map[chosen]
        context = build_agent_context(messages, rolling_summary, config.agent_names)

        await emit("agent_message", {
            "source": chosen,
            "round": turn_counter + 1,
            "streaming": True,
            "content": "",
        })

        async def _agent_call(a=agent, ctx=context):
            return await a.on_messages(ctx, CancellationToken())

        response = await _call_with_retry(_agent_call, label=chosen)
        if response is None or response.chat_message is None:
            turn_counter += 1
            continue

        content = response.chat_message.content or ""
        msg = TextMessage(content=content, source=chosen)
        messages.append(msg)
        last_spoke[chosen] = turn_counter
        persona_turns[chosen] += 1
        turn_counter += 1

        await emit("agent_message", {
            "source": chosen,
            "round": turn_counter,
            "streaming": False,
            "content": content,
        })

        # ── LIVING ARTIFACT UPDATE
        if turn_counter in config.artifact_schedule:
            living_artifact = await update_living_artifact(
                support_agent, messages, living_artifact, turn_counter,
                config.artifact_schedule, config.agent_names,
            )
            section_info = config.artifact_schedule[turn_counter]
            await emit("artifact_section", {
                "section_num": section_info[1],
                "section_name": section_info[0],
                "content": living_artifact.get(section_info[0], ""),
            })

        _update_coverage(c_coverage, content)

        await emit("stats", {
            "rounds": turn_counter,
            "gate_skips": gate_skips,
            "overseer_injections": overseer_injections,
            "c_coverage": c_coverage,
        })

        # ── CONVERGENCE DETECTION
        if turn_counter >= 10 and check_convergence(
            messages, config.agent_names, config.convergence_keywords,
        ):
            convergence_triggers += 1
            if turn_counter < config.min_rounds_before_convergence:
                # Force a challenger agent — pick last agent in list (typically outsider)
                forced_next = config.agent_names[-1] if config.agent_names else None
                await emit("convergence", {"forced_next": forced_next})
            else:
                forced_next = config.agent_names[-2] if len(config.agent_names) > 1 else config.agent_names[0]
                await emit("convergence", {"forced_next": forced_next})

        # ── CONSENSUS TERMINATION
        if check_consensus_termination(
            messages, turn_counter, c_coverage,
            config.agent_names, config.consensus_phrases,
            config.min_rounds_before_convergence,
        ):
            await emit("session_complete", {"terminated_by": "consensus"})
            break

    living_artifact = await finalize_artifact(
        support_agent, messages, living_artifact, config.agent_names,
    )

    stats = {
        "total_rounds": turn_counter,
        "gate_skips": gate_skips,
        "overseer_injections": overseer_injections,
        "convergence_triggers": convergence_triggers,
        "c_coverage": c_coverage,
        "persona_turns": persona_turns,
        "rolling_summary_used": rolling_summary is not None,
        "terminated_by": "consensus" if turn_counter < config.max_rounds else "max_rounds",
    }

    return messages, stats, living_artifact
```

- [ ] **Step 2: Commit**

```bash
git add backend/engine/brainstorm.py
git commit -m "feat: main brainstorm loop with event callbacks for WebSocket streaming"
```

---

### Task 13: PRD panel, conclusion, synthesis, and outputs

**Files:**
- Create: `backend/engine/prd_panel.py`
- Create: `backend/engine/conclusion.py`
- Create: `backend/engine/synthesis.py`
- Create: `backend/engine/outputs.py`

- [ ] **Step 1: Create backend/engine/prd_panel.py**

Extracted from `lemnisca_panel.py:720-815`. PRD mini-panel for Product mode.

```python
"""PRD mini-panel — 4 agents, pure rotation, reads artifact not transcript.
Extracted from lemnisca_panel.py:720-815."""

from typing import Callable, Awaitable
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client

EventCallback = Callable[[str, dict], Awaitable[None]]

_PRD_TASK = """\
You are now in a focused PRD co-authoring session.

The main brainstorm is complete. Here is the full structured decision artifact:

{artifact_text}

Your goal: debate and finalize a build-ready product specification in {panel_rounds} rounds.

RULES:
  · Do NOT reopen concept debates — those are closed
  · Disagree openly within your owned sections
  · Every section must be agreed or flagged as contested
  · PRD is done when all agents can defend every section to engineering

Start: each state the ONE thing you most want to sharpen in the artifact.\
"""


async def run_prd_mini_panel(
    config: EngineConfig,
    living_artifact: dict,
    emit: EventCallback,
) -> list:
    await emit("phase_transition", {"phase": "prd_panel"})

    artifact_text = (
        "\n\n".join(f"== {name} ==\n{content}" for name, content in living_artifact.items())
        if living_artifact
        else "Artifact not yet fully populated. Work from your understanding of the brainstorm."
    )

    task = _PRD_TASK.format(artifact_text=artifact_text, panel_rounds=config.prd_panel_rounds)

    prd_agents = []
    for agent_conf in config.agents:
        if agent_conf["name"] in config.prd_panel_names:
            client = make_client(
                model=agent_conf["model"],
                api_key=config.gemini_api_key,
                temperature=config.temperature,
            )
            prd_agents.append(AssistantAgent(
                name=agent_conf["name"],
                description=agent_conf.get("role_tag", agent_conf["name"]),
                system_message=agent_conf["persona"],
                model_client=client,
            ))

    if not prd_agents:
        return []

    prd_last_spoke = {a.name: 0 for a in prd_agents}
    prd_turn = [0]
    prd_names = [a.name for a in prd_agents]

    def prd_selector(msgs):
        prd_turn[0] += 1
        last = None
        for m in reversed(msgs):
            if getattr(m, "source", "") in prd_names:
                last = getattr(m, "source")
                break
        cands = sorted(
            [p for p in prd_names if p != last],
            key=lambda p: prd_last_spoke.get(p, 0),
        )
        chosen = cands[0]
        prd_last_spoke[chosen] = prd_turn[0]
        return chosen

    main_client = make_client(
        model=config.main_model,
        api_key=config.gemini_api_key,
        temperature=config.temperature,
    )

    team = SelectorGroupChat(
        participants=prd_agents,
        model_client=main_client,
        termination_condition=MaxMessageTermination(config.prd_panel_rounds + 2),
        selector_prompt="Select next speaker by pure rotation.",
        selector_func=prd_selector,
    )

    result = await Console(team.run_stream(task=task))
    panel_messages = [m for m in result.messages if getattr(m, "source", "") in prd_names]

    for msg in panel_messages:
        await emit("agent_message", {
            "source": getattr(msg, "source", ""),
            "round": 0,
            "streaming": False,
            "content": getattr(msg, "content", ""),
        })

    return panel_messages
```

- [ ] **Step 2: Create backend/engine/conclusion.py**

New module for Problem Discussion mode — generates a Conclusion Report instead of a PRD.

```python
"""Conclusion report generation for Problem Discussion mode."""

from typing import Callable, Awaitable
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client

EventCallback = Callable[[str, dict], Awaitable[None]]

_CONCLUSION_PROMPT = """\
Read the brainstorming discussion and the Living Artifact, then produce a
structured Conclusion Report.

LIVING ARTIFACT:
{artifact_text}

DISCUSSION (last 30 messages):
{discussion_text}

Output using this exact template:

# Conclusion Report

## 1. Problem Restated
[One paragraph restating the problem as understood after discussion]

## 2. Key Agreements
[What the panel definitively concluded — bullet points]

## 3. Key Tensions
[Where disagreement remained and why it matters — bullet points]

## 4. Recommended Direction
[The panel's strongest supported conclusion — 1-2 paragraphs]

## 5. Dissenting Views
[Minority positions worth preserving — bullet points with who held them]

## 6. Open Questions
[Specific questions that would change direction if answered — bullet points]

## 7. Next Steps
[Concrete actions — bullet points]\
"""


async def generate_conclusion(
    config: EngineConfig,
    messages: list,
    living_artifact: dict,
    emit: EventCallback,
) -> str:
    await emit("phase_transition", {"phase": "conclusion"})

    artifact_text = (
        "\n\n".join(f"== {name} ==\n{content}" for name, content in living_artifact.items())
        if living_artifact
        else "No artifact sections generated."
    )
    agent_msgs = [m for m in messages if getattr(m, "source", "") in config.agent_names]
    recent = agent_msgs[-30:]
    discussion_text = "\n\n".join(
        f"[{getattr(m, 'source', '?')}]:\n{getattr(m, 'content', '').strip()}"
        for m in recent
    )

    client = make_client(
        model=config.main_model,
        api_key=config.gemini_api_key,
        temperature=config.temperature,
    )
    writer = AssistantAgent(
        name="ConclusionWriter",
        system_message="You produce structured conclusion reports from brainstorming discussions. Follow the template exactly.",
        model_client=client,
    )

    prompt = _CONCLUSION_PROMPT.format(
        artifact_text=artifact_text,
        discussion_text=discussion_text,
    )

    response = await writer.on_messages(
        [TextMessage(content=prompt, source="user")], CancellationToken()
    )

    return response.chat_message.content if response and response.chat_message else "Conclusion generation failed."
```

- [ ] **Step 3: Create backend/engine/synthesis.py**

Extracted from `lemnisca_panel.py:822-958`. Generates synthesis report + build-ready PRD from mini-panel discussion.

```python
"""Synthesis report + PRD generation from mini-panel discussion.
Extracted from lemnisca_panel.py:822-958."""

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.clients import make_client

_SYNTHESIS_SYSTEM = (
    "You are a Senior Strategy Synthesizer reading a focused PRD co-authoring "
    "discussion. The main decisions have already been made. Extract, clarify, and "
    "structure what was agreed and what remains open. Every sentence must earn its place."
)

_SYNTHESIS_PROMPT = """\
Read the PRD panel discussion and produce a structured synthesis report.

## 1. Consensus Areas
What did the panel agree on definitively?
Name the product, user, trigger, inputs, output format specifically.

## 2. Key Tensions Resolved
Where did agents disagree? How resolved? What remains contested?

## 3. Winning Product Concept
  - Product name and one-line description
  - Product form
  - Target pain
  - Why it works
  - Confidence: High / Medium / Exploratory

## 4. What Was Explicitly Ruled Out
From the main brainstorm, confirmed rejected. Be blunt.

## 5. Open Questions Before Build Starts
What the PRD panel flagged as unresolved.

PRD PANEL DISCUSSION:
{panel_text}\
"""

_PRD_SYSTEM = (
    "You are producing a build-ready Product Requirements Document. "
    "Follow the template exactly. Do not add or skip sections. "
    "If a section was contested and unresolved, state the disagreement explicitly."
)

_PRD_PROMPT = """\
Extract the build-ready PRD from the PRD panel discussion.

PRD PANEL DISCUSSION:
{panel_text}

Output using this exact template:

# [Product Name] — Build-Ready PRD

## 1. Product Name and One-Line Description

## 2. Target User
  Who exactly:
  In what situation:
  What they have available at that moment:

## 3. Trigger Moment
  What just happened that makes them open this:

## 4. Required Inputs
  [List each. Must be sparse.]

## 5. Processing Logic
  What the tool computes or structures:
  Mathematical or logical basis:
  What it explicitly CANNOT infer:

## 6. Output
  Exact format:
  What the user receives:
  How it is used or shared:

## 7. Trust Mechanism
  Why the user believes this output:
  Why it is defensible:

## 8. v1 Scope
  Explicitly IN for v1:
  Explicitly OUT for v1 (with reason):

## 9. Wedge Mechanic
  How this tool creates a path to paid engagement:

## 10. Team Ownership

## 11. Unresolved Questions Before Build Starts
  [3-5 specific questions only]\
"""


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    import asyncio
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


async def generate_synthesis_and_prd(
    model: str,
    api_key: str,
    temperature: float,
    panel_messages: list,
) -> tuple[str, str]:
    """Generate both synthesis report and build-ready PRD.

    Returns:
        (synthesis_text, prd_text)
    """
    panel_text = "\n\n".join(
        f"[{getattr(m, 'source', '?')}]:\n{getattr(m, 'content', '').strip()}"
        for m in panel_messages
    )

    client = make_client(model=model, api_key=api_key, temperature=temperature)
    synthesizer = AssistantAgent(name="Synthesizer", system_message=_SYNTHESIS_SYSTEM, model_client=client)
    prd_writer = AssistantAgent(name="PRD_Writer", system_message=_PRD_SYSTEM, model_client=client)

    async def _synth():
        return await synthesizer.on_messages(
            [TextMessage(content=_SYNTHESIS_PROMPT.format(panel_text=panel_text), source="user")],
            CancellationToken(),
        )
    synth_r = await _call_with_retry(_synth, label="synthesizer")
    synthesis_text = synth_r.chat_message.content if synth_r and synth_r.chat_message else "Synthesis failed."

    async def _prd():
        return await prd_writer.on_messages(
            [TextMessage(content=_PRD_PROMPT.format(panel_text=panel_text), source="user")],
            CancellationToken(),
        )
    prd_r = await _call_with_retry(_prd, label="prd_writer")
    prd_text = prd_r.chat_message.content if prd_r and prd_r.chat_message else "PRD generation failed."

    return synthesis_text, prd_text
```

- [ ] **Step 4: Create backend/engine/outputs.py**

Extracted from `lemnisca_panel.py:960-998`. Builds output file content (not filesystem writes — the session runner saves to DB).

```python
"""Output file content builders.
Extracted from lemnisca_panel.py:960-998."""

from datetime import datetime, timezone


def build_transcript(messages: list, stats: dict, agent_names: list[str]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Brainstorming Panel — Full Transcript\n\n",
        f"**Date:** {ts}  |  **Model:** {stats.get('model', 'gemini')}\n",
        f"**Rounds:** {stats['total_rounds']}/{stats.get('max_rounds', '?')}  |  "
        f"**Terminated:** {stats['terminated_by']}\n",
        f"**Gate skips:** {stats['gate_skips']}  |  "
        f"**Overseer injections:** {stats['overseer_injections']}\n\n---\n\n",
    ]
    msg_num = 0
    for msg in messages:
        src = getattr(msg, "source", "Unknown")
        content = getattr(msg, "content", "")
        if not (isinstance(content, str) and content.strip()):
            continue
        if src == "Overseer":
            lines.append(f"### [OVERSEER]\n\n{content.strip()}\n\n---\n\n")
        elif src in agent_names:
            msg_num += 1
            lines.append(f"### [{msg_num}] {src}\n\n{content.strip()}\n\n---\n\n")
    return "".join(lines)


def build_artifact(living_artifact: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    lines = ["# Brainstorming Panel — Living Artifact\n\n", f"*{ts}*\n\n" + "=" * 60 + "\n\n"]
    for section_name, content in living_artifact.items():
        lines.append(f"{content.strip()}\n\n{'─' * 60}\n\n")
    return "".join(lines)
```

- [ ] **Step 5: Commit**

```bash
git add backend/engine/prd_panel.py backend/engine/conclusion.py backend/engine/synthesis.py backend/engine/outputs.py
git commit -m "feat: PRD panel, conclusion report, synthesis, and output builders"
```

---

## Phase 3: WebSocket Session Runner

### Task 14: Session runner service + WebSocket endpoint

**Files:**
- Create: `backend/services/session_runner.py`
- Modify: `backend/routers/sessions.py` (add run + WS endpoint)

- [ ] **Step 1: Create backend/services/session_runner.py**

This service wraps the engine and manages WebSocket communication.

```python
"""Session runner — wraps engine, emits WebSocket events."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

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
        """Send a structured event over WebSocket."""
        await self.ws.send_json({"type": event_type, **data})

    async def run(self):
        """Execute the full session: brainstorm → PRD/conclusion → outputs."""
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

        # Update session status
        session.status = SessionStatus.running
        self.db.commit()

        try:
            # Phase 1: Main brainstorm
            messages, stats, living_artifact = await run_brainstorm(config, self.emit)

            # Phase 2: PRD panel or Conclusion
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

            # Save to DB
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
```

- [ ] **Step 2: Add WebSocket and run endpoints to sessions router**

Append to `backend/routers/sessions.py`:

```python
import os
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from backend.services.session_runner import SessionRunner


@router.post("/{session_id}/run")
def start_session_run(session_id: str, db: DBSession = Depends(get_db)):
    """Returns the WebSocket URL to connect to for live streaming."""
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

    # Get DB session
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        session = db.query(Session).filter(Session.id == session_id).first()
        if not session:
            await websocket.send_json({"type": "error", "message": "Session not found"})
            await websocket.close()
            return

        api_key = os.environ.get("GEMINI_API_KEY", "")
        # Check if client sent API key in first message
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

        runner = SessionRunner(websocket, session, db, api_key)
        await runner.run()

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
def export_session(session_id: str, db: DBSession = Depends(get_db)):
    """Returns session outputs for download."""
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.outputs:
        raise HTTPException(status_code=400, detail="Session has no outputs")
    return {"outputs": session.outputs}
```

- [ ] **Step 3: Commit**

```bash
git add backend/services/session_runner.py backend/routers/sessions.py
git commit -m "feat: session runner service with WebSocket streaming endpoint"
```

---

### Task 15: AI suggestion endpoints

**Files:**
- Create: `backend/services/ai_suggest.py`
- Create: `backend/routers/suggest.py`

- [ ] **Step 1: Create backend/services/ai_suggest.py**

```python
"""AI suggestion service — problem statement + persona review + agent suggestions."""

import os
import json
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.clients import make_client

SUPPORT_MODEL = "gemini-2.5-flash"


async def _ask(system: str, user_prompt: str, api_key: str) -> str:
    client = make_client(model=SUPPORT_MODEL, api_key=api_key, temperature=0.3)
    agent = AssistantAgent(name="Suggester", system_message=system, model_client=client)
    response = await agent.on_messages(
        [TextMessage(content=user_prompt, source="user")], CancellationToken()
    )
    return response.chat_message.content if response and response.chat_message else ""


async def inline_suggestion(text: str, api_key: str) -> str:
    """Returns a single short suggestion for the problem statement."""
    system = "You are a brainstorming session design assistant. Be concise and specific."
    prompt = (
        f'The user is writing a problem statement for a multi-agent AI brainstorming session.\n'
        f'Current text: "{text}"\n'
        f'Identify the single most important missing element or improvement.\n'
        f'Return ONE short suggestion (max 15 words). If the text is already strong, return "NONE".'
    )
    return await _ask(system, prompt, api_key)


async def review_problem_statement(text: str, api_key: str) -> dict:
    """Returns structured review of a problem statement."""
    system = "You are a brainstorming session design expert."
    prompt = (
        f'Review this problem statement for a multi-agent AI discussion session:\n\n'
        f'"{text}"\n\n'
        f'Return JSON:\n'
        f'{{\n'
        f'  "clarity": "Low|Medium|High",\n'
        f'  "clarity_reason": "one sentence",\n'
        f'  "missing": ["list of missing elements"],\n'
        f'  "suggestions": ["2-3 specific improvement suggestions"],\n'
        f'  "rewrite": "improved version of the problem statement"\n'
        f'}}'
    )
    raw = await _ask(system, prompt, api_key)
    try:
        # Try to parse JSON from the response
        # Handle markdown code blocks
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return {"clarity": "Unknown", "clarity_reason": raw, "missing": [], "suggestions": [], "rewrite": ""}


async def review_persona(agent_name: str, persona_text: str, other_agents: list, api_key: str) -> dict:
    """Returns structured review of an agent persona."""
    system = "You are an expert in designing AI agent personas for structured debate."
    others_summary = "\n".join(f"- {a.get('name', '?')}: {a.get('persona', '')[:100]}" for a in other_agents)
    prompt = (
        f'Review this agent persona:\n\n'
        f'Name: {agent_name}\n'
        f'Persona: {persona_text}\n\n'
        f'Other agents on this panel:\n{others_summary}\n\n'
        f'Return JSON:\n'
        f'{{\n'
        f'  "missing_sections": ["list of missing must-contain sections"],\n'
        f'  "distinctiveness": "High|Medium|Low",\n'
        f'  "distinctiveness_reason": "one sentence",\n'
        f'  "suggestions": ["2-3 specific improvement suggestions"]\n'
        f'}}'
    )
    raw = await _ask(system, prompt, api_key)
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return {"missing_sections": [], "distinctiveness": "Unknown", "distinctiveness_reason": raw, "suggestions": []}


async def suggest_agents(problem_statement: str, mode: str, api_key: str) -> list:
    """Returns 3-5 suggested agent archetypes based on the problem statement."""
    system = "You are an expert in designing multi-agent brainstorming panels."
    prompt = (
        f'Based on this problem statement, suggest 4 agent archetypes that would '
        f'create productive tension and cover the most important perspectives.\n\n'
        f'Problem: "{problem_statement}"\n'
        f'Mode: {mode}\n\n'
        f'Return a JSON array of 4 agents:\n'
        f'[{{\n'
        f'  "name": "short descriptive name (use underscores, no spaces)",\n'
        f'  "mission": "one sentence mission",\n'
        f'  "persona": "full persona text",\n'
        f'  "model": "gemini-3.1-pro-preview",\n'
        f'  "role_tag": "short role label",\n'
        f'  "rationale": "one sentence — why this agent adds value"\n'
        f'}}]'
    )
    raw = await _ask(system, prompt, api_key)
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return []
```

- [ ] **Step 2: Create backend/routers/suggest.py**

```python
import os
from fastapi import APIRouter, Depends, HTTPException
from backend.auth import require_auth
from backend.models.schemas import ReviewRequest, AgentSuggestionRequest
from backend.services import ai_suggest

router = APIRouter(prefix="/api/suggest", tags=["suggest"], dependencies=[Depends(require_auth)])


def _get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    return key


@router.post("/inline")
async def inline_suggestion(body: dict):
    text = body.get("text", "")
    if not text:
        return {"suggestion": "NONE"}
    result = await ai_suggest.inline_suggestion(text, _get_api_key())
    return {"suggestion": result}


@router.post("/review")
async def review(req: ReviewRequest):
    api_key = _get_api_key()
    if req.review_type == "problem_statement":
        result = await ai_suggest.review_problem_statement(req.text, api_key)
    elif req.review_type == "persona":
        result = await ai_suggest.review_persona(
            req.other_agents[0].get("name", "") if req.other_agents else "",
            req.text,
            req.other_agents,
            api_key,
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid review_type")
    return {"result": result}


@router.post("/agents")
async def suggest_agents(req: AgentSuggestionRequest):
    result = await ai_suggest.suggest_agents(req.problem_statement, req.mode, _get_api_key())
    return {"agents": result}
```

- [ ] **Step 3: Add suggest router to main app**

Add to `backend/main.py` imports:
```python
from backend.routers import auth_router, sessions, templates, upload, suggest
```

Add to router includes:
```python
app.include_router(suggest.router)
```

- [ ] **Step 4: Commit**

```bash
git add backend/services/ai_suggest.py backend/routers/suggest.py backend/main.py
git commit -m "feat: AI suggestion endpoints for inline, review, and agent suggestions"
```

---

### Task 16: Export service (ZIP download)

**Files:**
- Create: `backend/services/export.py`
- Modify: `backend/routers/sessions.py` (update export endpoint)

- [ ] **Step 1: Create backend/services/export.py**

```python
"""ZIP export for session outputs."""

import io
import zipfile


def create_zip(outputs: dict[str, str], session_name: str) -> bytes:
    """Create a ZIP archive from session output files.

    Args:
        outputs: {filename: content} dict
        session_name: used as prefix for the ZIP

    Returns:
        bytes of the ZIP file
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in outputs.items():
            zf.writestr(f"{session_name}/{filename}", content)
    buffer.seek(0)
    return buffer.read()
```

- [ ] **Step 2: Update export endpoint in sessions router**

Replace the existing `/export` endpoint in `backend/routers/sessions.py`:

```python
from fastapi.responses import Response
from backend.services.export import create_zip


@router.get("/{session_id}/export")
def export_session(session_id: str, format: str = "json", db: DBSession = Depends(get_db)):
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
```

- [ ] **Step 3: Commit**

```bash
git add backend/services/export.py backend/routers/sessions.py
git commit -m "feat: ZIP export for session outputs"
```

---

## Phase 4: Frontend Skeleton

### Task 17: React + Vite + TypeScript + Tailwind setup

**Files:**
- Create: `frontend/` directory with Vite scaffolding

- [ ] **Step 1: Scaffold Vite project**

Run:
```bash
cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install react-router-dom zustand @xyflow/react react-markdown
```

- [ ] **Step 2: Configure Tailwind**

Replace `frontend/src/index.css`:
```css
@import "tailwindcss";

:root {
  --color-navy: #0a0e1a;
  --color-navy-light: #141929;
  --color-navy-lighter: #1e2438;
  --color-teal: #2dd4bf;
  --color-teal-dim: #14b8a6;
  --color-surface: #1a1f33;
  --color-border: #2a3050;
  --color-text: #e2e8f0;
  --color-text-dim: #94a3b8;
}

body {
  margin: 0;
  background-color: var(--color-navy);
  color: var(--color-text);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}

* {
  box-sizing: border-box;
}

::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: var(--color-navy);
}
::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 3px;
}
```

- [ ] **Step 3: Configure Vite proxy**

Update `frontend/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        ws: true,
      },
    },
  },
})
```

- [ ] **Step 4: Verify frontend starts**

Run: `cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium/frontend && npm run dev &`
Expected: Vite dev server starts on localhost:5173

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: React + Vite + TypeScript + Tailwind frontend scaffolding"
```

---

### Task 18: API client and auth store

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/store/authStore.ts`

- [ ] **Step 1: Create frontend/src/api/client.ts**

```typescript
const BASE = '/api';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('symposium_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem('symposium_token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: (path: string) => request(path, { method: 'DELETE' }),
};
```

- [ ] **Step 2: Create frontend/src/store/authStore.ts**

```typescript
import { create } from 'zustand';
import { api } from '../api/client';

interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  login: (password: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('symposium_token'),
  isAuthenticated: !!localStorage.getItem('symposium_token'),

  login: async (password: string) => {
    const { token } = await api.post<{ token: string }>('/auth/login', { password });
    localStorage.setItem('symposium_token', token);
    set({ token, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem('symposium_token');
    set({ token: null, isAuthenticated: false });
  },

  checkAuth: () => {
    const token = localStorage.getItem('symposium_token');
    set({ token, isAuthenticated: !!token });
  },
}));
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/ frontend/src/store/authStore.ts
git commit -m "feat: API client with auth token and Zustand auth store"
```

---

### Task 19: Login page

**Files:**
- Create: `frontend/src/pages/Login.tsx`

- [ ] **Step 1: Create frontend/src/pages/Login.tsx**

```tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export default function Login() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(password);
      navigate('/sessions');
    } catch {
      setError('Wrong password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--color-navy)' }}>
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm p-8 rounded-xl"
        style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-border)' }}
      >
        <h1 className="text-2xl font-bold mb-2" style={{ color: 'var(--color-teal)' }}>
          Symposium
        </h1>
        <p className="text-sm mb-6" style={{ color: 'var(--color-text-dim)' }}>
          Multi-agent brainstorming canvas
        </p>

        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Enter password"
          autoFocus
          className="w-full px-4 py-3 rounded-lg text-sm mb-4 outline-none focus:ring-2"
          style={{
            background: 'var(--color-navy)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text)',
            focusRingColor: 'var(--color-teal)',
          }}
        />

        {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

        <button
          type="submit"
          disabled={loading || !password}
          className="w-full py-3 rounded-lg font-medium text-sm transition-colors disabled:opacity-50"
          style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}
        >
          {loading ? 'Signing in...' : 'Enter'}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Login.tsx
git commit -m "feat: login page with dark theme"
```

---

### Task 20: Sessions list page

**Files:**
- Create: `frontend/src/pages/Sessions.tsx`
- Create: `frontend/src/store/sessionStore.ts`

- [ ] **Step 1: Create frontend/src/store/sessionStore.ts**

```typescript
import { create } from 'zustand';
import { api } from '../api/client';

export interface AgentConfig {
  id: string;
  name: string;
  model: string;
  persona: string;
  tools: string[];
  role_tag: string | null;
  canvas_position: { x: number; y: number };
}

export interface SessionSettings {
  max_rounds: number;
  temperature: number;
  gate_start_round: number;
  overseer_interval: number;
  min_rounds_before_convergence: number;
  prd_panel_rounds: number;
}

export interface SessionData {
  id: string;
  name: string;
  mode: string;
  problem_statement: string;
  agents: AgentConfig[];
  settings: SessionSettings;
  status: string;
  created_at: string;
  completed_at: string | null;
  canvas_state: Record<string, unknown>;
  document_ids: string[];
  outputs: Record<string, string> | null;
}

interface SessionState {
  sessions: SessionData[];
  currentSession: SessionData | null;
  loading: boolean;
  fetchSessions: () => Promise<void>;
  fetchSession: (id: string) => Promise<void>;
  createSession: (data: Partial<SessionData>) => Promise<SessionData>;
  updateSession: (id: string, data: Partial<SessionData>) => Promise<void>;
  deleteSession: (id: string) => Promise<void>;
  setCurrentSession: (session: SessionData | null) => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessions: [],
  currentSession: null,
  loading: false,

  fetchSessions: async () => {
    set({ loading: true });
    const sessions = await api.get<SessionData[]>('/sessions');
    set({ sessions, loading: false });
  },

  fetchSession: async (id: string) => {
    const session = await api.get<SessionData>(`/sessions/${id}`);
    set({ currentSession: session });
  },

  createSession: async (data) => {
    const session = await api.post<SessionData>('/sessions', {
      name: data.name || 'New Session',
      mode: data.mode || 'product',
      problem_statement: data.problem_statement || '',
      agents: data.agents || [],
      settings: data.settings || {},
      canvas_state: data.canvas_state || {},
    });
    set((s) => ({ sessions: [session, ...s.sessions] }));
    return session;
  },

  updateSession: async (id, data) => {
    const updated = await api.patch<SessionData>(`/sessions/${id}`, data);
    set((s) => ({
      sessions: s.sessions.map((sess) => (sess.id === id ? updated : sess)),
      currentSession: s.currentSession?.id === id ? updated : s.currentSession,
    }));
  },

  deleteSession: async (id) => {
    await api.delete(`/sessions/${id}`);
    set((s) => ({
      sessions: s.sessions.filter((sess) => sess.id !== id),
      currentSession: s.currentSession?.id === id ? null : s.currentSession,
    }));
  },

  setCurrentSession: (session) => set({ currentSession: session }),
}));
```

- [ ] **Step 2: Create frontend/src/pages/Sessions.tsx**

```tsx
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSessionStore } from '../store/sessionStore';
import { useAuthStore } from '../store/authStore';

export default function Sessions() {
  const { sessions, loading, fetchSessions, createSession, deleteSession } = useSessionStore();
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleNew = async () => {
    const session = await createSession({ name: 'New Session' });
    navigate(`/canvas/${session.id}`);
  };

  const statusColor = (status: string) => {
    switch (status) {
      case 'complete': return '#2dd4bf';
      case 'running': return '#fbbf24';
      case 'error': return '#f87171';
      default: return '#94a3b8';
    }
  };

  return (
    <div className="min-h-screen p-8" style={{ background: 'var(--color-navy)' }}>
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--color-teal)' }}>Symposium</h1>
            <p className="text-sm" style={{ color: 'var(--color-text-dim)' }}>
              Multi-agent brainstorming sessions
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleNew}
              className="px-4 py-2 rounded-lg font-medium text-sm"
              style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}
            >
              + New Session
            </button>
            <button
              onClick={() => { logout(); navigate('/login'); }}
              className="px-4 py-2 rounded-lg text-sm"
              style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}
            >
              Logout
            </button>
          </div>
        </div>

        {loading ? (
          <p style={{ color: 'var(--color-text-dim)' }}>Loading...</p>
        ) : sessions.length === 0 ? (
          <div
            className="text-center py-16 rounded-xl"
            style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-border)' }}
          >
            <p className="text-lg mb-2" style={{ color: 'var(--color-text-dim)' }}>No sessions yet</p>
            <p className="text-sm mb-4" style={{ color: 'var(--color-text-dim)' }}>
              Create your first brainstorming session
            </p>
            <button
              onClick={handleNew}
              className="px-4 py-2 rounded-lg font-medium text-sm"
              style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}
            >
              + New Session
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between p-4 rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
                style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-border)' }}
                onClick={() => s.status === 'complete' ? navigate(`/results/${s.id}`) : navigate(`/canvas/${s.id}`)}
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ background: statusColor(s.status) }}
                  />
                  <div>
                    <p className="font-medium">{s.name}</p>
                    <p className="text-xs" style={{ color: 'var(--color-text-dim)' }}>
                      {s.mode === 'product' ? 'Product Discussion' : 'Problem Discussion'} · {new Date(s.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className="text-xs px-2 py-1 rounded"
                    style={{ background: 'var(--color-navy)', color: statusColor(s.status) }}
                  >
                    {s.status}
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}
                    className="text-xs px-2 py-1 rounded hover:bg-red-900/30 text-red-400"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/store/sessionStore.ts frontend/src/pages/Sessions.tsx
git commit -m "feat: sessions list page with create/delete and session store"
```

---

### Task 21: Router setup in App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx`
- Create: `frontend/src/pages/Canvas.tsx` (placeholder)
- Create: `frontend/src/pages/Results.tsx` (placeholder)

- [ ] **Step 1: Create placeholder pages**

`frontend/src/pages/Canvas.tsx`:
```tsx
export default function Canvas() {
  return <div className="min-h-screen p-8" style={{ background: 'var(--color-navy)' }}>
    <h1 style={{ color: 'var(--color-teal)' }}>Canvas — Coming Soon</h1>
  </div>;
}
```

`frontend/src/pages/Results.tsx`:
```tsx
export default function Results() {
  return <div className="min-h-screen p-8" style={{ background: 'var(--color-navy)' }}>
    <h1 style={{ color: 'var(--color-teal)' }}>Results — Coming Soon</h1>
  </div>;
}
```

- [ ] **Step 2: Update App.tsx**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import Login from './pages/Login';
import Sessions from './pages/Sessions';
import Canvas from './pages/Canvas';
import Results from './pages/Results';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/sessions" element={<ProtectedRoute><Sessions /></ProtectedRoute>} />
        <Route path="/canvas/:id" element={<ProtectedRoute><Canvas /></ProtectedRoute>} />
        <Route path="/results/:id" element={<ProtectedRoute><Results /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/sessions" />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 3: Update main.tsx**

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 4: Verify app loads with routing**

Run: `cd frontend && npm run dev`
Navigate to `http://localhost:5173/login` — should see login form.
Expected: Dark themed login page renders

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: router setup with login, sessions, canvas, results pages"
```

---

## Phase 5: Canvas UI

### Task 22: Canvas store (Zustand + React Flow state)

**Files:**
- Create: `frontend/src/store/canvasStore.ts`

- [ ] **Step 1: Create frontend/src/store/canvasStore.ts**

```typescript
import { create } from 'zustand';
import { Node, Edge, applyNodeChanges, applyEdgeChanges, NodeChange, EdgeChange } from '@xyflow/react';

export interface AgentNodeData {
  id: string;
  name: string;
  model: string;
  persona: string;
  tools: string[];
  role_tag: string | null;
  isActive?: boolean;
  [key: string]: unknown;
}

interface CanvasState {
  nodes: Node<AgentNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
  drawerOpen: boolean;

  setNodes: (nodes: Node<AgentNodeData>[]) => void;
  setEdges: (edges: Edge[]) => void;
  onNodesChange: (changes: NodeChange<Node<AgentNodeData>>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;

  addAgent: (agent: AgentNodeData, position: { x: number; y: number }) => void;
  removeAgent: (nodeId: string) => void;
  updateAgent: (nodeId: string, data: Partial<AgentNodeData>) => void;
  setActiveAgent: (agentName: string | null) => void;

  selectNode: (nodeId: string | null) => void;
  setDrawerOpen: (open: boolean) => void;

  rebuildEdges: () => void;
}

let nodeIdCounter = 0;

export const useCanvasStore = create<CanvasState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  drawerOpen: false,

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  onNodesChange: (changes) => {
    set({ nodes: applyNodeChanges(changes, get().nodes) });
  },
  onEdgesChange: (changes) => {
    set({ edges: applyEdgeChanges(changes, get().edges) });
  },

  addAgent: (agent, position) => {
    const nodeId = `agent-${++nodeIdCounter}`;
    const newNode: Node<AgentNodeData> = {
      id: nodeId,
      type: 'agentNode',
      position,
      data: { ...agent, id: nodeId },
    };
    set((s) => ({ nodes: [...s.nodes, newNode] }));
    get().rebuildEdges();
  },

  removeAgent: (nodeId) => {
    set((s) => ({ nodes: s.nodes.filter((n) => n.id !== nodeId) }));
    get().rebuildEdges();
  },

  updateAgent: (nodeId, data) => {
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n
      ),
    }));
  },

  setActiveAgent: (agentName) => {
    set((s) => ({
      nodes: s.nodes.map((n) => ({
        ...n,
        data: { ...n.data, isActive: n.data.name === agentName },
      })),
    }));
  },

  selectNode: (nodeId) => {
    set({ selectedNodeId: nodeId, drawerOpen: !!nodeId });
  },

  setDrawerOpen: (open) => set({ drawerOpen: open }),

  rebuildEdges: () => {
    const { nodes } = get();
    const edges: Edge[] = [];
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        edges.push({
          id: `e-${nodes[i].id}-${nodes[j].id}`,
          source: nodes[i].id,
          target: nodes[j].id,
          style: { stroke: '#2a3050', strokeWidth: 1 },
          animated: false,
        });
      }
    }
    set({ edges });
  },
}));
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/store/canvasStore.ts
git commit -m "feat: canvas store with React Flow node/edge management"
```

---

### Task 23: AgentNode component

**Files:**
- Create: `frontend/src/components/canvas/AgentNode.tsx`

- [ ] **Step 1: Create frontend/src/components/canvas/AgentNode.tsx**

```tsx
import { memo } from 'react';
import { Handle, Position, NodeProps, type Node } from '@xyflow/react';
import type { AgentNodeData } from '../../store/canvasStore';

type AgentNodeType = Node<AgentNodeData>;

function AgentNode({ data }: NodeProps<AgentNodeType>) {
  const isActive = data.isActive;

  return (
    <div className="flex flex-col items-center">
      <Handle type="target" position={Position.Top} style={{ visibility: 'hidden' }} />

      <div
        className="relative w-20 h-20 rounded-full flex items-center justify-center cursor-pointer transition-all"
        style={{
          background: 'var(--color-navy-lighter)',
          border: `2px solid ${isActive ? 'var(--color-teal)' : 'var(--color-border)'}`,
          boxShadow: isActive ? '0 0 20px rgba(45, 212, 191, 0.4)' : 'none',
        }}
      >
        {isActive && (
          <div
            className="absolute inset-0 rounded-full animate-ping"
            style={{
              border: '2px solid var(--color-teal)',
              opacity: 0.3,
            }}
          />
        )}
        <span className="text-lg font-bold" style={{ color: 'var(--color-teal)' }}>
          {data.name?.charAt(0) || '?'}
        </span>
      </div>

      <p className="mt-2 text-xs font-medium text-center max-w-24 truncate" style={{ color: 'var(--color-text)' }}>
        {data.name || 'Unnamed'}
      </p>

      {data.role_tag && (
        <span
          className="mt-1 text-[10px] px-2 py-0.5 rounded-full"
          style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}
        >
          {data.role_tag}
        </span>
      )}

      <Handle type="source" position={Position.Bottom} style={{ visibility: 'hidden' }} />
    </div>
  );
}

export default memo(AgentNode);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/canvas/AgentNode.tsx
git commit -m "feat: AgentNode component with active speaker pulse animation"
```

---

### Task 24: Agent configuration drawer

**Files:**
- Create: `frontend/src/components/canvas/AgentDrawer.tsx`

- [ ] **Step 1: Create frontend/src/components/canvas/AgentDrawer.tsx**

```tsx
import { useCanvasStore } from '../../store/canvasStore';

const MODELS = [
  { value: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro (Quality)' },
  { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (Fast)' },
];

export default function AgentDrawer() {
  const { nodes, selectedNodeId, drawerOpen, setDrawerOpen, updateAgent, removeAgent } = useCanvasStore();

  const node = nodes.find((n) => n.id === selectedNodeId);
  if (!drawerOpen || !node) return null;

  const data = node.data;

  const update = (field: string, value: unknown) => {
    updateAgent(node.id, { [field]: value });
  };

  return (
    <div
      className="fixed right-0 top-0 h-full w-96 overflow-y-auto z-50 p-6"
      style={{
        background: 'var(--color-navy-light)',
        borderLeft: '1px solid var(--color-border)',
      }}
    >
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-bold" style={{ color: 'var(--color-teal)' }}>
          Agent Config
        </h2>
        <button
          onClick={() => setDrawerOpen(false)}
          className="text-sm px-2 py-1"
          style={{ color: 'var(--color-text-dim)' }}
        >
          Close
        </button>
      </div>

      {/* Agent Name */}
      <label className="block text-xs mb-1" style={{ color: 'var(--color-text-dim)' }}>Name</label>
      <input
        value={data.name || ''}
        onChange={(e) => update('name', e.target.value)}
        className="w-full px-3 py-2 rounded-lg text-sm mb-4 outline-none"
        style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
      />

      {/* Model */}
      <label className="block text-xs mb-1" style={{ color: 'var(--color-text-dim)' }}>Model</label>
      <select
        value={data.model || MODELS[0].value}
        onChange={(e) => update('model', e.target.value)}
        className="w-full px-3 py-2 rounded-lg text-sm mb-4 outline-none"
        style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
      >
        {MODELS.map((m) => (
          <option key={m.value} value={m.value}>{m.label}</option>
        ))}
      </select>

      {/* Role Tag */}
      <label className="block text-xs mb-1" style={{ color: 'var(--color-text-dim)' }}>Role Tag</label>
      <input
        value={data.role_tag || ''}
        onChange={(e) => update('role_tag', e.target.value)}
        placeholder="e.g. Challenger, Domain Expert"
        className="w-full px-3 py-2 rounded-lg text-sm mb-4 outline-none"
        style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
      />

      {/* Persona */}
      <label className="block text-xs mb-1" style={{ color: 'var(--color-text-dim)' }}>Persona Definition</label>
      <textarea
        value={data.persona || ''}
        onChange={(e) => update('persona', e.target.value)}
        rows={12}
        placeholder="Define this agent's background, worldview, what they care about, distrust, how they interact..."
        className="w-full px-3 py-2 rounded-lg text-sm mb-4 outline-none resize-y"
        style={{
          background: 'var(--color-navy)',
          border: '1px solid var(--color-border)',
          color: 'var(--color-text)',
          fontFamily: 'monospace',
        }}
      />

      {/* Web Search Toggle */}
      <div className="flex items-center justify-between mb-6">
        <span className="text-sm" style={{ color: 'var(--color-text)' }}>Web Search</span>
        <button
          onClick={() => {
            const tools = data.tools || [];
            update('tools', tools.includes('web_search')
              ? tools.filter((t: string) => t !== 'web_search')
              : [...tools, 'web_search']);
          }}
          className="px-3 py-1 rounded-full text-xs"
          style={{
            background: (data.tools || []).includes('web_search') ? 'var(--color-teal)' : 'var(--color-navy)',
            color: (data.tools || []).includes('web_search') ? 'var(--color-navy)' : 'var(--color-text-dim)',
            border: '1px solid var(--color-border)',
          }}
        >
          {(data.tools || []).includes('web_search') ? 'ON' : 'OFF'}
        </button>
      </div>

      {/* Delete Agent */}
      <button
        onClick={() => { removeAgent(node.id); setDrawerOpen(false); }}
        className="w-full py-2 rounded-lg text-sm text-red-400 hover:bg-red-900/20 transition-colors"
        style={{ border: '1px solid rgba(248, 113, 113, 0.3)' }}
      >
        Remove Agent
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/canvas/AgentDrawer.tsx
git commit -m "feat: agent configuration drawer with name, model, persona, tools"
```

---

### Task 25: Agent library sidebar

**Files:**
- Create: `frontend/src/components/canvas/AgentLibrary.tsx`

- [ ] **Step 1: Create frontend/src/components/canvas/AgentLibrary.tsx**

```tsx
import { useState, useEffect } from 'react';
import { useCanvasStore, AgentNodeData } from '../../store/canvasStore';
import { api } from '../../api/client';

interface TemplateAgent {
  id: string;
  name: string;
  model: string;
  persona: string;
  tools: string[];
  role_tag: string | null;
  canvas_position: { x: number; y: number };
}

interface Template {
  id: string;
  name: string;
  agents: TemplateAgent[];
  is_default: boolean;
}

export default function AgentLibrary() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [search, setSearch] = useState('');
  const addAgent = useCanvasStore((s) => s.addAgent);
  const nodes = useCanvasStore((s) => s.nodes);

  useEffect(() => {
    api.get<Template[]>('/templates').then(setTemplates).catch(() => {});
  }, []);

  const defaultTemplate = templates.find((t) => t.is_default);
  const libraryAgents = defaultTemplate?.agents || [];

  const filteredAgents = libraryAgents.filter((a) =>
    a.name.toLowerCase().includes(search.toLowerCase()) ||
    (a.role_tag || '').toLowerCase().includes(search.toLowerCase())
  );

  const handleAddBlank = () => {
    const offset = nodes.length * 30;
    addAgent(
      { id: '', name: 'New_Agent', model: 'gemini-3.1-pro-preview', persona: '', tools: [], role_tag: null },
      { x: 250 + offset, y: 250 + offset },
    );
  };

  const handleAddLibraryAgent = (agent: TemplateAgent) => {
    const offset = nodes.length * 30;
    addAgent(
      { id: '', name: agent.name, model: agent.model, persona: agent.persona, tools: agent.tools, role_tag: agent.role_tag },
      { x: agent.canvas_position?.x || (250 + offset), y: agent.canvas_position?.y || (250 + offset) },
    );
  };

  return (
    <div
      className="w-64 h-full overflow-y-auto p-4 flex flex-col gap-3"
      style={{
        background: 'var(--color-navy-light)',
        borderLeft: '1px solid var(--color-border)',
      }}
    >
      <h3 className="text-sm font-bold" style={{ color: 'var(--color-teal)' }}>Agents</h3>

      {/* Blank Agent */}
      <button
        onClick={handleAddBlank}
        className="w-full py-3 rounded-lg text-sm font-medium transition-colors"
        style={{
          background: 'var(--color-navy)',
          border: '2px dashed var(--color-border)',
          color: 'var(--color-text-dim)',
        }}
      >
        + Blank Agent
      </button>

      {/* Search */}
      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search agents..."
        className="w-full px-3 py-2 rounded-lg text-xs outline-none"
        style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
      />

      {/* Library Agents */}
      {defaultTemplate && (
        <div>
          <p className="text-[10px] uppercase tracking-wider mb-2" style={{ color: 'var(--color-text-dim)' }}>
            {defaultTemplate.name}
          </p>
          {filteredAgents.map((agent) => (
            <button
              key={agent.id || agent.name}
              onClick={() => handleAddLibraryAgent(agent)}
              className="w-full text-left p-3 rounded-lg mb-2 hover:opacity-80 transition-opacity"
              style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)' }}
            >
              <p className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                {agent.name.replace(/_/g, ' ')}
              </p>
              {agent.role_tag && (
                <span className="text-[10px]" style={{ color: 'var(--color-teal-dim)' }}>
                  {agent.role_tag}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/canvas/AgentLibrary.tsx
git commit -m "feat: agent library sidebar with blank agent and template agents"
```

---

### Task 26: Setup components (ProblemStatement, ModeSelector, AdvancedSettings)

**Files:**
- Create: `frontend/src/components/setup/ProblemStatement.tsx`
- Create: `frontend/src/components/setup/ModeSelector.tsx`
- Create: `frontend/src/components/setup/AdvancedSettings.tsx`

- [ ] **Step 1: Create frontend/src/components/setup/ProblemStatement.tsx**

```tsx
import { useState } from 'react';

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function ProblemStatement({ value, onChange }: Props) {
  const [charCount, setCharCount] = useState(value.length);

  const handleChange = (text: string) => {
    onChange(text);
    setCharCount(text.length);
  };

  return (
    <div>
      <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-dim)' }}>
        Problem Statement
      </label>
      <textarea
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        rows={6}
        placeholder="Describe the problem, goal, or question this session should address..."
        className="w-full px-3 py-2 rounded-lg text-sm outline-none resize-y"
        style={{
          background: 'var(--color-navy)',
          border: '1px solid var(--color-border)',
          color: 'var(--color-text)',
        }}
      />
      <div className="flex justify-between mt-1">
        <span className="text-[10px]" style={{ color: charCount < 100 ? '#f87171' : 'var(--color-text-dim)' }}>
          {charCount} chars {charCount < 100 ? '(100+ recommended)' : ''}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create frontend/src/components/setup/ModeSelector.tsx**

```tsx
interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function ModeSelector({ value, onChange }: Props) {
  return (
    <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--color-navy)' }}>
      {[
        { key: 'product', label: 'Product Discussion' },
        { key: 'problem_discussion', label: 'Problem Discussion' },
      ].map((mode) => (
        <button
          key={mode.key}
          onClick={() => onChange(mode.key)}
          className="flex-1 py-2 rounded-md text-xs font-medium transition-colors"
          style={{
            background: value === mode.key ? 'var(--color-teal)' : 'transparent',
            color: value === mode.key ? 'var(--color-navy)' : 'var(--color-text-dim)',
          }}
        >
          {mode.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create frontend/src/components/setup/AdvancedSettings.tsx**

```tsx
import { useState } from 'react';
import type { SessionSettings } from '../../store/sessionStore';

interface Props {
  settings: SessionSettings;
  onChange: (settings: SessionSettings) => void;
}

const ROUND_OPTIONS = [
  { value: 20, cost: '~$0.51' },
  { value: 50, cost: '~$1.27' },
  { value: 80, cost: '~$2.40' },
  { value: 100, cost: '~$3.80' },
];

export default function AdvancedSettings({ settings, onChange }: Props) {
  const [expanded, setExpanded] = useState(false);

  const update = (key: keyof SessionSettings, value: number) => {
    onChange({ ...settings, [key]: value });
  };

  return (
    <div>
      {/* Rounds selector */}
      <label className="block text-xs font-medium mb-2" style={{ color: 'var(--color-text-dim)' }}>Rounds</label>
      <div className="flex gap-2 mb-4">
        {ROUND_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => update('max_rounds', opt.value)}
            className="flex-1 py-2 rounded-lg text-center"
            style={{
              background: settings.max_rounds === opt.value ? 'var(--color-teal)' : 'var(--color-navy)',
              color: settings.max_rounds === opt.value ? 'var(--color-navy)' : 'var(--color-text-dim)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div className="text-sm font-bold">{opt.value}</div>
            <div className="text-[10px]">{opt.cost}</div>
          </button>
        ))}
      </div>

      {/* Advanced toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-xs mb-3"
        style={{ color: 'var(--color-text-dim)' }}
      >
        {expanded ? '- Hide' : '+ Show'} Advanced Settings
      </button>

      {expanded && (
        <div className="space-y-3">
          <div>
            <label className="text-[10px] block" style={{ color: 'var(--color-text-dim)' }}>Gate Start Round</label>
            <input
              type="number"
              value={settings.gate_start_round}
              onChange={(e) => update('gate_start_round', parseInt(e.target.value))}
              className="w-full px-2 py-1 rounded text-sm"
              style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            />
          </div>
          <div>
            <label className="text-[10px] block" style={{ color: 'var(--color-text-dim)' }}>Overseer Interval</label>
            <input
              type="number"
              value={settings.overseer_interval}
              onChange={(e) => update('overseer_interval', parseInt(e.target.value))}
              className="w-full px-2 py-1 rounded text-sm"
              style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            />
          </div>
          <div>
            <label className="text-[10px] block" style={{ color: 'var(--color-text-dim)' }}>Temperature ({settings.temperature})</label>
            <input
              type="range"
              min="0.3"
              max="1.0"
              step="0.05"
              value={settings.temperature}
              onChange={(e) => update('temperature', parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
          <div>
            <label className="text-[10px] block" style={{ color: 'var(--color-text-dim)' }}>Min Rounds Before Consensus</label>
            <input
              type="number"
              value={settings.min_rounds_before_convergence}
              onChange={(e) => update('min_rounds_before_convergence', parseInt(e.target.value))}
              className="w-full px-2 py-1 rounded text-sm"
              style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/setup/
git commit -m "feat: setup components — problem statement, mode selector, advanced settings"
```

---

### Task 27: Full Canvas page (setup mode)

**Files:**
- Modify: `frontend/src/pages/Canvas.tsx`

- [ ] **Step 1: Rewrite frontend/src/pages/Canvas.tsx**

```tsx
import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ReactFlow, Background, BackgroundVariant, type Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useSessionStore, type SessionSettings } from '../store/sessionStore';
import { useCanvasStore, type AgentNodeData } from '../store/canvasStore';
import AgentNode from '../components/canvas/AgentNode';
import AgentDrawer from '../components/canvas/AgentDrawer';
import AgentLibrary from '../components/canvas/AgentLibrary';
import ProblemStatement from '../components/setup/ProblemStatement';
import ModeSelector from '../components/setup/ModeSelector';
import AdvancedSettings from '../components/setup/AdvancedSettings';

const nodeTypes = { agentNode: AgentNode };

const defaultSettings: SessionSettings = {
  max_rounds: 50,
  temperature: 0.70,
  gate_start_round: 10,
  overseer_interval: 10,
  min_rounds_before_convergence: 45,
  prd_panel_rounds: 10,
};

export default function Canvas() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentSession, fetchSession, updateSession } = useSessionStore();
  const { nodes, edges, onNodesChange, onEdgesChange, selectNode, setNodes, addAgent, rebuildEdges } = useCanvasStore();

  const [problemStatement, setProblemStatement] = useState('');
  const [mode, setMode] = useState('product');
  const [settings, setSettings] = useState<SessionSettings>(defaultSettings);
  const [isLive, setIsLive] = useState(false);

  // Load session data
  useEffect(() => {
    if (id) fetchSession(id);
  }, [id, fetchSession]);

  // Populate canvas from session
  useEffect(() => {
    if (currentSession) {
      setProblemStatement(currentSession.problem_statement || '');
      setMode(currentSession.mode || 'product');
      setSettings({ ...defaultSettings, ...currentSession.settings });

      // Load agents onto canvas
      if (currentSession.agents?.length > 0 && nodes.length === 0) {
        currentSession.agents.forEach((agent) => {
          addAgent(
            { id: agent.id, name: agent.name, model: agent.model, persona: agent.persona, tools: agent.tools, role_tag: agent.role_tag },
            agent.canvas_position || { x: 250, y: 250 },
          );
        });
      }
    }
  }, [currentSession]);

  // Auto-save on changes
  const handleSave = useCallback(async () => {
    if (!id) return;
    const agentConfigs = nodes.map((n: Node<AgentNodeData>) => ({
      id: n.id,
      name: n.data.name,
      model: n.data.model,
      persona: n.data.persona,
      tools: n.data.tools,
      role_tag: n.data.role_tag,
      canvas_position: n.position,
    }));
    await updateSession(id, {
      problem_statement: problemStatement,
      mode: mode as 'product' | 'problem_discussion',
      agents: agentConfigs as any,
      settings,
    });
  }, [id, nodes, problemStatement, mode, settings, updateSession]);

  const handleBeginSymposium = async () => {
    await handleSave();
    setIsLive(true);
    // Live mode will be implemented in Phase 6
  };

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    selectNode(node.id);
  };

  if (!currentSession) {
    return <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--color-navy)', color: 'var(--color-text-dim)' }}>Loading...</div>;
  }

  return (
    <div className="h-screen flex" style={{ background: 'var(--color-navy)' }}>
      {/* Left sidebar — Setup */}
      <div
        className="w-80 h-full overflow-y-auto p-4 flex flex-col gap-4"
        style={{ background: 'var(--color-navy-light)', borderRight: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold" style={{ color: 'var(--color-teal)' }}>Setup</h2>
          <button
            onClick={() => navigate('/sessions')}
            className="text-xs"
            style={{ color: 'var(--color-text-dim)' }}
          >
            Back
          </button>
        </div>

        <ProblemStatement value={problemStatement} onChange={setProblemStatement} />
        <ModeSelector value={mode} onChange={setMode} />
        <AdvancedSettings settings={settings} onChange={setSettings} />

        <button
          onClick={handleSave}
          className="w-full py-2 rounded-lg text-sm"
          style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}
        >
          Save Draft
        </button>

        <button
          onClick={handleBeginSymposium}
          disabled={!problemStatement || nodes.length < 2}
          className="w-full py-3 rounded-lg font-bold text-sm transition-colors disabled:opacity-40"
          style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}
        >
          Begin Symposium
        </button>

        {nodes.length < 2 && (
          <p className="text-[10px]" style={{ color: '#fbbf24' }}>
            Add at least 2 agents to begin
          </p>
        )}
      </div>

      {/* Center — Canvas */}
      <div className="flex-1 h-full">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e2438" />
        </ReactFlow>
      </div>

      {/* Right sidebar — Agent Library */}
      <AgentLibrary />

      {/* Agent config drawer */}
      <AgentDrawer />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Canvas.tsx
git commit -m "feat: full canvas page with setup sidebar, React Flow canvas, agent library"
```

---

## Phase 6: Live Session View

### Task 28: WebSocket hook

**Files:**
- Create: `frontend/src/hooks/useWebSocket.ts`

- [ ] **Step 1: Create frontend/src/hooks/useWebSocket.ts**

```typescript
import { useEffect, useRef, useState, useCallback } from 'react';

export interface WSMessage {
  type: string;
  [key: string]: unknown;
}

interface UseWebSocketOptions {
  sessionId: string;
  apiKey?: string;
  onMessage?: (msg: WSMessage) => void;
}

export function useWebSocket({ sessionId, apiKey, onMessage }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<WSMessage[]>([]);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/sessions/${sessionId}/ws`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      // Send API key if provided
      if (apiKey) {
        ws.send(JSON.stringify({ api_key: apiKey }));
      } else {
        ws.send(JSON.stringify({}));
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        setMessages((prev) => [...prev, msg]);
        onMessage?.(msg);
      } catch {
        // ignore non-JSON
      }
    };

    ws.onclose = () => {
      setConnected(false);
    };

    ws.onerror = () => {
      setConnected(false);
    };
  }, [sessionId, apiKey, onMessage]);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
  }, []);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  return { connect, disconnect, connected, messages };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useWebSocket.ts
git commit -m "feat: WebSocket hook for live session streaming"
```

---

### Task 29: Live feed, artifact panel, stats bar components

**Files:**
- Create: `frontend/src/components/session/LiveFeed.tsx`
- Create: `frontend/src/components/session/ArtifactPanel.tsx`
- Create: `frontend/src/components/session/StatsBar.tsx`

- [ ] **Step 1: Create frontend/src/components/session/LiveFeed.tsx**

```tsx
import { useEffect, useRef } from 'react';
import type { WSMessage } from '../../hooks/useWebSocket';

interface Props {
  messages: WSMessage[];
}

export default function LiveFeed({ messages }: Props) {
  const feedRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef(false);

  useEffect(() => {
    if (!userScrolledUp.current && feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [messages]);

  const handleScroll = () => {
    if (!feedRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = feedRef.current;
    userScrolledUp.current = scrollHeight - scrollTop - clientHeight > 50;
  };

  return (
    <div
      ref={feedRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto p-4 space-y-3"
      style={{ background: 'var(--color-navy)' }}
    >
      {messages.map((msg, i) => {
        if (msg.type === 'agent_message' && !msg.streaming) {
          return (
            <div key={i} className="p-4 rounded-lg" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-border)' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-bold" style={{ color: 'var(--color-teal)' }}>
                  {msg.source as string}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: 'var(--color-navy)', color: 'var(--color-text-dim)' }}>
                  Round {msg.round as number}
                </span>
              </div>
              <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--color-text)', fontFamily: 'monospace', lineHeight: '1.6' }}>
                {msg.content as string}
              </p>
            </div>
          );
        }

        if (msg.type === 'overseer') {
          return (
            <div key={i} className="p-4 rounded-lg" style={{ background: '#1a1a2e', border: '1px solid #333' }}>
              <p className="text-xs font-mono whitespace-pre-wrap" style={{ color: '#94a3b8' }}>
                {msg.content as string}
              </p>
            </div>
          );
        }

        if (msg.type === 'gate_skip') {
          return (
            <div key={i} className="px-3 py-1 text-xs" style={{ color: 'var(--color-text-dim)' }}>
              {msg.agent as string} skipped — no new contribution
            </div>
          );
        }

        if (msg.type === 'convergence') {
          return (
            <div key={i} className="px-3 py-2 text-xs rounded" style={{ background: '#1e1a2e', color: '#a78bfa', border: '1px solid #4c1d95' }}>
              Convergence detected — forcing {msg.forced_next as string}
            </div>
          );
        }

        if (msg.type === 'phase_transition') {
          return (
            <div key={i} className="py-4 text-center">
              <div className="inline-block px-4 py-2 rounded-lg text-sm font-medium" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>
                {msg.phase === 'prd_panel' ? 'Brainstorm complete. Running PRD panel...' :
                 msg.phase === 'conclusion' ? 'Brainstorm complete. Generating Conclusion Report...' :
                 `Phase: ${msg.phase}`}
              </div>
            </div>
          );
        }

        if (msg.type === 'session_complete') {
          return (
            <div key={i} className="py-4 text-center">
              <div className="inline-block px-6 py-3 rounded-lg text-sm font-bold" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>
                Session Complete — {msg.terminated_by as string}
              </div>
            </div>
          );
        }

        if (msg.type === 'error') {
          return (
            <div key={i} className="px-3 py-2 text-sm text-red-400 rounded" style={{ background: '#1a0a0a', border: '1px solid #7f1d1d' }}>
              Error: {msg.message as string}
            </div>
          );
        }

        return null;
      })}
    </div>
  );
}
```

- [ ] **Step 2: Create frontend/src/components/session/ArtifactPanel.tsx**

```tsx
import type { WSMessage } from '../../hooks/useWebSocket';

interface Props {
  messages: WSMessage[];
}

export default function ArtifactPanel({ messages }: Props) {
  const sections = messages.filter((m) => m.type === 'artifact_section');

  if (sections.length === 0) {
    return (
      <div className="p-4 text-sm" style={{ color: 'var(--color-text-dim)' }}>
        Living Artifact will appear here as the session progresses...
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4 overflow-y-auto">
      <h3 className="text-sm font-bold" style={{ color: 'var(--color-teal)' }}>Living Artifact</h3>
      {sections.map((s, i) => (
        <div
          key={i}
          className="p-3 rounded-lg text-sm"
          style={{
            background: 'var(--color-navy-light)',
            border: '1px solid var(--color-border)',
            animation: 'fadeIn 0.5s ease-in',
          }}
        >
          <p className="text-[10px] mb-2" style={{ color: 'var(--color-text-dim)' }}>
            Section {s.section_num as number} — {s.section_name as string}
          </p>
          <p className="whitespace-pre-wrap font-mono text-xs" style={{ color: 'var(--color-text)' }}>
            {s.content as string}
          </p>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create frontend/src/components/session/StatsBar.tsx**

```tsx
import type { WSMessage } from '../../hooks/useWebSocket';

interface Props {
  messages: WSMessage[];
  maxRounds: number;
}

export default function StatsBar({ messages, maxRounds }: Props) {
  const latestStats = [...messages].reverse().find((m) => m.type === 'stats');
  const rounds = (latestStats?.rounds as number) || 0;
  const gateSkips = (latestStats?.gate_skips as number) || 0;
  const overseerInjections = messages.filter((m) => m.type === 'overseer').length;

  return (
    <div
      className="flex items-center gap-6 px-4 py-2 text-xs"
      style={{ background: 'var(--color-navy-light)', borderBottom: '1px solid var(--color-border)' }}
    >
      <div>
        <span style={{ color: 'var(--color-text-dim)' }}>Rounds: </span>
        <span style={{ color: 'var(--color-teal)' }}>{rounds} / {maxRounds}</span>
      </div>
      <div>
        <span style={{ color: 'var(--color-text-dim)' }}>Gate skips: </span>
        <span>{gateSkips}</span>
      </div>
      <div>
        <span style={{ color: 'var(--color-text-dim)' }}>Overseer: </span>
        <span>{overseerInjections}</span>
      </div>
      <div className="flex-1" />
      <div className="w-32 h-1.5 rounded-full" style={{ background: 'var(--color-navy)' }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${(rounds / maxRounds) * 100}%`, background: 'var(--color-teal)' }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/session/
git commit -m "feat: live feed, artifact panel, and stats bar components"
```

---

### Task 30: Canvas live mode integration

**Files:**
- Modify: `frontend/src/pages/Canvas.tsx` (add live mode)

- [ ] **Step 1: Add live mode to Canvas.tsx**

Add these imports to the top:
```tsx
import { useWebSocket, type WSMessage } from '../hooks/useWebSocket';
import LiveFeed from '../components/session/LiveFeed';
import ArtifactPanel from '../components/session/ArtifactPanel';
import StatsBar from '../components/session/StatsBar';
import { api } from '../api/client';
```

Add WebSocket handling inside the `Canvas` component, after existing state:
```tsx
const { connect, disconnect, connected, messages: wsMessages } = useWebSocket({
  sessionId: id || '',
  onMessage: (msg) => {
    if (msg.type === 'agent_message' && !msg.streaming) {
      useCanvasStore.getState().setActiveAgent(msg.source as string);
    }
    if (msg.type === 'session_complete') {
      useCanvasStore.getState().setActiveAgent(null);
      navigate(`/results/${id}`);
    }
  },
});
```

Update `handleBeginSymposium`:
```tsx
const handleBeginSymposium = async () => {
  await handleSave();
  await api.post(`/sessions/${id}/run`);
  setIsLive(true);
  connect();
};
```

Replace the return JSX — when `isLive` is true, render the split live view:

```tsx
if (isLive) {
  return (
    <div className="h-screen flex flex-col" style={{ background: 'var(--color-navy)' }}>
      <StatsBar messages={wsMessages} maxRounds={settings.max_rounds} />
      <div className="flex-1 flex">
        {/* Left — Canvas (40%) */}
        <div className="w-2/5 h-full" style={{ borderRight: '1px solid var(--color-border)' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e2438" />
          </ReactFlow>
        </div>
        {/* Right — Live Feed (60%) */}
        <div className="w-3/5 h-full flex flex-col">
          <LiveFeed messages={wsMessages} />
          <div style={{ height: '30%', borderTop: '1px solid var(--color-border)' }}>
            <ArtifactPanel messages={wsMessages} />
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Canvas.tsx
git commit -m "feat: canvas live mode with split view, streaming feed, and artifact panel"
```

---

## Phase 7: Results Page

### Task 31: Markdown renderer and Results page

**Files:**
- Create: `frontend/src/components/shared/MarkdownRenderer.tsx`
- Modify: `frontend/src/pages/Results.tsx`

- [ ] **Step 1: Create frontend/src/components/shared/MarkdownRenderer.tsx**

```tsx
import ReactMarkdown from 'react-markdown';

interface Props {
  content: string;
}

export default function MarkdownRenderer({ content }: Props) {
  return (
    <div className="prose prose-invert prose-sm max-w-none" style={{ color: 'var(--color-text)' }}>
      <ReactMarkdown
        components={{
          h1: ({ children }) => <h1 className="text-xl font-bold mt-6 mb-3" style={{ color: 'var(--color-teal)' }}>{children}</h1>,
          h2: ({ children }) => <h2 className="text-lg font-bold mt-5 mb-2" style={{ color: 'var(--color-text)' }}>{children}</h2>,
          h3: ({ children }) => <h3 className="text-base font-bold mt-4 mb-2" style={{ color: 'var(--color-text)' }}>{children}</h3>,
          p: ({ children }) => <p className="mb-3 leading-relaxed text-sm">{children}</p>,
          ul: ({ children }) => <ul className="mb-3 pl-4 list-disc text-sm">{children}</ul>,
          li: ({ children }) => <li className="mb-1">{children}</li>,
          strong: ({ children }) => <strong style={{ color: 'var(--color-teal)' }}>{children}</strong>,
          hr: () => <hr className="my-4" style={{ borderColor: 'var(--color-border)' }} />,
          blockquote: ({ children }) => (
            <blockquote className="pl-4 my-3 text-sm" style={{ borderLeft: '3px solid var(--color-teal)', color: 'var(--color-text-dim)' }}>
              {children}
            </blockquote>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
```

- [ ] **Step 2: Rewrite frontend/src/pages/Results.tsx**

```tsx
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useSessionStore } from '../store/sessionStore';
import { api } from '../api/client';
import MarkdownRenderer from '../components/shared/MarkdownRenderer';

export default function Results() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentSession, fetchSession } = useSessionStore();
  const [activeTab, setActiveTab] = useState('');

  useEffect(() => {
    if (id) fetchSession(id);
  }, [id, fetchSession]);

  useEffect(() => {
    if (currentSession?.outputs) {
      const tabs = Object.keys(currentSession.outputs);
      if (tabs.length > 0 && !activeTab) {
        // Default to PRD or conclusion tab if available
        const defaultTab = tabs.find((t) => t.includes('prd') || t.includes('conclusion')) || tabs[0];
        setActiveTab(defaultTab);
      }
    }
  }, [currentSession, activeTab]);

  const handleDownload = (filename: string, content: string) => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadZip = async () => {
    if (!id) return;
    const res = await fetch(`/api/sessions/${id}/export?format=zip`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('symposium_token')}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentSession?.name || 'session'}.zip`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!currentSession) {
    return <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--color-navy)', color: 'var(--color-text-dim)' }}>Loading...</div>;
  }

  const outputs = currentSession.outputs || {};
  const tabs = Object.keys(outputs);

  return (
    <div className="min-h-screen" style={{ background: 'var(--color-navy)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-8 py-4" style={{ borderBottom: '1px solid var(--color-border)' }}>
        <div>
          <button onClick={() => navigate('/sessions')} className="text-xs mb-1" style={{ color: 'var(--color-text-dim)' }}>
            &larr; Sessions
          </button>
          <h1 className="text-lg font-bold" style={{ color: 'var(--color-teal)' }}>{currentSession.name}</h1>
          <p className="text-xs" style={{ color: 'var(--color-text-dim)' }}>
            {currentSession.mode === 'product' ? 'Product Discussion' : 'Problem Discussion'} · Completed {currentSession.completed_at ? new Date(currentSession.completed_at).toLocaleString() : ''}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => navigate(`/canvas/${id}`)}
            className="px-3 py-2 rounded-lg text-xs"
            style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}
          >
            Re-run
          </button>
          <button
            onClick={handleDownloadZip}
            className="px-3 py-2 rounded-lg text-xs font-medium"
            style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}
          >
            Download ZIP
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex px-8 pt-4 gap-1" style={{ borderBottom: '1px solid var(--color-border)' }}>
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className="px-4 py-2 text-sm rounded-t-lg"
            style={{
              background: activeTab === tab ? 'var(--color-navy-light)' : 'transparent',
              color: activeTab === tab ? 'var(--color-teal)' : 'var(--color-text-dim)',
              borderBottom: activeTab === tab ? '2px solid var(--color-teal)' : '2px solid transparent',
            }}
          >
            {tab.replace('.md', '').replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="max-w-4xl mx-auto px-8 py-6">
        {activeTab && outputs[activeTab] && (
          <>
            <div className="flex justify-end mb-4">
              <button
                onClick={() => handleDownload(activeTab, outputs[activeTab])}
                className="text-xs px-3 py-1 rounded"
                style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}
              >
                Download {activeTab}
              </button>
            </div>
            <MarkdownRenderer content={outputs[activeTab]} />
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/shared/MarkdownRenderer.tsx frontend/src/pages/Results.tsx
git commit -m "feat: results page with tabbed markdown viewer and download"
```

---

## Phase 8: Final Integration and Polish

### Task 32: Wire everything together and verify end-to-end

**Files:**
- Verify all imports and fix any missing connections

- [ ] **Step 1: Create a startup script**

Create `start.sh` at the project root:

```bash
#!/bin/bash
# Start both backend and frontend for development

echo "Starting Symposium..."

# Backend
cd backend/..
pip install -r requirements.txt -q
python -m uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "Backend started on :8000 (PID $BACKEND_PID)"

# Frontend
cd frontend
npm install -q
npm run dev &
FRONTEND_PID=$!
echo "Frontend started on :5173 (PID $FRONTEND_PID)"

echo ""
echo "Symposium running at http://localhost:5173"
echo "API docs at http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x start.sh`

- [ ] **Step 3: Create .env from example**

Run: `cp .env.example .env`

- [ ] **Step 4: Test full startup**

Run: `./start.sh`
Expected: Both servers start, login page loads at localhost:5173

- [ ] **Step 5: Commit**

```bash
git add start.sh
git commit -m "feat: development startup script"
```

---

### Task 33: Template save/load (post-session modal)

**Files:**
- Create: `frontend/src/components/shared/SaveTemplateModal.tsx`
- Modify: `frontend/src/pages/Results.tsx` (add post-session modal trigger)

- [ ] **Step 1: Create frontend/src/components/shared/SaveTemplateModal.tsx**

```tsx
import { useState } from 'react';
import { api } from '../../api/client';
import type { SessionData } from '../../store/sessionStore';

interface Props {
  session: SessionData;
  onClose: () => void;
}

export default function SaveTemplateModal({ session, onClose }: Props) {
  const [name, setName] = useState(`${session.name} Template`);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.post('/templates', {
        name,
        agents: session.agents,
        settings: session.settings,
        mode: session.mode,
        canvas_state: session.canvas_state,
      });
      onClose();
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div className="w-full max-w-md p-6 rounded-xl" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-border)' }}>
        <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--color-teal)' }}>
          Save as Template?
        </h2>
        <p className="text-sm mb-4" style={{ color: 'var(--color-text-dim)' }}>
          Save this canvas configuration for future sessions.
        </p>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full px-3 py-2 rounded-lg text-sm mb-4 outline-none"
          style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
        />
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-lg text-sm"
            style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}
          >
            Not now
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !name}
            className="flex-1 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}
          >
            {saving ? 'Saving...' : 'Save Template'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add modal to Results page**

Add to the top of Results.tsx:
```tsx
import SaveTemplateModal from '../components/shared/SaveTemplateModal';
```

Add state:
```tsx
const [showTemplateModal, setShowTemplateModal] = useState(true);
```

Add before closing `</div>`:
```tsx
{showTemplateModal && currentSession.status === 'complete' && (
  <SaveTemplateModal session={currentSession} onClose={() => setShowTemplateModal(false)} />
)}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/shared/SaveTemplateModal.tsx frontend/src/pages/Results.tsx
git commit -m "feat: post-session save-as-template modal"
```

---

### Task 34: AI suggestion hooks for frontend

**Files:**
- Create: `frontend/src/hooks/useAISuggest.ts`
- Modify: `frontend/src/components/setup/ProblemStatement.tsx` (add inline suggestions)

- [ ] **Step 1: Create frontend/src/hooks/useAISuggest.ts**

```typescript
import { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';

export function useInlineSuggestion(text: string, debounceMs: number = 800) {
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    setSuggestion(null);
    if (!text || text.length < 20) return;

    if (timeoutRef.current) clearTimeout(timeoutRef.current);

    timeoutRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.post<{ suggestion: string }>('/suggest/inline', { text });
        if (res.suggestion && res.suggestion !== 'NONE') {
          setSuggestion(res.suggestion);
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }, debounceMs);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [text, debounceMs]);

  const dismiss = () => setSuggestion(null);

  return { suggestion, loading, dismiss };
}


export function useReview() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const review = async (text: string, type: 'problem_statement' | 'persona', otherAgents: unknown[] = []) => {
    setLoading(true);
    setResult(null);
    try {
      const res = await api.post<{ result: Record<string, unknown> }>('/suggest/review', {
        text,
        review_type: type,
        other_agents: otherAgents,
      });
      setResult(res.result);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  return { review, loading, result, clearResult: () => setResult(null) };
}
```

- [ ] **Step 2: Add inline suggestions to ProblemStatement.tsx**

Update `frontend/src/components/setup/ProblemStatement.tsx` to use the hook:

```tsx
import { useState } from 'react';
import { useInlineSuggestion, useReview } from '../../hooks/useAISuggest';

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function ProblemStatement({ value, onChange }: Props) {
  const { suggestion, dismiss } = useInlineSuggestion(value);
  const { review, loading: reviewing, result: reviewResult, clearResult } = useReview();

  return (
    <div>
      <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-dim)' }}>
        Problem Statement
      </label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={6}
        placeholder="Describe the problem, goal, or question this session should address..."
        className="w-full px-3 py-2 rounded-lg text-sm outline-none resize-y"
        style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
      />

      <div className="flex justify-between items-center mt-1">
        <span className="text-[10px]" style={{ color: value.length < 100 ? '#f87171' : 'var(--color-text-dim)' }}>
          {value.length} chars
        </span>
        <button
          onClick={() => review(value, 'problem_statement')}
          disabled={reviewing || value.length < 20}
          className="text-[10px] px-2 py-1 rounded disabled:opacity-40"
          style={{ border: '1px solid var(--color-border)', color: 'var(--color-teal-dim)' }}
        >
          {reviewing ? 'Reviewing...' : 'Review'}
        </button>
      </div>

      {/* Inline suggestion chip */}
      {suggestion && (
        <div
          className="mt-2 p-2 rounded-lg flex items-center justify-between text-xs"
          style={{ background: 'var(--color-navy)', border: '1px solid var(--color-teal-dim)' }}
        >
          <span style={{ color: 'var(--color-text-dim)' }}>{suggestion}</span>
          <button onClick={dismiss} className="ml-2 text-[10px]" style={{ color: 'var(--color-text-dim)' }}>dismiss</button>
        </div>
      )}

      {/* Review results */}
      {reviewResult && (
        <div className="mt-3 p-3 rounded-lg text-xs space-y-2" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)' }}>
          <div className="flex justify-between">
            <span style={{ color: 'var(--color-text-dim)' }}>
              Clarity: <strong style={{ color: (reviewResult.clarity as string) === 'High' ? '#2dd4bf' : (reviewResult.clarity as string) === 'Medium' ? '#fbbf24' : '#f87171' }}>{reviewResult.clarity as string}</strong>
            </span>
            <button onClick={clearResult} className="text-[10px]" style={{ color: 'var(--color-text-dim)' }}>close</button>
          </div>
          {(reviewResult.missing as string[])?.length > 0 && (
            <div>
              <p style={{ color: '#f87171' }}>Missing:</p>
              <ul className="pl-3">
                {(reviewResult.missing as string[]).map((m, i) => <li key={i} style={{ color: 'var(--color-text-dim)' }}>- {m}</li>)}
              </ul>
            </div>
          )}
          {(reviewResult.suggestions as string[])?.length > 0 && (
            <div>
              <p style={{ color: 'var(--color-teal-dim)' }}>Suggestions:</p>
              <ul className="pl-3">
                {(reviewResult.suggestions as string[]).map((s, i) => <li key={i} style={{ color: 'var(--color-text-dim)' }}>- {s}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useAISuggest.ts frontend/src/components/setup/ProblemStatement.tsx
git commit -m "feat: AI inline suggestions and review for problem statements"
```

---

### Task 35: Final commit — all pieces wired

- [ ] **Step 1: Verify all files exist and imports work**

Run: `cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium && python -c "from backend.main import app; print('Backend imports OK')"`
Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`

Fix any import errors that surface.

- [ ] **Step 2: Final commit**

```bash
git add -A
git commit -m "feat: Symposium v1 — complete multi-agent brainstorming web app"
```

---

## Summary of what this plan builds

| Phase | What it delivers |
|-------|-----------------|
| 1. Backend Foundation | FastAPI app, SQLite DB, auth, CRUD for sessions + templates |
| 2. Engine Modularization | `backend/engine/` package — gate, selector, overseer, artifact, convergence, summary, brainstorm loop |
| 3. WebSocket Runner | Session runner service + WS endpoint + AI suggestion endpoints + ZIP export |
| 4. Frontend Skeleton | Vite + React + Tailwind + routing + login + sessions list |
| 5. Canvas UI | React Flow canvas, agent nodes, config drawer, agent library, setup panel |
| 6. Live Session | WebSocket hook, live feed, artifact panel, stats bar, split view |
| 7. Results | Tabbed markdown viewer, individual + ZIP download |
| 8. Polish | Save-as-template modal, AI suggestions, startup script |

**Total tasks: 35**
**Total files created: ~55**
