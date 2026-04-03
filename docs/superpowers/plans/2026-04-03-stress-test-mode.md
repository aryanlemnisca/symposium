# Stress Test Mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Stress Test as a third session mode — multi-phase document review with AI-proposed phases, stateful Overseer, bidirectional WebSocket for pause/resume, per-phase artifacts, and a final readiness verdict.

**Architecture:** New stress test brainstorm loop (`stress_brainstorm.py`) shares existing utilities (gate, selector, clients) but has its own phase-aware flow. StressOverseer is a stateful class managing phase progression, drift detection, artifact writing, and verdict generation. Bidirectional WebSocket via asyncio.Queue enables pause/resume during live sessions.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, SQLite, AutoGen v0.4, Gemini API, React 18, TypeScript, Zustand, TailwindCSS. New deps: pypdf, python-docx, openpyxl, pandas.

**Spec:** `docs/superpowers/specs/2026-04-03-stress-test-mode-design.md`

---

## File Structure

### New files

```
backend/
  services/
    doc_extract.py              # Text extraction from PDF/DOCX/XLSX/CSV/TXT/MD
    stress_suggest.py           # Phase inference, re-interpret, agent suggestion
  routers/
    stress_test.py              # Stress test API endpoints
  engine/
    stress_brainstorm.py        # Phase-aware brainstorm loop
    stress_overseer.py          # StressOverseer class (stateful)

frontend/src/
  components/
    setup/
      DocumentUpload.tsx        # Document upload area with drag-drop
      PhaseCards.tsx             # Editable phase cards for setup
      StressTestSettings.tsx    # Min rounds slider + computed totals
    session/
      PhasePauseCard.tsx        # Phase advancement pause card with countdown
      DocumentSidebar.tsx       # Document list sidebar during live session
```

### Modified files

```
backend/
  models/session.py             # Add stress_test to mode enum, new columns
  models/schemas.py             # Phase, UploadedDocument schemas, stress settings
  routers/sessions.py           # Bidirectional WebSocket
  services/session_runner.py    # Dispatch to run_stress_test(), pass receive
  engine/selector.py            # Optional stress_context parameter
  main.py                       # Mount stress_test router

frontend/src/
  store/sessionStore.ts         # Phase, UploadedDocument types
  hooks/useWebSocket.ts         # sendCommand() method
  components/setup/ModeSelector.tsx  # Add Stress Test option
  components/session/LiveFeed.tsx    # Phase pause card, drift redirect, verdict
  components/session/StatsBar.tsx    # Phase + sub-phase indicator
  components/session/ArtifactPanel.tsx # Per-phase collapsible artifacts
  pages/Canvas.tsx              # Stress test setup flow
  pages/Results.tsx             # Per-phase tabs, verdict tab
  
requirements.txt                # New dependencies
```

---

## Phase 1: Backend Foundation

### Task 1: Add dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add new dependencies to requirements.txt**

Add these lines to the end of `requirements.txt`:

```txt
pypdf==5.4.0
python-docx==1.1.2
openpyxl==3.1.5
pandas==2.2.3
```

- [ ] **Step 2: Install**

Run: `cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium && pip install -r requirements.txt`
Expected: All packages install successfully

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "feat: add document extraction dependencies for stress test mode"
```

---

### Task 2: Data model extensions

**Files:**
- Modify: `backend/models/session.py`
- Modify: `backend/models/schemas.py`

- [ ] **Step 1: Extend Session model**

In `backend/models/session.py`, add `stress_test` to `SessionMode` enum and add new columns to `Session`:

```python
class SessionMode(str, enum.Enum):
    product = "product"
    problem_discussion = "problem_discussion"
    stress_test = "stress_test"
```

Add these columns to the `Session` class after `canvas_state`:

```python
    phases = Column(JSON, nullable=True)                    # list[Phase] for stress test
    current_phase_index = Column(Integer, nullable=True)    # active phase index
    uploaded_documents = Column(JSON, nullable=True)        # list[UploadedDocument]
    stress_review_instructions = Column(Text, nullable=True)  # AI-generated review instructions
```

Add `Integer` to the SQLAlchemy import at the top:

```python
from sqlalchemy import Column, String, Text, DateTime, JSON, Boolean, Enum as SAEnum, Integer
```

- [ ] **Step 2: Add Phase and UploadedDocument Pydantic schemas**

In `backend/models/schemas.py`, add after the existing `SessionMode` enum:

```python
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
```

Update `SessionMode` enum to add stress_test:

```python
class SessionMode(str, Enum):
    product = "product"
    problem_discussion = "problem_discussion"
    stress_test = "stress_test"
```

Add `stress_test_min_rounds_per_phase` to `SessionSettings`:

```python
class SessionSettings(BaseModel):
    max_rounds: int = 50
    temperature: float = 0.70
    gate_start_round: int = 10
    overseer_interval: int = 10
    min_rounds_before_convergence: int = 45
    prd_panel_rounds: int = 10
    prd_panel_names: list[str] = []
    stress_test_min_rounds_per_phase: int = 20
```

Add new optional fields to `SessionUpdate`:

```python
class SessionUpdate(BaseModel):
    # ... existing fields ...
    phases: Optional[list[Phase]] = None
    uploaded_documents: Optional[list[UploadedDocument]] = None
    stress_review_instructions: Optional[str] = None
```

Add new fields to `SessionResponse`:

```python
class SessionResponse(BaseModel):
    # ... existing fields ...
    phases: Optional[list[dict]] = None
    uploaded_documents: Optional[list[dict]] = None
    stress_review_instructions: Optional[str] = None
```

- [ ] **Step 3: Update session response builder**

In `backend/routers/sessions.py`, update `_session_to_response()` to include new fields:

```python
def _session_to_response(s: Session) -> dict:
    return {
        # ... existing fields ...
        "phases": s.phases,
        "uploaded_documents": s.uploaded_documents,
        "stress_review_instructions": s.stress_review_instructions,
    }
```

- [ ] **Step 4: Delete old database and verify**

Run:
```bash
rm -f symposium.db
cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium && python -c "
from backend.database import init_db
init_db()
from backend.models.session import Session, SessionMode
print('Modes:', [m.value for m in SessionMode])
print('OK')
"
```
Expected: `Modes: ['product', 'problem_discussion', 'stress_test']` then `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/models/session.py backend/models/schemas.py backend/routers/sessions.py
git commit -m "feat: data model extensions for stress test mode"
```

---

### Task 3: Document text extraction service

**Files:**
- Create: `backend/services/doc_extract.py`

- [ ] **Step 1: Create doc_extract.py**

```python
"""Document text extraction — PDF, DOCX, XLSX, CSV, TXT, MD."""

import io
import os


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from a document. Raises ValueError on unsupported/failed extraction."""
    ext = os.path.splitext(filename)[1].lower()

    if ext in (".txt", ".md"):
        return file_bytes.decode("utf-8", errors="replace")

    if ext == ".pdf":
        return _extract_pdf(file_bytes, filename)

    if ext == ".docx":
        return _extract_docx(file_bytes)

    if ext == ".xlsx":
        return _extract_xlsx(file_bytes)

    if ext == ".csv":
        return _extract_csv(file_bytes)

    raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(file_bytes: bytes, filename: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    has_images = False
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
        if hasattr(page, "images") and len(page.images) > 0:
            has_images = True

    result = "\n\n".join(pages).strip()
    if not result:
        raise ValueError(f"Could not extract text from {filename}. The PDF may be image-only.")
    if has_images:
        result += (
            "\n\n[Note: This document contains images/charts that could not be "
            "extracted as text. Key visual content should be described in the problem statement.]"
        )
    return result


def _extract_docx(file_bytes: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    parts = []

    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)

    for table in doc.tables:
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows.append("| " + " | ".join(cells) + " |")
        if rows:
            # Add markdown table header separator after first row
            header_sep = "| " + " | ".join(["---"] * len(table.rows[0].cells)) + " |"
            rows.insert(1, header_sep)
            parts.append("\n".join(rows))

    return "\n\n".join(parts).strip()


def _extract_xlsx(file_bytes: bytes) -> str:
    import pandas as pd

    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    parts = []
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name)
        parts.append(f"## Sheet: {sheet_name}\n\n{df.to_markdown(index=False)}")
    return "\n\n".join(parts).strip()


def _extract_csv(file_bytes: bytes) -> str:
    import pandas as pd

    df = pd.read_csv(io.BytesIO(file_bytes))
    return df.to_markdown(index=False)
```

- [ ] **Step 2: Verify imports work**

Run:
```bash
python -c "from backend.services.doc_extract import extract_text; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/services/doc_extract.py
git commit -m "feat: document text extraction service for PDF, DOCX, XLSX, CSV, TXT, MD"
```

---

### Task 4: Stress test upload endpoint

**Files:**
- Create: `backend/routers/stress_test.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create stress_test router with upload endpoint**

```python
"""Stress test specific endpoints."""

import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session as DBSession
from backend.database import get_db
from backend.auth import require_auth
from backend.models.session import Session
from backend.services.doc_extract import extract_text

router = APIRouter(prefix="/api", tags=["stress-test"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".xlsx", ".csv"}
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB


@router.post("/upload/stress-test")
async def upload_stress_test_document(
    file: UploadFile = File(...),
    _=Depends(require_auth),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max {MAX_UPLOAD_SIZE // (1024*1024)}MB")

    try:
        content_text = extract_text(content, file.filename or "document")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    doc = {
        "id": str(uuid.uuid4()),
        "filename": file.filename or "document",
        "filetype": ext.lstrip("."),
        "content_text": content_text,
        "size_bytes": len(content),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "id": doc["id"],
        "filename": doc["filename"],
        "filetype": doc["filetype"],
        "size_bytes": doc["size_bytes"],
        "preview": content_text[:500],
        "uploaded_at": doc["uploaded_at"],
        "document": doc,
    }
```

- [ ] **Step 2: Mount router in main.py**

In `backend/main.py`, add after `from backend.routers import suggest`:

```python
from backend.routers import stress_test
```

And after `app.include_router(suggest.router)`:

```python
app.include_router(stress_test.router)
```

- [ ] **Step 3: Verify endpoint works**

Run:
```bash
python -c "
from backend.main import app
routes = [r.path for r in app.routes if hasattr(r, 'path')]
print('/api/upload/stress-test' in [r for r in routes])
print('OK')
"
```
Expected: `True` then `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/routers/stress_test.py backend/main.py
git commit -m "feat: stress test document upload endpoint with text extraction"
```

---

### Task 5: Phase inference and re-interpret service

**Files:**
- Create: `backend/services/stress_suggest.py`

- [ ] **Step 1: Create stress_suggest.py**

```python
"""Stress test AI services — phase inference, re-interpret, agent suggestion."""

import json
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.clients import make_client

SUPPORT_MODEL = "gemini-2.5-flash"


async def _ask(system: str, prompt: str, api_key: str) -> str:
    client = make_client(model=SUPPORT_MODEL, api_key=api_key, temperature=0.3)
    agent = AssistantAgent(name="StressSuggester", system_message=system, model_client=client)
    response = await agent.on_messages(
        [TextMessage(content=prompt, source="user")], CancellationToken()
    )
    return response.chat_message.content if response and response.chat_message else ""


def _parse_json(raw: str):
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return None


async def analyse_documents(
    documents: list[dict],
    problem_statement: str,
    api_key: str,
) -> dict:
    """Propose phase breakdown + review instructions from documents."""
    system = (
        "You are an expert document reviewer designing a multi-phase stress-test review session. "
        "You sequence phases so dependency-heavy sections are reviewed before things that depend on them."
    )
    doc_summaries = "\n\n".join(
        f"[{d['filename']}] ({d['size_bytes']} bytes):\n{d['content_text'][:2000]}"
        for d in documents
    )
    prompt = (
        f"You are analysing a set of documents that a user wants to stress-test using a multi-agent review board.\n\n"
        f"Problem statement:\n{problem_statement}\n\n"
        f"Documents uploaded:\n{doc_summaries}\n\n"
        f"Propose a logical phase breakdown for the review. Each phase should:\n"
        f"- Focus on a coherent subset of the documents\n"
        f"- Have a clear question to answer\n"
        f"- Be sequenced so earlier phases inform later ones\n"
        f"- Sequence dependency-heavy sections before things that depend on them\n"
        f"- Flag cross-document dependencies explicitly in subquestions\n"
        f"- Take approximately 20-30 rounds of agent debate to exhaust\n\n"
        f"Also generate a REVIEW INSTRUCTIONS block specific to these documents.\n"
        f"What should every reviewer check for given this type of work product?\n"
        f"Include domain-specific checks (not generic quality checks).\n\n"
        f"Return JSON:\n"
        f'{{\n'
        f'  "phases": [\n'
        f'    {{\n'
        f'      "number": 1,\n'
        f'      "name": "short phase name",\n'
        f'      "document_ids": ["doc_id_1", "doc_id_2"],\n'
        f'      "focus_question": "the primary question this phase must answer",\n'
        f'      "key_subquestions": ["subquestion 1", "subquestion 2", "subquestion 3"],\n'
        f'      "rationale": "why these documents and this question go together"\n'
        f'    }}\n'
        f'  ],\n'
        f'  "review_instructions": "full review instructions block tailored to these documents",\n'
        f'  "suggested_min_rounds_per_phase": 20\n'
        f'}}'
    )

    raw = await _ask(system, prompt, api_key)
    result = _parse_json(raw)
    if result and isinstance(result, dict) and "phases" in result:
        return result
    return {"phases": [], "review_instructions": "", "suggested_min_rounds_per_phase": 20}


async def reinterpret_phases(
    current_phases: list[dict],
    documents: list[dict],
    problem_statement: str,
    api_key: str,
) -> dict:
    """Re-interpret phases after user edits."""
    system = (
        "You are an expert document reviewer. The user has edited your proposed phase plan. "
        "Reinterpret and return an updated version that respects their edits while maintaining "
        "logical sequencing and dependency ordering."
    )
    doc_summaries = "\n\n".join(
        f"[{d['filename']}]: {d['content_text'][:1000]}"
        for d in documents
    )
    phases_text = json.dumps(current_phases, indent=2)
    prompt = (
        f"Problem statement:\n{problem_statement}\n\n"
        f"Documents:\n{doc_summaries}\n\n"
        f"User's edited phase plan:\n{phases_text}\n\n"
        f"Reinterpret this plan. Return updated JSON with the same structure:\n"
        f'{{\n'
        f'  "phases": [...same structure as input...],\n'
        f'  "changes_explanation": "brief explanation of what you adjusted and why"\n'
        f'}}'
    )

    raw = await _ask(system, prompt, api_key)
    result = _parse_json(raw)
    if result and isinstance(result, dict) and "phases" in result:
        return result
    return {"phases": current_phases, "changes_explanation": "No changes made."}


async def suggest_stress_test_agents(
    documents: list[dict],
    phases: list[dict],
    problem_statement: str,
    api_key: str,
) -> list:
    """Suggest agents for stress test based on documents and phases."""
    system = (
        "You are designing a review board for a multi-agent stress-test session. "
        "Every panel MUST have: a domain expert, a logic challenger, an execution realist, "
        "and a scope guardian. Each agent has a 'lens' — what they specifically look for."
    )
    doc_summaries = "\n".join(f"- {d['filename']}: {d['content_text'][:300]}" for d in documents)
    phases_text = "\n".join(
        f"- Phase {p.get('number', '?')}: {p.get('name', '?')} — {p.get('focus_question', '?')}"
        for p in phases
    )
    prompt = (
        f"Documents being reviewed:\n{doc_summaries}\n\n"
        f"Confirmed phases:\n{phases_text}\n\n"
        f"Problem statement:\n{problem_statement}\n\n"
        f"Suggest 4-6 agents. Each MUST have a distinct review lens.\n\n"
        f"Mandatory roles:\n"
        f"1. Domain expert — knows the subject matter\n"
        f"2. Logic challenger — finds contradictions, weak reasoning\n"
        f"3. Execution realist — challenges whether plans can actually be done\n"
        f"4. Scope guardian — checks if documents cover what they claim\n\n"
        f"Return JSON array:\n"
        f'[{{\n'
        f'  "name": "Agent_Name",\n'
        f'  "role_tag": "2-3 word label",\n'
        f'  "mission": "one sentence",\n'
        f'  "lens": "what this agent specifically looks for in documents",\n'
        f'  "persona": "full structured persona (200-400 words)",\n'
        f'  "model": "gemini-3.1-pro-preview",\n'
        f'  "rationale": "why this agent creates productive tension"\n'
        f'}}]'
    )

    raw = await _ask(system, prompt, api_key)
    result = _parse_json(raw)
    if result and isinstance(result, list):
        return result
    return []
```

- [ ] **Step 2: Verify imports**

Run:
```bash
python -c "from backend.services.stress_suggest import analyse_documents, reinterpret_phases, suggest_stress_test_agents; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/services/stress_suggest.py
git commit -m "feat: stress test AI services — phase inference, re-interpret, agent suggestion"
```

---

### Task 6: Stress test API endpoints (analyse, reinterpret, confirm, suggest-agents)

**Files:**
- Modify: `backend/routers/stress_test.py`

- [ ] **Step 1: Add endpoints to stress_test router**

Add these imports and endpoints after the existing upload endpoint in `backend/routers/stress_test.py`:

```python
from backend.services import stress_suggest


def _get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    return key


@router.post("/sessions/{session_id}/stress/analyse-documents")
async def analyse_documents(
    session_id: str,
    db: DBSession = Depends(get_db),
    _=Depends(require_auth),
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.uploaded_documents:
        raise HTTPException(status_code=400, detail="No documents uploaded")
    if not session.problem_statement:
        raise HTTPException(status_code=400, detail="No problem statement")

    result = await stress_suggest.analyse_documents(
        session.uploaded_documents,
        session.problem_statement,
        _get_api_key(),
    )
    return result


@router.post("/sessions/{session_id}/stress/reinterpret-phases")
async def reinterpret_phases(
    session_id: str,
    body: dict,
    db: DBSession = Depends(get_db),
    _=Depends(require_auth),
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await stress_suggest.reinterpret_phases(
        body.get("phases", []),
        session.uploaded_documents or [],
        session.problem_statement or "",
        _get_api_key(),
    )
    return result


@router.post("/sessions/{session_id}/stress/confirm-phases")
async def confirm_phases(
    session_id: str,
    body: dict,
    db: DBSession = Depends(get_db),
    _=Depends(require_auth),
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    phases = body.get("phases", [])
    review_instructions = body.get("review_instructions", "")

    # Set all phases to pending, index to 0
    for p in phases:
        p["status"] = "pending"
        p["start_round"] = None
        p["end_round"] = None
        p["artifact"] = None
        p["confirmed"] = []
        p["contested"] = []
        p["open_questions"] = []

    session.phases = phases
    session.current_phase_index = 0
    session.stress_review_instructions = review_instructions
    db.commit()

    return {"status": "confirmed", "phase_count": len(phases)}


@router.post("/sessions/{session_id}/stress/suggest-agents")
async def suggest_agents(
    session_id: str,
    db: DBSession = Depends(get_db),
    _=Depends(require_auth),
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.phases:
        raise HTTPException(status_code=400, detail="Phases not confirmed yet")

    result = await stress_suggest.suggest_stress_test_agents(
        session.uploaded_documents or [],
        session.phases,
        session.problem_statement or "",
        _get_api_key(),
    )
    return {"agents": result}


@router.get("/sessions/{session_id}/stress/phases")
def get_phases(
    session_id: str,
    db: DBSession = Depends(get_db),
    _=Depends(require_auth),
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"phases": session.phases or [], "current_phase_index": session.current_phase_index}


@router.get("/sessions/{session_id}/stress/artifacts")
def get_artifacts(
    session_id: str,
    db: DBSession = Depends(get_db),
    _=Depends(require_auth),
):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    artifacts = []
    for phase in (session.phases or []):
        if phase.get("artifact"):
            artifacts.append({
                "phase_number": phase["number"],
                "phase_name": phase["name"],
                "artifact": phase["artifact"],
            })
    return {"artifacts": artifacts}
```

- [ ] **Step 2: Verify all endpoints register**

Run:
```bash
python -c "
from backend.main import app
stress_routes = [r.path for r in app.routes if hasattr(r, 'path') and 'stress' in r.path]
for r in sorted(stress_routes):
    print(r)
"
```
Expected: All 6 stress test endpoints listed

- [ ] **Step 3: Commit**

```bash
git add backend/routers/stress_test.py
git commit -m "feat: stress test API endpoints — analyse, reinterpret, confirm, suggest-agents"
```

---

## Phase 2: Engine

### Task 7: StressOverseer class

**Files:**
- Create: `backend/engine/stress_overseer.py`

- [ ] **Step 1: Create stress_overseer.py**

```python
"""StressOverseer — stateful phase controller for stress test sessions."""

import asyncio
from typing import Optional
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken


_SUB_PHASES = [
    (0.20, "Comprehend", "Read the phase documents. State what each document claims. Identify key assertions. No challenges yet."),
    (0.45, "Challenge", "Poke holes. Find weak logic, unsupported claims, missing evidence, contradictions. Be adversarial."),
    (0.65, "Cross-examine", "Respond to challenges raised. Defend or concede specific points. Force resolution per claim."),
    (0.85, "Synthesize", "Build the confirmed/contested/open list. What is sound? What is not?"),
    (1.00, "Conclude", "Final positions. Each agent states their verdict on the focus question. No new challenges — commit."),
]

_PHASE_DIRECTIVE_TEMPLATE = """\
[PHASE {number} NOW ACTIVE]

Focus: {name}
Primary question: {focus_question}

Key questions to resolve this phase:
{subquestions}

{carry_forward_text}

Do not re-open confirmed items unless you find a direct contradiction
in the current phase documents. Stay focused on Phase {number}.\
"""

_DRIFT_CHECK_PROMPT = """\
You are monitoring a stress-test review session.

Current phase: {phase_name}
Focus question: {focus_question}
Current sub-phase: {sub_phase} — {sub_phase_directive}

Last 5 agent messages:
{recent_messages}

Is the discussion on track for the current sub-phase?
If agents are drifting off the focus question or doing the wrong thing for this sub-phase
(e.g. challenging during Comprehend, or raising new issues during Conclude):
→ Return a one-sentence redirect.

If on track:
→ Return exactly: ON_TRACK

Return only the redirect sentence or ON_TRACK. Nothing else.\
"""

_PHASE_EVAL_PROMPT = """\
You are evaluating phase progress in a stress-test review session.

Current phase: {phase_name}
Focus question: {focus_question}
Key subquestions: {subquestions}
Rounds completed this phase: {round_count}
Minimum required: {min_rounds}

Recent messages (last 10):
{recent_messages}

Evaluate:
1. Has the focus question been substantially answered? (yes/partial/no)
2. Which subquestions are resolved? Which are still open?
3. Is the discussion still generating new insights or repeating?
4. Has minimum round count been reached? (yes/no)

If all subquestions are addressed AND minimum rounds reached AND discussion is repeating:
→ Return action: "suggest_advance"

Otherwise:
→ Return action: "continue"

Return JSON:
{{
  "action": "suggest_advance" or "continue",
  "confirmed": ["item 1", "item 2"],
  "contested": ["item 1"],
  "open_questions": ["question 1"],
  "continue_reason": "what still needs debate (if continue)",
  "summary": "2-3 sentence summary of phase findings (if suggest_advance)"
}}\
"""

_PHASE_ARTIFACT_PROMPT = """\
Write the Phase {number} review artifact for a stress-test session.

Phase name: {name}
Documents reviewed: {docs}
Focus question: {focus_question}

Agent discussion (full phase):
{phase_messages}

Produce the artifact in this exact format:

PHASE {number} — {name}
Documents reviewed: {docs}
Rounds: {start_round} to {end_round}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONFIRMED SOUND
[Each item: specific claim · why confirmed · which agents agreed]

CONTESTED
[Each item: specific claim · what the objection is · who raised it · not yet resolved]

MUST FIX BEFORE NEXT PHASE
[Blocking issues that must be resolved before the session can credibly proceed]

OPEN QUESTIONS
[Specific questions that emerged · why they matter · what answering them would change]

CROSS-DOCUMENT CONTRADICTIONS FOUND
[Any place where one document's claims conflict with another]

Be specific — name documents, name agents, quote specific claims. No vague summaries.\
"""

_FINAL_VERDICT_PROMPT = """\
You are producing the final readiness verdict for a stress-test review session.

The following phase artifacts were produced during the session:
{all_phase_artifacts}

Produce the final verdict in this exact format:

STRESS TEST — FINAL READINESS VERDICT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OVERALL VERDICT
READY / NOT READY / CONDITIONALLY READY

[One paragraph explaining the verdict]

BLOCKING ISSUES
[Must be resolved before the next step — specific, actionable]
· [issue]: [what must change]

NON-BLOCKING ISSUES
[Should be addressed but do not block progress]
· [issue]: [recommendation]

CONFIRMED SOUND — DO NOT REVISIT
[Items that survived stress-testing across all phases]
· [item]

CROSS-PHASE CONTRADICTIONS
[Places where findings in one phase conflict with another]
· [contradiction]: [which phases · what the conflict is]

RECOMMENDED FIRST ACTION
[The single most important thing to do before proceeding]

Be direct. Do not hedge. This verdict will be used to make a real decision.\
"""


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


class StressOverseer:
    def __init__(
        self,
        support_agent: AssistantAgent,
        phases: list[dict],
        documents: list[dict],
        min_rounds_per_phase: int,
        agent_names: list[str],
    ):
        self.support_agent = support_agent
        self.phases = phases
        self.documents = documents
        self.min_rounds_per_phase = min_rounds_per_phase
        self.agent_names = agent_names
        self.phase_round_counts: dict[int, int] = {i: 0 for i in range(len(phases))}
        self.carry_forward: dict[str, list[str]] = {
            "confirmed": [],
            "contested": [],
            "open_questions": [],
        }

    def get_sub_phase(self, phase_round_count: int) -> tuple[str, str]:
        """Return (sub_phase_name, sub_phase_directive) based on progress."""
        pct = phase_round_count / max(self.min_rounds_per_phase, 1)
        for threshold, name, directive in _SUB_PHASES:
            if pct <= threshold:
                return name, directive
        return _SUB_PHASES[-1][1], _SUB_PHASES[-1][2]

    def get_selector_context(self, phase_index: int) -> dict:
        """Build stress_context dict for the phase-aware selector."""
        phase = self.phases[phase_index]
        phase_round_count = self.phase_round_counts.get(phase_index, 0)
        sub_phase, sub_directive = self.get_sub_phase(phase_round_count)
        return {
            "phase_name": phase["name"],
            "focus_question": phase.get("focus_question", ""),
            "sub_phase": sub_phase,
            "sub_phase_directive": sub_directive,
        }

    def generate_phase_directive(self, phase_index: int) -> TextMessage:
        """Build the [PHASE N NOW ACTIVE] message."""
        phase = self.phases[phase_index]
        subquestions = "\n".join(f"· {q}" for q in phase.get("key_subquestions", []))

        carry_parts = []
        if self.carry_forward["confirmed"]:
            carry_parts.append("Carried forward from previous phases:")
            carry_parts.append("CONFIRMED: " + "; ".join(self.carry_forward["confirmed"]))
        if self.carry_forward["contested"]:
            carry_parts.append("CONTESTED: " + "; ".join(self.carry_forward["contested"]))
        carry_forward_text = "\n".join(carry_parts) if carry_parts else ""

        content = _PHASE_DIRECTIVE_TEMPLATE.format(
            number=phase["number"],
            name=phase["name"],
            focus_question=phase.get("focus_question", ""),
            subquestions=subquestions,
            carry_forward_text=carry_forward_text,
        )
        return TextMessage(content=content, source="Overseer")

    def check_keyword_drift(self, phase_index: int, messages: list) -> Optional[TextMessage]:
        """Zero-cost keyword drift check. Returns redirect or None."""
        phase = self.phases[phase_index]
        focus_words = set()
        for word in phase.get("focus_question", "").lower().split():
            if len(word) > 3:
                focus_words.add(word)
        for sq in phase.get("key_subquestions", []):
            for word in sq.lower().split():
                if len(word) > 3:
                    focus_words.add(word)

        if not focus_words:
            return None

        recent = [
            m for m in messages[-5:]
            if getattr(m, "source", "") in self.agent_names
        ][-3:]

        if not recent:
            return None

        for m in recent:
            content_lower = getattr(m, "content", "").lower()
            if any(w in content_lower for w in focus_words):
                return None  # On track

        return TextMessage(
            content=f"[OVERSEER] Stay focused on: {phase.get('focus_question', '')}",
            source="Overseer",
        )

    async def check_drift(self, phase_index: int, messages: list, round_num: int) -> Optional[TextMessage]:
        """LLM drift check (Flash call). Returns redirect or None."""
        phase = self.phases[phase_index]
        phase_round_count = self.phase_round_counts.get(phase_index, 0)
        sub_phase, sub_directive = self.get_sub_phase(phase_round_count)

        recent = [
            m for m in messages[-8:]
            if getattr(m, "source", "") in self.agent_names
        ][-5:]
        recent_text = "\n".join(
            f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:200]}"
            for m in recent
        )

        prompt = _DRIFT_CHECK_PROMPT.format(
            phase_name=phase["name"],
            focus_question=phase.get("focus_question", ""),
            sub_phase=sub_phase,
            sub_phase_directive=sub_directive,
            recent_messages=recent_text,
        )

        async def _call():
            return await self.support_agent.on_messages(
                [TextMessage(content=prompt, source="system")], CancellationToken()
            )

        response = await _call_with_retry(_call, label="drift_check")
        if response and response.chat_message:
            content = response.chat_message.content.strip()
            if content != "ON_TRACK" and content:
                return TextMessage(content=f"[OVERSEER] {content}", source="Overseer")
        return None

    async def evaluate_phase(self, phase_index: int, messages: list, round_num: int) -> dict:
        """Full phase evaluation every 5 rounds."""
        phase = self.phases[phase_index]
        phase_round_count = self.phase_round_counts.get(phase_index, 0)

        recent = [
            m for m in messages[-15:]
            if getattr(m, "source", "") in self.agent_names
            or getattr(m, "source", "") == "Overseer"
        ][-10:]
        recent_text = "\n".join(
            f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:300]}"
            for m in recent
        )
        subquestions = "\n".join(f"· {q}" for q in phase.get("key_subquestions", []))

        prompt = _PHASE_EVAL_PROMPT.format(
            phase_name=phase["name"],
            focus_question=phase.get("focus_question", ""),
            subquestions=subquestions,
            round_count=phase_round_count,
            min_rounds=self.min_rounds_per_phase,
            recent_messages=recent_text,
        )

        async def _call():
            return await self.support_agent.on_messages(
                [TextMessage(content=prompt, source="system")], CancellationToken()
            )

        response = await _call_with_retry(_call, label="phase_eval")
        if response and response.chat_message:
            parsed = _parse_json_safe(response.chat_message.content)
            if parsed:
                # Enforce minimum rounds
                if phase_round_count < self.min_rounds_per_phase:
                    parsed["action"] = "continue"
                    parsed["continue_reason"] = f"Minimum rounds ({self.min_rounds_per_phase}) not reached ({phase_round_count})"
                return parsed

        return {
            "action": "continue",
            "confirmed": [],
            "contested": [],
            "open_questions": [],
            "continue_reason": "Evaluation failed, continuing",
            "summary": "",
        }

    async def write_phase_artifact(self, phase_index: int, messages: list) -> str:
        """Write structured artifact when phase closes."""
        phase = self.phases[phase_index]
        phase_msgs = [
            m for m in messages
            if getattr(m, "source", "") in self.agent_names
            or getattr(m, "source", "") == "Overseer"
        ]
        phase_text = "\n\n".join(
            f"[{getattr(m, 'source', '?')}]: {getattr(m, 'content', '')[:500]}"
            for m in phase_msgs[-40:]
        )
        doc_names = []
        for doc in self.documents:
            if doc.get("id") in phase.get("document_ids", []):
                doc_names.append(doc["filename"])

        prompt = _PHASE_ARTIFACT_PROMPT.format(
            number=phase["number"],
            name=phase["name"],
            docs=", ".join(doc_names) or "All documents",
            focus_question=phase.get("focus_question", ""),
            phase_messages=phase_text,
            start_round=phase.get("start_round", "?"),
            end_round=phase.get("end_round", "?"),
        )

        async def _call():
            return await self.support_agent.on_messages(
                [TextMessage(content=prompt, source="system")], CancellationToken()
            )

        response = await _call_with_retry(_call, label=f"artifact_p{phase['number']}")
        artifact = ""
        if response and response.chat_message:
            artifact = response.chat_message.content

        # Update carry-forward
        eval_result = await self.evaluate_phase(phase_index, messages, 0)
        self.carry_forward["confirmed"].extend(eval_result.get("confirmed", []))
        self.carry_forward["contested"].extend(eval_result.get("contested", []))
        self.carry_forward["open_questions"].extend(eval_result.get("open_questions", []))

        return artifact

    def evaluate_session_close(self, total_rounds: int) -> bool:
        """Check if all phases complete and min total rounds reached."""
        min_total = len(self.phases) * self.min_rounds_per_phase
        all_complete = all(
            p.get("status") == "complete" for p in self.phases
        )
        return all_complete and total_rounds >= min_total

    async def generate_final_verdict(self) -> str:
        """Generate final readiness verdict from all phase artifacts."""
        all_artifacts = "\n\n---\n\n".join(
            p.get("artifact", "No artifact") for p in self.phases if p.get("artifact")
        )
        prompt = _FINAL_VERDICT_PROMPT.format(all_phase_artifacts=all_artifacts)

        async def _call():
            return await self.support_agent.on_messages(
                [TextMessage(content=prompt, source="system")], CancellationToken()
            )

        response = await _call_with_retry(_call, label="final_verdict")
        if response and response.chat_message:
            return response.chat_message.content
        return "Verdict generation failed."


def _parse_json_safe(raw: str):
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except Exception:
        return None


import json
```

- [ ] **Step 2: Verify imports**

Run:
```bash
python -c "from backend.engine.stress_overseer import StressOverseer; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/engine/stress_overseer.py
git commit -m "feat: StressOverseer class — phase evaluation, drift check, artifacts, verdict"
```

---

### Task 8: Phase-aware selector

**Files:**
- Modify: `backend/engine/selector.py`

- [ ] **Step 1: Add stress_context parameter to hybrid_selector**

In `backend/engine/selector.py`, update the `hybrid_selector` function signature to add the optional parameter:

```python
async def hybrid_selector(
    support_agent: AssistantAgent,
    messages: list,
    last_spoke: dict,
    turn_counter: int,
    agent_names: list[str],
    max_rounds: int,
    forced_next: Optional[str] = None,
    stress_context: Optional[dict] = None,
) -> str:
```

Find the line where `_SELECTOR_PROMPT` is formatted and add stress context. After `phase_context=_phase_context(turn_counter, max_rounds),` add:

```python
    stress_addition = ""
    if stress_context:
        stress_addition = (
            f"\n\nCurrent phase: {stress_context.get('phase_name', '')}\n"
            f"Phase focus: {stress_context.get('focus_question', '')}\n"
            f"Sub-phase: {stress_context.get('sub_phase', '')} — {stress_context.get('sub_phase_directive', '')}\n\n"
            f"In Challenge sub-phase: prioritize adversarial agents.\n"
            f"In Comprehend sub-phase: rotate evenly — everyone must state their reading.\n"
            f"In Synthesize/Conclude: prioritize agents who haven't committed a position yet."
        )
```

Append `stress_addition` to the prompt string before sending to the support agent.

- [ ] **Step 2: Verify existing modes still work**

Run:
```bash
python -c "from backend.engine.selector import hybrid_selector; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/engine/selector.py
git commit -m "feat: phase-aware selector with optional stress_context"
```

---

### Task 9: Stress test brainstorm loop

**Files:**
- Create: `backend/engine/stress_brainstorm.py`

- [ ] **Step 1: Create stress_brainstorm.py**

```python
"""Stress test brainstorm loop — phase-aware with bidirectional WebSocket."""

import asyncio
import time
from typing import Callable, Awaitable, Optional
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from backend.engine.config import EngineConfig
from backend.engine.clients import make_client
from backend.engine.gate import run_speech_gate
from backend.engine.selector import hybrid_selector
from backend.engine.summary import generate_rolling_summary, build_agent_context
from backend.engine.stress_overseer import StressOverseer

EventCallback = Callable[[str, dict], Awaitable[None]]
ReceiveCallback = Callable[[], Awaitable[dict]]


async def _call_with_retry(coro_fn, max_retries: int = 3, label: str = "call"):
    delays = [2, 4, 8]
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception:
            if attempt < max_retries:
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    return None


async def wait_for_command(receive: ReceiveCallback, timeout: Optional[float] = 60) -> str:
    """Wait for a client command or timeout."""
    try:
        if timeout:
            msg = await asyncio.wait_for(receive(), timeout=timeout)
        else:
            msg = await receive()
        return msg.get("action", "advance_phase")
    except asyncio.TimeoutError:
        return "auto_advance"
    except Exception:
        return "auto_advance"


def _build_agents(config: EngineConfig):
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


def _build_stress_context(
    problem_statement_msg: TextMessage,
    review_instructions: str,
    documents: list[dict],
    phases: list[dict],
    current_phase_index: int,
    phase_messages: list,
) -> list:
    """Build agent context for stress test mode."""
    context = [problem_statement_msg]

    # Review instructions
    if review_instructions:
        context.append(TextMessage(content=review_instructions, source="system"))

    # Current phase docs — full text
    current_phase = phases[current_phase_index]
    current_doc_ids = set(current_phase.get("document_ids", []))
    current_docs = [d for d in documents if d.get("id") in current_doc_ids]
    if current_docs:
        doc_text = "\n\n".join(
            f"[Document: {d['filename']}]\n{d['content_text']}"
            for d in current_docs
        )
        context.append(TextMessage(content=f"DOCUMENTS FOR THIS PHASE\n{'='*40}\n\n{doc_text}", source="system"))

    # Previous phase artifacts (compact)
    for prev_phase in phases[:current_phase_index]:
        if prev_phase.get("artifact"):
            context.append(TextMessage(content=prev_phase["artifact"], source="Overseer"))

    # Phase conversation history
    context.extend(phase_messages)

    return context


async def run_stress_test(
    config: EngineConfig,
    phases: list[dict],
    documents: list[dict],
    review_instructions: str,
    emit: EventCallback,
    receive: ReceiveCallback,
) -> tuple[list, dict, list[dict], str]:
    """Run a stress test session with phase-aware loop. Returns (messages, stats, phases, verdict)."""

    agents = _build_agents(config)
    agent_map = {a.name: a for a in agents}

    support_client = make_client(
        model=config.support_model,
        api_key=config.gemini_api_key,
        temperature=0.3,
    )
    support_agent = AssistantAgent(
        name="Support",
        description="Stress test support agent",
        system_message="You are a precise, concise assistant. Follow instructions exactly.",
        model_client=support_client,
    )

    min_rounds_per_phase = getattr(config, "stress_test_min_rounds_per_phase", 20)

    overseer = StressOverseer(
        support_agent=support_agent,
        phases=phases,
        documents=documents,
        min_rounds_per_phase=min_rounds_per_phase,
        agent_names=config.agent_names,
    )

    all_messages = [TextMessage(content=config.problem_statement, source="user")]
    last_spoke = {name: 0 for name in config.agent_names}
    persona_turns = {name: 0 for name in config.agent_names}

    total_round_count = 0
    total_gate_skips = 0
    start_time = time.monotonic()

    await emit("session_started", {"max_rounds": config.max_rounds, "total_phases": len(phases)})

    for phase_index in range(len(phases)):
        phase = phases[phase_index]
        phase["status"] = "active"
        phase["start_round"] = total_round_count

        # Inject phase directive
        directive = overseer.generate_phase_directive(phase_index)
        all_messages.append(directive)
        phase_messages = [directive]

        await emit("phase_directive", {
            "phase_number": phase["number"],
            "phase_name": phase["name"],
            "focus_question": phase.get("focus_question", ""),
            "subquestions": phase.get("key_subquestions", []),
            "sub_phase": "Comprehend",
        })

        phase_round_count = 0
        phase_active = True

        while phase_active and total_round_count < config.max_rounds:
            phase_round_count += 1
            overseer.phase_round_counts[phase_index] = phase_round_count

            # Drift check / evaluation
            if phase_round_count % 5 == 0:
                # Full evaluation
                evaluation = await overseer.evaluate_phase(phase_index, all_messages, total_round_count)
                await emit("overseer_phase_eval", {
                    "action": evaluation["action"],
                    "confirmed": evaluation.get("confirmed", []),
                    "contested": evaluation.get("contested", []),
                    "summary": evaluation.get("summary", ""),
                    "phase_number": phase["number"],
                })

                if evaluation["action"] == "suggest_advance":
                    await emit("phase_pause", {
                        "phase_number": phase["number"],
                        "timeout_seconds": 60,
                        "summary": evaluation.get("summary", ""),
                        "confirmed": evaluation.get("confirmed", []),
                        "contested": evaluation.get("contested", []),
                        "open_questions": evaluation.get("open_questions", []),
                        "next_phase": phase_index + 1 < len(phases),
                    })

                    command = await wait_for_command(receive, timeout=60)

                    if command == "pause_timer":
                        command = await wait_for_command(receive, timeout=None)

                    if command == "continue_phase":
                        await emit("phase_continue", {"phase_number": phase["number"], "reason": "user override"})
                        continue
                    else:
                        # advance_phase or auto_advance
                        phase_active = False
                        break
                else:
                    # Emit evaluation as overseer message
                    reason = evaluation.get("continue_reason", "")
                    if reason:
                        msg = TextMessage(content=f"[OVERSEER — Phase {phase['number']} Eval]\n{reason}", source="Overseer")
                        all_messages.append(msg)
                        phase_messages.append(msg)
                        await emit("overseer", {"content": msg.content, "round": total_round_count})

            elif phase_round_count % 5 == 3:
                # LLM drift check
                drift = await overseer.check_drift(phase_index, all_messages, total_round_count)
                if drift:
                    all_messages.append(drift)
                    phase_messages.append(drift)
                    await emit("drift_redirect", {"message": drift.content, "sub_phase": overseer.get_sub_phase(phase_round_count)[0]})
            else:
                # Keyword drift check (zero cost)
                drift = overseer.check_keyword_drift(phase_index, all_messages)
                if drift:
                    all_messages.append(drift)
                    phase_messages.append(drift)
                    await emit("drift_redirect", {"message": drift.content, "sub_phase": overseer.get_sub_phase(phase_round_count)[0]})

            # Select next speaker
            stress_ctx = overseer.get_selector_context(phase_index)
            chosen = await hybrid_selector(
                support_agent, all_messages, last_spoke, total_round_count,
                config.agent_names, config.max_rounds, None,
                stress_context=stress_ctx,
            )

            # Gate check
            if total_round_count >= config.gate_start_round:
                should_speak, claim = await run_speech_gate(
                    support_agent, chosen, all_messages, config.agent_names,
                )
                if not should_speak:
                    total_gate_skips += 1
                    await emit("gate_skip", {"agent": chosen, "round": total_round_count})
                    fallback = sorted(
                        [p for p in config.agent_names if p != chosen],
                        key=lambda p: last_spoke.get(p, 0),
                    )
                    chosen = fallback[0] if fallback else chosen

            # Agent call with streaming
            agent = agent_map[chosen]
            context = _build_stress_context(
                all_messages[0], review_instructions, documents,
                phases, phase_index, phase_messages,
            )

            await emit("agent_message", {
                "source": chosen,
                "round": total_round_count + 1,
                "streaming": True,
                "content": "",
            })

            content = ""
            try:
                stream = agent.on_messages_stream(context, CancellationToken())
                async for chunk in stream:
                    if hasattr(chunk, 'content') and isinstance(chunk.content, str):
                        content = chunk.content
                        await emit("agent_message_chunk", {
                            "source": chosen,
                            "round": total_round_count + 1,
                            "content": chunk.content,
                        })
                    elif hasattr(chunk, 'chat_message') and chunk.chat_message:
                        content = chunk.chat_message.content or ""
            except Exception:
                async def _agent_call(a=agent, ctx=context):
                    return await a.on_messages(ctx, CancellationToken())
                response = await _call_with_retry(_agent_call, label=chosen)
                if response and response.chat_message:
                    content = response.chat_message.content or ""

            if not content:
                total_round_count += 1
                continue

            msg = TextMessage(content=content, source=chosen)
            all_messages.append(msg)
            phase_messages.append(msg)
            last_spoke[chosen] = total_round_count
            persona_turns[chosen] += 1
            total_round_count += 1

            await emit("agent_message", {
                "source": chosen,
                "round": total_round_count,
                "streaming": False,
                "content": content,
            })

            # Stats
            elapsed = time.monotonic() - start_time
            avg_per_round = elapsed / max(total_round_count, 1)
            remaining = config.max_rounds - total_round_count
            sub_phase_name = overseer.get_sub_phase(phase_round_count)[0]

            await emit("stats", {
                "rounds": total_round_count,
                "gate_skips": total_gate_skips,
                "phase_number": phase["number"],
                "phase_name": phase["name"],
                "phase_round": phase_round_count,
                "sub_phase": sub_phase_name,
                "total_phases": len(phases),
                "elapsed_seconds": round(elapsed),
                "eta_seconds": round(avg_per_round * remaining),
            })

        # Phase ended — write artifact
        phase["end_round"] = total_round_count
        phase["status"] = "complete"

        artifact = await overseer.write_phase_artifact(phase_index, all_messages)
        phase["artifact"] = artifact

        await emit("phase_artifact_written", {
            "phase_number": phase["number"],
            "content": artifact,
        })

        if phase_index + 1 < len(phases):
            await emit("phase_advanced", {
                "from_phase": phase["number"],
                "to_phase": phases[phase_index + 1]["number"],
            })

    # Session close
    await emit("session_close_suggest", {
        "total_rounds": total_round_count,
        "phases_complete": len(phases),
    })

    command = await wait_for_command(receive, timeout=60)
    if command == "pause_timer":
        command = await wait_for_command(receive, timeout=None)

    if command == "continue_reviewing":
        # Run additional rounds without phases (free-form)
        # For now, just proceed to verdict
        pass

    # Generate final verdict
    await emit("verdict_generating", {})
    verdict = await overseer.generate_final_verdict()
    await emit("verdict_complete", {"content": verdict})

    stats = {
        "total_rounds": total_round_count,
        "gate_skips": total_gate_skips,
        "persona_turns": persona_turns,
        "phases_completed": len(phases),
        "terminated_by": "verdict",
    }

    return all_messages, stats, phases, verdict
```
```

- [ ] **Step 2: Verify imports**

Run:
```bash
python -c "from backend.engine.stress_brainstorm import run_stress_test; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/engine/stress_brainstorm.py
git commit -m "feat: stress test brainstorm loop with phase-aware flow"
```

---

### Task 10: Bidirectional WebSocket + session runner dispatch

**Files:**
- Modify: `backend/routers/sessions.py`
- Modify: `backend/services/session_runner.py`
- Modify: `backend/engine/config.py`

- [ ] **Step 1: Add stress_test_min_rounds_per_phase to EngineConfig**

In `backend/engine/config.py`, add to the `EngineConfig` dataclass:

```python
    stress_test_min_rounds_per_phase: int = 20
```

- [ ] **Step 2: Update WebSocket handler for bidirectional communication**

In `backend/routers/sessions.py`, replace the `session_websocket` function:

```python
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

        # Bidirectional: create command queue and receive loop
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
```

- [ ] **Step 3: Update SessionRunner to dispatch stress test mode**

In `backend/services/session_runner.py`, add import at the top:

```python
from backend.engine.stress_brainstorm import run_stress_test
```

Update the `run` method signature and add stress test dispatch:

```python
    async def run(self, receive=None):
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

        session.status = SessionStatus.running
        self.db.commit()

        try:
            mode = config.mode

            if mode == "stress_test":
                phases = session.phases or []
                documents = session.uploaded_documents or []
                review_instructions = session.stress_review_instructions or ""

                async def _receive():
                    if receive:
                        return await receive()
                    # Block forever if no receive (shouldn't happen for stress test)
                    await asyncio.sleep(999999)
                    return {"action": "auto_advance"}

                all_messages, stats, final_phases, verdict_text = await run_stress_test(
                    config, phases, documents, review_instructions,
                    self.emit, _receive,
                )

                # Build outputs
                from backend.engine.outputs import build_transcript
                transcript = build_transcript(
                    all_messages,
                    {**stats, "model": config.main_model, "max_rounds": config.max_rounds},
                    config.agent_names,
                )

                outputs = {"transcript.md": transcript}
                for phase in final_phases:
                    if phase.get("artifact"):
                        outputs[f"phase_{phase['number']}_artifact.md"] = phase["artifact"]

                outputs["verdict.md"] = verdict_text or "Verdict not generated."

                session.phases = final_phases
                session.outputs = outputs

            elif mode == "product":
                messages, stats, living_artifact = await run_brainstorm(config, self.emit)

                await self.emit("phase_transition", {"phase": "synthesis"})
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
                messages, stats, living_artifact = await run_brainstorm(config, self.emit)

                conclusion_text = await generate_conclusion(config, messages, living_artifact, self.emit)
                outputs = {
                    "transcript.md": build_transcript(messages, {**stats, "model": config.main_model, "max_rounds": config.max_rounds}, config.agent_names),
                    "artifact.md": build_artifact(living_artifact),
                    "conclusion.md": conclusion_text,
                }

            session.status = SessionStatus.complete
            session.completed_at = datetime.now(timezone.utc)
            if mode != "stress_test":
                session.transcript = outputs.get("transcript.md", "")
                session.artifact = living_artifact
            session.outputs = outputs
            self.db.commit()

            await self.emit("session_complete", {
                "terminated_by": stats.get("terminated_by", "complete"),
                "outputs": list(outputs.keys()),
            })

        except Exception as e:
            session.status = SessionStatus.error
            self.db.commit()
            await self.emit("error", {"message": str(e)})
```

Note: The existing `run` method needs the full replacement since the structure changes with the mode dispatch. Make sure `build_transcript`, `build_artifact`, `run_brainstorm`, `run_prd_mini_panel`, `generate_synthesis_and_prd`, `generate_conclusion` imports are all present.

- [ ] **Step 4: Verify everything imports**

Run:
```bash
python -c "
from backend.services.session_runner import SessionRunner
from backend.engine.stress_brainstorm import run_stress_test
from backend.engine.config import EngineConfig
c = EngineConfig(gemini_api_key='x', problem_statement='t', agents=[{'name':'A'}], stress_test_min_rounds_per_phase=15)
print(f'stress min rounds: {c.stress_test_min_rounds_per_phase}')
print('OK')
"
```
Expected: `stress min rounds: 15` then `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/routers/sessions.py backend/services/session_runner.py backend/engine/config.py
git commit -m "feat: bidirectional WebSocket + session runner dispatch for stress test"
```

---

## Phase 3: Frontend

### Task 11: Frontend types and WebSocket send

**Files:**
- Modify: `frontend/src/store/sessionStore.ts`
- Modify: `frontend/src/hooks/useWebSocket.ts`
- Modify: `frontend/src/components/setup/ModeSelector.tsx`

- [ ] **Step 1: Add types to sessionStore.ts**

Add after existing `SessionSettings` interface:

```typescript
export interface UploadedDocument {
  id: string;
  filename: string;
  filetype: string;
  content_text: string;
  size_bytes: number;
  uploaded_at: string;
}

export interface Phase {
  number: number;
  name: string;
  document_ids: string[];
  focus_question: string;
  key_subquestions: string[];
  rationale: string;
  status: 'pending' | 'active' | 'complete';
  start_round: number | null;
  end_round: number | null;
  artifact: string | null;
  confirmed: string[];
  contested: string[];
  open_questions: string[];
}
```

Add to `SessionSettings`:

```typescript
  stress_test_min_rounds_per_phase?: number;
```

Add to `SessionData`:

```typescript
  phases: Phase[] | null;
  uploaded_documents: UploadedDocument[] | null;
  stress_review_instructions: string | null;
```

- [ ] **Step 2: Add sendCommand to useWebSocket**

In `frontend/src/hooks/useWebSocket.ts`, add a `sendCommand` method:

```typescript
  const sendCommand = useCallback((action: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action }));
    }
  }, []);
```

Update the return:

```typescript
  return { connect, disconnect, connected, messages, sendCommand };
```

- [ ] **Step 3: Add Stress Test to ModeSelector**

In `frontend/src/components/setup/ModeSelector.tsx`, add the third mode option to the array:

```typescript
      {[
        { key: 'product', label: 'Product Discussion' },
        { key: 'problem_discussion', label: 'Problem Discussion' },
        { key: 'stress_test', label: 'Stress Test' },
      ].map((mode) => (
```

- [ ] **Step 4: Verify TypeScript compiles**

Run:
```bash
cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium/frontend && npx tsc --noEmit
```
Expected: Exit 0

- [ ] **Step 5: Commit**

```bash
git add frontend/src/store/sessionStore.ts frontend/src/hooks/useWebSocket.ts frontend/src/components/setup/ModeSelector.tsx
git commit -m "feat: frontend types, WS sendCommand, stress test mode option"
```

---

### Task 12: Document upload component

**Files:**
- Create: `frontend/src/components/setup/DocumentUpload.tsx`

- [ ] **Step 1: Create DocumentUpload.tsx**

```tsx
import { useState, useRef } from 'react';
import { api } from '../../api/client';
import type { UploadedDocument } from '../../store/sessionStore';

interface Props {
  documents: UploadedDocument[];
  onChange: (docs: UploadedDocument[]) => void;
}

export default function DocumentUpload({ documents, onChange }: Props) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);

    const newDocs = [...documents];
    for (const file of Array.from(files)) {
      try {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch('/api/upload/stress-test', {
          method: 'POST',
          headers: { Authorization: `Bearer ${localStorage.getItem('symposium_token')}` },
          body: formData,
        });
        if (!res.ok) {
          const err = await res.json();
          setError(err.detail || 'Upload failed');
          continue;
        }
        const data = await res.json();
        newDocs.push(data.document as UploadedDocument);
      } catch {
        setError(`Failed to upload ${file.name}`);
      }
    }
    onChange(newDocs);
    setUploading(false);
  };

  const removeDoc = (docId: string) => {
    onChange(documents.filter((d) => d.id !== docId));
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  };

  return (
    <div>
      <label className="block text-xs font-medium mb-1" style={{ color: 'var(--color-text-dim)' }}>Documents</label>

      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        onClick={() => fileRef.current?.click()}
        className="w-full py-6 rounded-lg text-center text-xs cursor-pointer transition-colors"
        style={{ border: '2px dashed var(--color-border)', color: 'var(--color-text-dim)' }}
      >
        {uploading ? 'Uploading...' : 'Drop files here or click to upload'}
        <div className="text-[10px] mt-1">PDF, DOCX, TXT, MD, XLSX, CSV — max 20MB each</div>
      </div>

      <input
        ref={fileRef}
        type="file"
        multiple
        accept=".pdf,.docx,.txt,.md,.xlsx,.csv"
        onChange={(e) => handleFiles(e.target.files)}
        className="hidden"
      />

      {error && (
        <p className="text-[10px] mt-1" style={{ color: '#f87171' }}>{error}</p>
      )}

      {documents.length > 0 && (
        <div className="mt-2 space-y-1.5">
          {documents.map((doc) => (
            <div key={doc.id} className="flex items-center justify-between p-2 rounded-lg text-xs" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)' }}>
              <div className="min-w-0">
                <span className="font-medium truncate block" style={{ color: 'var(--color-text)' }}>{doc.filename}</span>
                <span style={{ color: 'var(--color-text-dim)' }}>{formatSize(doc.size_bytes)} · {doc.filetype}</span>
              </div>
              <button onClick={(e) => { e.stopPropagation(); removeDoc(doc.id); }} className="text-[10px] px-1.5 shrink-0" style={{ color: '#f87171' }}>x</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium/frontend && npx tsc --noEmit
```
Expected: Exit 0

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/setup/DocumentUpload.tsx
git commit -m "feat: document upload component with drag-drop for stress test"
```

---

### Task 13: Phase cards component

**Files:**
- Create: `frontend/src/components/setup/PhaseCards.tsx`

- [ ] **Step 1: Create PhaseCards.tsx**

```tsx
import { useState } from 'react';
import type { Phase } from '../../store/sessionStore';

interface Props {
  phases: Phase[];
  onChange: (phases: Phase[]) => void;
  onReinterpret: () => void;
  onConfirm: () => void;
  reinterpreting: boolean;
  confirmed: boolean;
}

export default function PhaseCards({ phases, onChange, onReinterpret, onConfirm, reinterpreting, confirmed }: Props) {
  const updatePhase = (index: number, updates: Partial<Phase>) => {
    const updated = phases.map((p, i) => i === index ? { ...p, ...updates } : p);
    onChange(updated);
  };

  const addSubquestion = (index: number) => {
    const phase = phases[index];
    updatePhase(index, { key_subquestions: [...phase.key_subquestions, ''] });
  };

  const updateSubquestion = (phaseIndex: number, sqIndex: number, value: string) => {
    const phase = phases[phaseIndex];
    const sqs = [...phase.key_subquestions];
    sqs[sqIndex] = value;
    updatePhase(phaseIndex, { key_subquestions: sqs });
  };

  const removeSubquestion = (phaseIndex: number, sqIndex: number) => {
    const phase = phases[phaseIndex];
    updatePhase(phaseIndex, { key_subquestions: phase.key_subquestions.filter((_, i) => i !== sqIndex) });
  };

  const removePhase = (index: number) => {
    const updated = phases.filter((_, i) => i !== index).map((p, i) => ({ ...p, number: i + 1 }));
    onChange(updated);
  };

  if (phases.length === 0) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold" style={{ color: 'var(--color-teal)' }}>
          Review Phases ({phases.length})
        </h3>
        {!confirmed && (
          <div className="flex gap-2">
            <button onClick={onReinterpret} disabled={reinterpreting} className="text-[10px] px-2 py-1 rounded disabled:opacity-40" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>
              {reinterpreting ? 'Re-interpreting...' : 'Re-interpret'}
            </button>
            <button onClick={onConfirm} className="text-[10px] px-2 py-1 rounded font-medium" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>
              Confirm Phases
            </button>
          </div>
        )}
      </div>

      {confirmed && (
        <div className="text-[10px] px-3 py-2 rounded-lg" style={{ background: 'rgba(45, 212, 191, 0.1)', border: '1px solid var(--color-teal-dim)', color: 'var(--color-teal)' }}>
          Phases confirmed. Add agents and begin the session.
        </div>
      )}

      {phases.map((phase, i) => (
        <div key={i}>
          {/* Connector */}
          {i > 0 && (
            <div className="flex justify-center py-2">
              <div className="w-0.5 h-6" style={{ background: 'var(--color-border)' }} />
            </div>
          )}

          <div className="p-4 rounded-xl" style={{ background: 'var(--color-navy-light)', border: `1px solid ${confirmed ? 'var(--color-border)' : 'var(--color-teal-dim)'}` }}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>{phase.number}</span>
                {confirmed ? (
                  <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>{phase.name}</span>
                ) : (
                  <input
                    value={phase.name}
                    onChange={(e) => updatePhase(i, { name: e.target.value })}
                    className="text-sm font-medium bg-transparent outline-none"
                    style={{ color: 'var(--color-text)' }}
                  />
                )}
              </div>
              {!confirmed && (
                <button onClick={() => removePhase(i)} className="text-[10px]" style={{ color: '#f87171' }}>Remove</button>
              )}
            </div>

            <div className="mb-2">
              <label className="text-[10px] block mb-0.5" style={{ color: 'var(--color-text-dim)' }}>Focus Question</label>
              {confirmed ? (
                <p className="text-xs" style={{ color: 'var(--color-text)' }}>{phase.focus_question}</p>
              ) : (
                <textarea
                  value={phase.focus_question}
                  onChange={(e) => updatePhase(i, { focus_question: e.target.value })}
                  rows={2}
                  className="w-full px-2 py-1 rounded text-xs outline-none resize-y"
                  style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                />
              )}
            </div>

            <div className="mb-2">
              <label className="text-[10px] block mb-0.5" style={{ color: 'var(--color-text-dim)' }}>Subquestions</label>
              {phase.key_subquestions.map((sq, sqI) => (
                <div key={sqI} className="flex items-center gap-1 mb-1">
                  <span className="text-[10px] shrink-0" style={{ color: 'var(--color-text-dim)' }}>·</span>
                  {confirmed ? (
                    <span className="text-xs" style={{ color: 'var(--color-text)' }}>{sq}</span>
                  ) : (
                    <>
                      <input
                        value={sq}
                        onChange={(e) => updateSubquestion(i, sqI, e.target.value)}
                        className="flex-1 px-2 py-0.5 rounded text-xs outline-none"
                        style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
                      />
                      <button onClick={() => removeSubquestion(i, sqI)} className="text-[10px] px-1" style={{ color: '#f87171' }}>x</button>
                    </>
                  )}
                </div>
              ))}
              {!confirmed && (
                <button onClick={() => addSubquestion(i)} className="text-[10px] mt-1" style={{ color: 'var(--color-teal-dim)' }}>+ Add subquestion</button>
              )}
            </div>

            {phase.rationale && (
              <p className="text-[10px] italic" style={{ color: 'var(--color-text-dim)' }}>{phase.rationale}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium/frontend && npx tsc --noEmit
```
Expected: Exit 0

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/setup/PhaseCards.tsx
git commit -m "feat: editable phase cards component for stress test setup"
```

---

### Task 14: Phase pause card and document sidebar components

**Files:**
- Create: `frontend/src/components/session/PhasePauseCard.tsx`
- Create: `frontend/src/components/session/DocumentSidebar.tsx`

- [ ] **Step 1: Create PhasePauseCard.tsx**

```tsx
import { useState, useEffect } from 'react';

interface Props {
  phaseNumber: number;
  summary: string;
  confirmed: string[];
  contested: string[];
  openQuestions: string[];
  hasNextPhase: boolean;
  onAdvance: () => void;
  onContinue: () => void;
  onPauseTimer: () => void;
}

export default function PhasePauseCard({ phaseNumber, summary, confirmed, contested, openQuestions, hasNextPhase, onAdvance, onContinue, onPauseTimer }: Props) {
  const [countdown, setCountdown] = useState(60);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused) return;
    if (countdown <= 0) {
      onAdvance();
      return;
    }
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [countdown, paused, onAdvance]);

  const handlePause = () => {
    setPaused(true);
    onPauseTimer();
  };

  return (
    <div className="my-4 p-4 rounded-xl" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-teal)' }}>
      <h3 className="text-sm font-bold mb-2" style={{ color: 'var(--color-teal)' }}>
        Phase {phaseNumber} Review Complete
      </h3>

      {summary && <p className="text-xs mb-3" style={{ color: 'var(--color-text)' }}>{summary}</p>}

      {confirmed.length > 0 && (
        <div className="mb-2">
          <p className="text-[10px] font-medium" style={{ color: '#2dd4bf' }}>Confirmed:</p>
          <ul className="pl-3">{confirmed.map((item, i) => <li key={i} className="text-xs" style={{ color: 'var(--color-text-dim)' }}>· {item}</li>)}</ul>
        </div>
      )}

      {contested.length > 0 && (
        <div className="mb-2">
          <p className="text-[10px] font-medium" style={{ color: '#fbbf24' }}>Contested:</p>
          <ul className="pl-3">{contested.map((item, i) => <li key={i} className="text-xs" style={{ color: 'var(--color-text-dim)' }}>· {item}</li>)}</ul>
        </div>
      )}

      {openQuestions.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] font-medium" style={{ color: '#f87171' }}>Open Questions:</p>
          <ul className="pl-3">{openQuestions.map((item, i) => <li key={i} className="text-xs" style={{ color: 'var(--color-text-dim)' }}>· {item}</li>)}</ul>
        </div>
      )}

      <div className="flex items-center gap-2">
        {hasNextPhase ? (
          <button onClick={onAdvance} className="flex-1 py-2 rounded-lg text-xs font-medium" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>
            Advance to Phase {phaseNumber + 1}
          </button>
        ) : (
          <button onClick={onAdvance} className="flex-1 py-2 rounded-lg text-xs font-medium" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>
            Generate Final Verdict
          </button>
        )}
        <button onClick={onContinue} className="flex-1 py-2 rounded-lg text-xs" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>
          Continue Phase {phaseNumber}
        </button>
      </div>

      <div className="flex items-center justify-between mt-2">
        {!paused ? (
          <>
            <span className="text-[10px]" style={{ color: countdown <= 10 ? '#f87171' : 'var(--color-text-dim)' }}>
              Auto-advancing in {countdown}s
            </span>
            <button onClick={handlePause} className="text-[10px] px-2 py-0.5 rounded" style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-dim)' }}>
              Pause Timer
            </button>
          </>
        ) : (
          <span className="text-[10px]" style={{ color: 'var(--color-text-dim)' }}>Timer paused — waiting for your decision</span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create DocumentSidebar.tsx**

```tsx
import type { UploadedDocument, Phase } from '../../store/sessionStore';

interface Props {
  documents: UploadedDocument[];
  phases: Phase[];
  currentPhaseIndex: number;
}

export default function DocumentSidebar({ documents, phases, currentPhaseIndex }: Props) {
  const currentPhase = phases[currentPhaseIndex];
  const currentDocIds = new Set(currentPhase?.document_ids || []);
  const previousDocIds = new Set(
    phases.slice(0, currentPhaseIndex).flatMap((p) => p.document_ids || [])
  );

  const getDocStatus = (docId: string): 'current' | 'previous' | 'future' => {
    if (currentDocIds.has(docId)) return 'current';
    if (previousDocIds.has(docId)) return 'previous';
    return 'future';
  };

  const statusStyles = {
    current: { border: '1px solid var(--color-teal)', color: 'var(--color-text)', opacity: 1 },
    previous: { border: '1px solid var(--color-border)', color: 'var(--color-text-dim)', opacity: 0.6 },
    future: { border: '1px solid var(--color-border)', color: 'var(--color-text-dim)', opacity: 0.3 },
  };

  const statusLabels = { current: 'Active', previous: 'Reviewed', future: 'Upcoming' };

  return (
    <div className="h-full overflow-y-auto p-3" style={{ background: 'var(--color-navy-light)', borderRight: '1px solid var(--color-border)' }}>
      <h3 className="text-xs font-bold mb-3" style={{ color: 'var(--color-teal)' }}>Documents</h3>

      {documents.map((doc) => {
        const status = getDocStatus(doc.id);
        const styles = statusStyles[status];
        return (
          <div key={doc.id} className="p-2 rounded-lg mb-2 text-xs" style={{ background: 'var(--color-navy)', ...styles, opacity: styles.opacity }}>
            <p className="font-medium truncate" style={{ color: styles.color }}>{doc.filename}</p>
            <div className="flex justify-between mt-0.5">
              <span className="text-[10px]" style={{ color: 'var(--color-text-dim)' }}>{doc.filetype}</span>
              <span className="text-[10px]" style={{ color: status === 'current' ? 'var(--color-teal)' : 'var(--color-text-dim)' }}>{statusLabels[status]}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run:
```bash
cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium/frontend && npx tsc --noEmit
```
Expected: Exit 0

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/session/PhasePauseCard.tsx frontend/src/components/session/DocumentSidebar.tsx
git commit -m "feat: phase pause card with countdown and document sidebar components"
```

---

### Task 15: Wire stress test into Canvas.tsx

**Files:**
- Modify: `frontend/src/pages/Canvas.tsx`

- [ ] **Step 1: Add stress test imports and state**

Add imports at the top of Canvas.tsx:

```tsx
import DocumentUpload from '../components/setup/DocumentUpload';
import PhaseCards from '../components/setup/PhaseCards';
import DocumentSidebar from '../components/session/DocumentSidebar';
import PhasePauseCard from '../components/session/PhasePauseCard';
import type { UploadedDocument, Phase } from '../store/sessionStore';
```

Add state variables after existing state declarations:

```tsx
  // Stress test state
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDocument[]>([]);
  const [phases, setPhases] = useState<Phase[]>([]);
  const [phasesConfirmed, setPhasesConfirmed] = useState(false);
  const [reviewInstructions, setReviewInstructions] = useState('');
  const [analysing, setAnalysing] = useState(false);
  const [reinterpreting, setReinterpreting] = useState(false);
```

- [ ] **Step 2: Add stress test handler functions**

Add after existing handler functions:

```tsx
  const handleAnalyseDocuments = async () => {
    if (!id) return;
    // Save docs to session first
    await updateSession(id, { uploaded_documents: uploadedDocs as any });
    setAnalysing(true);
    try {
      const res = await api.post<{ phases: Phase[]; review_instructions: string }>(`/sessions/${id}/stress/analyse-documents`);
      // Map document filenames to IDs for phase.document_ids
      const phasesWithIds = (res.phases || []).map((p: any, i: number) => ({
        ...p,
        number: i + 1,
        status: 'pending' as const,
        document_ids: p.document_ids || uploadedDocs.map((d) => d.id),
        key_subquestions: p.key_subquestions || [],
        start_round: null,
        end_round: null,
        artifact: null,
        confirmed: [],
        contested: [],
        open_questions: [],
      }));
      setPhases(phasesWithIds);
      setReviewInstructions(res.review_instructions || '');
    } catch {
      // ignore
    } finally {
      setAnalysing(false);
    }
  };

  const handleReinterpret = async () => {
    if (!id) return;
    setReinterpreting(true);
    try {
      const res = await api.post<{ phases: Phase[] }>(`/sessions/${id}/stress/reinterpret-phases`, { phases });
      if (res.phases) {
        setPhases(res.phases.map((p: any, i: number) => ({ ...p, number: i + 1 })));
      }
    } catch {
      // ignore
    } finally {
      setReinterpreting(false);
    }
  };

  const handleConfirmPhases = async () => {
    if (!id) return;
    await api.post(`/sessions/${id}/stress/confirm-phases`, { phases, review_instructions: reviewInstructions });
    setPhasesConfirmed(true);
  };
```

- [ ] **Step 3: Update handleConfirmStart to include stress test settings**

In the existing `handleConfirmStart`, add stress test fields to the settings:

```tsx
  const handleConfirmStart = async () => {
    setShowConfirm(false);
    const finalSettings = {
      ...settings,
      prd_panel_names: prdPanelNames,
      stress_test_min_rounds_per_phase: settings.stress_test_min_rounds_per_phase || 20,
    };
    // ... rest of existing code
  };
```

- [ ] **Step 4: Add stress test sections to the sidebar**

In the setup mode sidebar (the `return` block with `<div className="w-80 ...`), add stress test sections after the ModeSelector, conditionally:

```tsx
        {mode === 'stress_test' && (
          <>
            <DocumentUpload documents={uploadedDocs} onChange={setUploadedDocs} />
          </>
        )}

        <ProblemStatement value={problemStatement} onChange={setProblemStatement} />
        <ModeSelector value={mode} onChange={setMode} />

        {mode === 'stress_test' && uploadedDocs.length > 0 && problemStatement.length > 20 && !phases.length && (
          <button onClick={handleAnalyseDocuments} disabled={analysing} className="w-full py-2 rounded-lg text-sm disabled:opacity-40" style={{ border: '1px solid var(--color-teal-dim)', color: 'var(--color-teal-dim)' }}>
            {analysing ? 'Analysing documents...' : 'Analyse Documents'}
          </button>
        )}

        {mode !== 'stress_test' && (
          <button onClick={handleSuggestAgents} disabled={suggestingAgents || problemStatement.length < 20} className="w-full py-2 rounded-lg text-sm disabled:opacity-40" style={{ border: '1px solid var(--color-teal-dim)', color: 'var(--color-teal-dim)' }}>
            {suggestingAgents ? 'Generating agents...' : 'Suggest Agents'}
          </button>
        )}
```

- [ ] **Step 5: Replace canvas main area for phase definition**

In the setup mode, when stress test phases exist but aren't confirmed, show PhaseCards instead of ReactFlow:

```tsx
      {/* Main area */}
      <div className="flex-1 h-full">
        {mode === 'stress_test' && phases.length > 0 && !phasesConfirmed ? (
          <div className="h-full overflow-y-auto p-6">
            <PhaseCards
              phases={phases}
              onChange={setPhases}
              onReinterpret={handleReinterpret}
              onConfirm={handleConfirmPhases}
              reinterpreting={reinterpreting}
              confirmed={phasesConfirmed}
            />

            {reviewInstructions && (
              <div className="mt-4">
                <label className="text-[10px] block mb-1 uppercase tracking-wider" style={{ color: 'var(--color-text-dim)' }}>Review Instructions (editable)</label>
                <textarea
                  value={reviewInstructions}
                  onChange={(e) => setReviewInstructions(e.target.value)}
                  rows={8}
                  className="w-full px-3 py-2 rounded-lg text-xs outline-none resize-y"
                  style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)', color: 'var(--color-text)', fontFamily: 'monospace' }}
                />
              </div>
            )}
          </div>
        ) : (
          <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={handleNodeClick} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}>
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e2438" />
          </ReactFlow>
        )}
      </div>
```

- [ ] **Step 6: Update live mode for stress test**

In the live mode (`if (isLive)` block), replace the left canvas panel with DocumentSidebar for stress test:

```tsx
  if (isLive) {
    return (
      <div className="h-screen flex flex-col overflow-hidden" style={{ background: 'var(--color-navy)' }}>
        <StatsBar messages={wsMessages} maxRounds={settings.max_rounds} />
        <div className="flex-1 flex min-h-0">
          <div className="w-2/5 h-full" style={{ borderRight: '1px solid var(--color-border)' }}>
            {mode === 'stress_test' && uploadedDocs.length > 0 ? (
              <DocumentSidebar
                documents={uploadedDocs}
                phases={phases}
                currentPhaseIndex={/* get from latest stats message */ 0}
              />
            ) : (
              <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}>
                <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e2438" />
              </ReactFlow>
            )}
          </div>
          {/* ... rest same ... */}
        </div>
      </div>
    );
  }
```

- [ ] **Step 7: Verify TypeScript compiles**

Run:
```bash
cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium/frontend && npx tsc --noEmit
```
Expected: Exit 0

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/Canvas.tsx
git commit -m "feat: wire stress test setup flow into Canvas page"
```

---

### Task 16: LiveFeed + StatsBar + ArtifactPanel updates

**Files:**
- Modify: `frontend/src/components/session/LiveFeed.tsx`
- Modify: `frontend/src/components/session/StatsBar.tsx`
- Modify: `frontend/src/components/session/ArtifactPanel.tsx`

- [ ] **Step 1: Add phase events to LiveFeed**

In `LiveFeed.tsx`, add handlers for new message types in the render loop, after existing `phase_transition` handler:

```tsx
        if (msg.type === 'phase_directive') {
          return (
            <div key={i} className="py-4 text-center">
              <div className="inline-block px-4 py-2 rounded-lg text-sm font-medium" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>
                Phase {msg.phase_number as number}: {msg.phase_name as string}
              </div>
              <p className="text-xs mt-1" style={{ color: 'var(--color-text-dim)' }}>{msg.focus_question as string}</p>
            </div>
          );
        }
        if (msg.type === 'drift_redirect') {
          return (
            <div key={i} className="px-3 py-2 text-xs rounded" style={{ background: '#1a1a2e', border: '1px solid #333', color: '#fbbf24' }}>
              {msg.message as string}
            </div>
          );
        }
        if (msg.type === 'phase_artifact_written') {
          return (
            <div key={i} className="py-4 text-center">
              <div className="inline-block px-4 py-2 rounded-lg text-xs" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-teal-dim)', color: 'var(--color-teal)' }}>
                Phase {msg.phase_number as number} artifact written
              </div>
            </div>
          );
        }
        if (msg.type === 'verdict_generating') {
          return (
            <div key={i} className="py-4 text-center">
              <div className="inline-block px-4 py-2 rounded-lg text-sm font-medium animate-pulse" style={{ background: 'var(--color-teal)', color: 'var(--color-navy)' }}>
                Generating final readiness verdict...
              </div>
            </div>
          );
        }
        if (msg.type === 'verdict_complete') {
          return (
            <div key={i} className="py-4">
              <div className="p-4 rounded-xl" style={{ background: 'var(--color-navy-light)', border: '1px solid var(--color-teal)' }}>
                <h3 className="text-sm font-bold mb-2" style={{ color: 'var(--color-teal)' }}>Final Readiness Verdict</h3>
                <CollapsibleMessage content={msg.content as string} />
              </div>
            </div>
          );
        }
```

Note: `phase_pause` events will be handled by the parent Canvas component which renders PhasePauseCard, not by LiveFeed directly.

- [ ] **Step 2: Update StatsBar for phase awareness**

In `StatsBar.tsx`, add phase info from stats:

```tsx
  const phaseNumber = (latestStats?.phase_number as number) || null;
  const phaseName = (latestStats?.phase_name as string) || '';
  const subPhase = (latestStats?.sub_phase as string) || '';
  const totalPhases = (latestStats?.total_phases as number) || 0;
```

Add after the existing Overseer stat div:

```tsx
      {phaseNumber && (
        <div>
          <span style={{ color: 'var(--color-text-dim)' }}>Phase: </span>
          <span style={{ color: 'var(--color-teal)' }}>{phaseNumber}/{totalPhases}</span>
          <span style={{ color: 'var(--color-text-dim)' }}> — {phaseName}</span>
        </div>
      )}
      {subPhase && (
        <div>
          <span style={{ color: 'var(--color-text-dim)' }}>{subPhase}</span>
        </div>
      )}
```

- [ ] **Step 3: Update ArtifactPanel for per-phase artifacts**

In `ArtifactPanel.tsx`, add handling for `phase_artifact_written` messages. The existing panel shows artifact sections — for stress test, each phase artifact becomes a collapsible section:

Add after existing artifact handling:

```tsx
  const phaseArtifacts = messages
    .filter((m) => m.type === 'phase_artifact_written')
    .map((m) => ({ phase: m.phase_number as number, content: m.content as string }));
```

Render phase artifacts:

```tsx
  {phaseArtifacts.map((pa) => (
    <div key={`phase-${pa.phase}`} className="p-3 rounded-lg mb-2" style={{ background: 'var(--color-navy)', border: '1px solid var(--color-border)' }}>
      <CollapsibleMessage content={`PHASE ${pa.phase} ARTIFACT\n\n${pa.content}`} />
    </div>
  ))}
```

Note: You'll need to either import or inline a CollapsibleMessage component (or reuse the one from LiveFeed — extract it to a shared component if not already).

- [ ] **Step 4: Verify TypeScript compiles**

Run:
```bash
cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium/frontend && npx tsc --noEmit
```
Expected: Exit 0

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/session/LiveFeed.tsx frontend/src/components/session/StatsBar.tsx frontend/src/components/session/ArtifactPanel.tsx
git commit -m "feat: LiveFeed phase events, StatsBar phase indicator, ArtifactPanel per-phase artifacts"
```

---

### Task 17: Results page — per-phase tabs and verdict

**Files:**
- Modify: `frontend/src/pages/Results.tsx`

- [ ] **Step 1: Update Results page for stress test outputs**

The Results page already shows tabs from `outputs` keys. For stress test, the outputs will include `phase_1_artifact.md`, `phase_2_artifact.md`, ..., `verdict.md`, `transcript.md`. The existing tab system handles this automatically since it iterates `Object.keys(outputs)`.

Update the tab display to highlight the verdict tab and order tabs logically:

```tsx
  const tabs = Object.keys(outputs);
  // Sort: verdict first, then phases in order, then transcript last
  const sortedTabs = [...tabs].sort((a, b) => {
    if (a.includes('verdict')) return -1;
    if (b.includes('verdict')) return 1;
    if (a.includes('phase') && b.includes('phase')) return a.localeCompare(b);
    if (a.includes('transcript')) return 1;
    if (b.includes('transcript')) return -1;
    return 0;
  });
```

Use `sortedTabs` instead of `tabs` in the tab rendering. Add a highlight style for the verdict tab:

```tsx
  {sortedTabs.map((tab) => (
    <button key={tab} onClick={() => setActiveTab(tab)} className="px-4 py-2 text-sm rounded-t-lg" style={{
      background: activeTab === tab ? 'var(--color-navy-light)' : 'transparent',
      color: activeTab === tab ? 'var(--color-teal)' : tab.includes('verdict') ? '#fbbf24' : 'var(--color-text-dim)',
      borderBottom: activeTab === tab ? '2px solid var(--color-teal)' : '2px solid transparent',
      fontWeight: tab.includes('verdict') ? 'bold' : 'normal',
    }}>
      {tab.replace('.md', '').replace(/_/g, ' ')}
    </button>
  ))}
```

- [ ] **Step 2: Set default tab to verdict for stress test**

Update the default tab selection:

```tsx
  useEffect(() => {
    if (currentSession?.outputs) {
      const tabs = Object.keys(currentSession.outputs);
      if (tabs.length > 0 && !activeTab) {
        const defaultTab = tabs.find((t) => t.includes('verdict'))
          || tabs.find((t) => t.includes('prd') || t.includes('conclusion'))
          || tabs[0];
        setActiveTab(defaultTab);
      }
    }
  }, [currentSession, activeTab]);
```

- [ ] **Step 3: Verify TypeScript compiles**

Run:
```bash
cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium/frontend && npx tsc --noEmit
```
Expected: Exit 0

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Results.tsx
git commit -m "feat: Results page with per-phase artifact tabs and verdict highlight"
```

---

## Phase 4: Integration

### Task 18: End-to-end verification

- [ ] **Step 1: Verify all backend imports**

Run:
```bash
python -c "
from backend.main import app
from backend.services.doc_extract import extract_text
from backend.services.stress_suggest import analyse_documents
from backend.engine.stress_brainstorm import run_stress_test
from backend.engine.stress_overseer import StressOverseer
from backend.routers.stress_test import router
print('All backend imports OK')
"
```
Expected: `All backend imports OK`

- [ ] **Step 2: Verify frontend compiles**

Run:
```bash
cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium/frontend && npx tsc --noEmit && echo "TypeScript OK"
```
Expected: `TypeScript OK`

- [ ] **Step 3: Verify production build**

Run:
```bash
cd /Users/aryanjakhar/Desktop/Lemnisca/Symposium/frontend && npx vite build && echo "Build OK"
```
Expected: `Build OK`

- [ ] **Step 4: Verify all API routes registered**

Run:
```bash
python -c "
from backend.main import app
routes = []
for route in app.routes:
    if hasattr(route, 'methods'):
        routes.append(f'{sorted(route.methods)} {route.path}')
    elif hasattr(route, 'routes'):
        prefix = getattr(route, 'prefix', '')
        for r in route.routes:
            if hasattr(r, 'methods'):
                routes.append(f'{sorted(r.methods)} {prefix}{r.path}')
for r in sorted(routes):
    print(r)
"
```
Expected: All existing routes plus new stress test routes

- [ ] **Step 5: Commit all remaining changes**

```bash
git add -A
git commit -m "feat: stress test mode — complete implementation"
```

---

## Summary

| Task | What it delivers |
|------|-----------------|
| 1 | New dependencies (pypdf, python-docx, openpyxl, pandas) |
| 2 | Data model: stress_test mode, Phase, UploadedDocument schemas |
| 3 | Document text extraction service |
| 4 | Upload endpoint with text extraction |
| 5 | Phase inference + re-interpret AI service |
| 6 | All stress test API endpoints |
| 7 | StressOverseer class (stateful phase controller) |
| 8 | Phase-aware selector |
| 9 | Stress test brainstorm loop |
| 10 | Bidirectional WebSocket + session runner dispatch |
| 11 | Frontend types, WS sendCommand, mode option |
| 12 | Document upload component |
| 13 | Phase cards component |
| 14 | Phase pause card + document sidebar |
| 15 | Canvas.tsx stress test wiring |
| 16 | LiveFeed, StatsBar, ArtifactPanel updates |
| 17 | Results page per-phase tabs + verdict |
| 18 | End-to-end verification |

**Total tasks: 18**
**Estimated new files: 10**
**Estimated modified files: 14**
