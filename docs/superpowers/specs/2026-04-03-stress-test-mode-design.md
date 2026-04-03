# Stress Test Mode — Design Spec

> Symposium third mode: multi-phase document stress-testing with phase-aware Overseer control.

---

## 1. Overview

Stress Test mode lets users upload documents (roadmaps, strategy packs, research reports) and have agents review them phase by phase — challenging logic, finding weaknesses, checking dependency sequencing, confirming what's sound, and producing structured artifacts per phase plus a final readiness verdict.

It shares all existing infrastructure (canvas, agents, gate, selector, WebSocket streaming) but adds: document upload with text extraction, AI-proposed phase definitions, a stateful StressOverseer with sub-phases, bidirectional WebSocket for pause/resume, and per-phase artifact generation.

---

## 2. Data Model Extensions

### Session model (extend existing)

```
mode: enum → add "stress_test" to existing product | problem_discussion
phases: JSON column (list[Phase]) — null for non-stress-test
current_phase_index: Integer — null for non-stress-test
uploaded_documents: JSON column (list[UploadedDocument]) — null for non-stress-test
stress_review_instructions: Text — null for non-stress-test, AI-generated, user-editable
```

### Phase structure (stored as JSON on Session)

```
Phase:
  number: int
  name: str
  document_ids: list[str]       # which uploaded docs belong to this phase
  focus_question: str
  key_subquestions: list[str]
  rationale: str
  status: "pending" | "active" | "complete"
  start_round: int | null
  end_round: int | null
  artifact: str | null          # written when phase closes
  confirmed: list[str]
  contested: list[str]
  open_questions: list[str]
```

### UploadedDocument structure (stored as JSON on Session)

```
UploadedDocument:
  id: str (uuid)
  filename: str
  filetype: str
  content_text: str             # extracted at upload time
  size_bytes: int
  uploaded_at: str (ISO)
```

### SessionSettings extension

```
stress_test_min_rounds_per_phase: int (default 20, range 10-40)
```

`stress_test_min_total_rounds` is computed at runtime: `len(phases) * min_rounds_per_phase`. Not stored.

No new database tables. Everything is JSON columns on the existing Session model.

---

## 3. Document Upload & Text Extraction

### Endpoint

`POST /api/upload/stress-test` — accepts multipart file upload.

### Per-file flow

1. Validate: max 20MB, allowed types (pdf, docx, txt, md, xlsx, csv)
2. Extract text immediately based on filetype:
   - PDF → `pypdf` (PdfReader, extract page text)
   - DOCX → `python-docx` (iterate paragraphs + tables)
   - XLSX → `openpyxl` + convert to markdown table
   - CSV → `pandas` read_csv + to_markdown
   - TXT/MD → read as-is
3. If images/charts detected in PDFs, append warning: `"[Note: This document contains images/charts that could not be extracted as text.]"`
4. Return: `{ id, filename, filetype, size_bytes, preview (first 500 chars), uploaded_at }`
5. If extraction fails, return 422 with specific error

### Storage

No file system storage of raw files. Extracted `content_text` stored directly in session's `uploaded_documents` JSON. Raw files discarded after extraction.

### New file

`backend/services/doc_extract.py` — single function `extract_text(file_bytes, filename) -> str` that dispatches by extension.

### New dependencies

```
pypdf
python-docx
openpyxl
pandas
```

---

## 4. Phase Inference & Re-interpret Loop

### Endpoints (all in `backend/routers/stress_test.py`, prefix `/api/sessions/{id}/stress`)

**`POST .../analyse-documents`** — sends uploaded docs + problem statement to Gemini Flash. Returns proposed phases. The phase inference prompt sequences phases so dependency-heavy sections are reviewed before things that depend on them.

**`POST .../reinterpret-phases`** — takes user's edited phases + documents + problem statement. Returns updated phase plan with explanation of changes.

**`POST .../confirm-phases`** — locks phases into session. Sets all statuses to `pending`, `current_phase_index` to 0. Enables "Begin Symposium" button.

### AI logic

Lives in `backend/services/stress_suggest.py`. Functions: `analyse_documents()`, `reinterpret_phases()`.

Phase inference prompt instructs AI to:
- Focus each phase on a coherent subset of documents
- Sequence so earlier phases inform later ones (dependencies reviewed first)
- Flag cross-document dependencies explicitly in subquestions
- Estimate 20-30 rounds per phase

### User flow

1. Upload docs → `POST /api/upload/stress-test`
2. Write problem statement → patch session
3. Click "Analyse Documents" → `POST .../analyse-documents` → phases returned
4. Edit phases → click "Re-interpret" → `POST .../reinterpret-phases` → updated phases
5. Repeat step 4 until satisfied
6. Click "Confirm Phases" → `POST .../confirm-phases` → phases locked

---

## 5. Agent Suggestion for Stress Test

### Endpoint

`POST /api/sessions/{id}/stress/suggest-agents`

### How it differs from existing suggest_agents

Agents are designed around documents and phases, not just the problem statement. Each agent has a **lens** — what they specifically look for in documents. The lens is used by the phase-aware selector to prioritize agents during relevant sub-phases.

### Mandatory agent types

- **Domain expert** — knows the subject matter of the documents
- **Logic challenger** — finds contradictions, weak reasoning, unsupported claims
- **Execution realist** — challenges whether what's written can actually be done
- **Scope guardian** — checks whether documents cover what they claim to cover

### Function

`suggest_stress_test_agents(documents, phases, problem_statement) -> list` in `backend/services/stress_suggest.py`.

### Frontend

Same card UI as existing agent suggestions. Each card additionally shows the "Lens" field.

---

## 6. Stress Test Brainstorm Loop

### New file: `backend/engine/stress_brainstorm.py`

Separate loop from existing `run_brainstorm()`. Shares imports (gate, selector, clients, retry) but has its own flow.

### Function signature

```python
async def run_stress_test(config, phases, documents, emit, receive):
```

`receive` is an async callable backed by `asyncio.Queue` — yields commands from the WebSocket client.

### Loop structure

```
for each phase in phases:
    inject phase directive
    phase_round_count = 0
    
    while phase_round_count < max_rounds_remaining:
        # Selector (with stress_context) → gate → agent call → stream → emit
        phase_round_count += 1
        total_round_count += 1
        
        if phase_round_count % 5 == 0:
            evaluation = stress_overseer.evaluate_phase(...)
            if evaluation.action == "suggest_advance":
                emit("phase_pause", ...)
                command = await wait_for_command(receive, timeout=60)
                handle command (advance / continue / pause_timer / auto_advance)
        elif phase_round_count % 5 == 3:
            # LLM drift check (1 Flash call)
            drift = stress_overseer.check_drift(...)
            if drift: inject redirect message
        else:
            # Keyword drift check (zero cost)
            drift = stress_overseer.check_keyword_drift(...)
            if drift: inject redirect message

# All phases done → session close suggestion → final verdict
```

### Context building per round

```
1. Problem statement (messages[0])
2. Stress test review instructions (AI-generated from session.stress_review_instructions)
3. Current phase docs — FULL TEXT
4. Previous phase docs — ARTIFACT ONLY (compact carry-forward)
5. Future phase docs — NOT INCLUDED
6. Conversation history (current phase messages)
7. Current phase directive (focus question, subquestions, carry-forward)
8. Agent persona
```

### Stress Test Review Instructions (generated, not hardcoded)

The review instructions are **generated by the AI during phase inference** (`analyse_documents()`), tailored to the specific documents being reviewed. They are stored on the session as `stress_review_instructions` (new JSON field) and injected into every agent's context.

The phase inference prompt includes:
```
Also generate a REVIEW INSTRUCTIONS block specific to these documents.
What should every reviewer check for given this type of work product?
Include domain-specific checks (not generic quality checks).
Return as "review_instructions": "..." in the JSON response.
```

**Examples of what the AI might generate:**

For a product roadmap:
```
STRESS TEST REVIEW INSTRUCTIONS
════════════════════════════════
- Are execution dependencies between items explicitly stated or assumed?
- Is the proposed sequence realistic given the dependencies?
- Are parallel workstreams truly independent or do they share a bottleneck?
- What must be true before this plan can start that isn't stated?
- Flag every dependency assumption you find. Name the specific items.
```

For a research paper:
```
STRESS TEST REVIEW INSTRUCTIONS
════════════════════════════════
- Is every causal claim supported by cited evidence or stated as an assumption?
- Does the methodology justify the conclusions drawn?
- Are there alternative interpretations of the data that weren't addressed?
- Which findings depend on sample size or selection criteria?
- Flag every unsupported inference. Name the specific claim and what's missing.
```

**User can edit** the generated instructions in the phase definition UI alongside the phase cards, before confirming phases. This allows domain experts to add checks the AI missed.

---

## 7. StressOverseer

### New file: `backend/engine/stress_overseer.py`

Stateful class (unlike existing stateless overseer).

### Class structure

```
class StressOverseer:
    __init__(support_agent, phases, documents, config):
        self.phases = phases
        self.documents = documents
        self.phase_round_counts = {i: 0 for i in range(len(phases))}
        self.carry_forward = {"confirmed": [], "contested": [], "open_questions": []}

    get_sub_phase(phase_round_count, min_rounds_per_phase) -> str
        # Returns sub-phase based on % of phase rounds completed

    get_selector_context(phase_index) -> dict
        # Returns stress_context dict for the selector

    generate_phase_directive(phase_index) -> TextMessage
        # [PHASE N NOW ACTIVE] message with focus, subquestions, carry-forward

    check_keyword_drift(phase_index, messages) -> TextMessage | None
        # Zero LLM cost — checks if last 3 messages contain phase focus keywords
        # Returns template redirect or None if on track

    check_drift(phase_index, messages, round_num) -> TextMessage | None
        # LLM call (Flash) — last 5 messages. Returns redirect or None if on track.

    generate_reminder(phase_index, messages, round_num) -> TextMessage
        # Constraint reminder scoped to current phase (if drift detected)

    evaluate_phase(phase_index, messages, round_num) -> PhaseEvaluation
        # Full evaluation every 5 rounds
        # Returns: { action, confirmed, contested, open_questions, summary }
        # Will NOT suggest_advance if round_num < min_rounds_per_phase

    write_phase_artifact(phase_index, messages) -> str
        # Structured artifact: CONFIRMED SOUND / CONTESTED / MUST FIX / OPEN QUESTIONS / CROSS-DOC CONTRADICTIONS
        # Updates self.carry_forward

    evaluate_session_close(total_rounds) -> bool
        # True if all phases complete AND total_rounds >= min_total_rounds

    generate_final_verdict(all_phase_artifacts) -> str
        # READY / NOT READY / CONDITIONALLY READY
```

### Sub-phases within each phase

| % of phase rounds | Sub-phase | Directive |
|---|---|---|
| 0-20% | Comprehend | Read documents. State claims. Identify assertions. No challenges yet. |
| 20-45% | Challenge | Poke holes. Weak logic, unsupported claims, contradictions. Be adversarial. |
| 45-65% | Cross-examine | Respond to challenges. Defend or concede. Force resolution per claim. |
| 65-85% | Synthesize | Build confirmed/contested/open list. What's sound, what's not. |
| 85-100% | Conclude | Final positions. Each agent states verdict on focus question. No new challenges. |

### Cadence

| Round in phase | Action | Cost |
|---|---|---|
| 1, 2 | Keyword-based drift check — match recent messages against phase focus question keywords, same pattern as convergence detector | Zero LLM cost |
| 3 | LLM drift check via `check_drift()` — Flash call, last 5 messages | 1 Flash call |
| 4 | Keyword-based drift check | Zero LLM cost |
| 5 | Full phase evaluation via `evaluate_phase()` — Flash call | 1 Flash call |

This pattern repeats every 5 rounds. Over 100 rounds: ~20 Flash drift checks + ~20 Flash evaluations = ~40 Flash calls total (vs 80+ if checking every round).

Keyword drift check (`check_keyword_drift()`) is a zero-cost function that checks if the last 3 agent messages contain any of the current phase's focus question keywords or subquestion keywords. If none match, it emits a redirect message using a template (no LLM call): `"[OVERSEER] Stay focused on: {focus_question}"`

---

## 8. Bidirectional WebSocket

### Modified: `backend/routers/sessions.py`

```python
async def session_websocket(websocket, session_id):
    await websocket.accept()
    init_msg = await websocket.receive_json()
    
    command_queue = asyncio.Queue()
    
    async def receive_loop():
        while True:
            try:
                msg = await websocket.receive_json()
                await command_queue.put(msg)
            except WebSocketDisconnect:
                await command_queue.put({"action": "disconnected"})
                break
    
    receive_task = asyncio.create_task(receive_loop())
    runner = SessionRunner(websocket, session, db, api_key)
    await runner.run(receive=command_queue.get)
    receive_task.cancel()
```

### Client commands

```json
{"action": "advance_phase"}
{"action": "continue_phase"}
{"action": "pause_timer"}
{"action": "disconnected"}     // synthetic, from receive_loop
```

### wait_for_command helper (in stress_brainstorm.py)

```python
async def wait_for_command(receive, timeout=60):
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
```

Timeout or disconnect → auto-advance. All phases auto-advance → auto-generate final verdict. User comes back to a completed session.

For Product/Conclusion modes: `SessionRunner.run()` accepts `receive=None` as default. The existing `run_brainstorm()` is never passed a receive callable. The bidirectional WS receive loop still runs (harmlessly draining any unexpected client messages) but the brainstorm loop never reads from it. Zero impact on existing modes.

---

## 9. Phase-Aware Selector

### Modified: `backend/engine/selector.py`

Add optional `stress_context` parameter to `hybrid_selector()`:

```python
async def hybrid_selector(
    support_agent, messages, last_spoke, turn_counter,
    agent_names, max_rounds, forced_next,
    stress_context=None    # new, optional
):
```

When `stress_context` is provided, append to selector prompt:

```
Current phase: {phase_name}
Phase focus: {focus_question}
Sub-phase: {sub_phase} — {sub_phase_directive}
Phase-relevant agents: {agents whose lens applies}

In Challenge sub-phase: prioritize adversarial agents.
In Comprehend sub-phase: rotate evenly — everyone must state their reading.
In Synthesize/Conclude: prioritize agents who haven't committed a position yet.
```

`stress_context` dict built by `StressOverseer.get_selector_context()` each round.

Existing modes pass `stress_context=None`, selector behaves exactly as before.

---

## 10. WebSocket Message Types (new)

```json
{"type": "phase_directive",        "phase_number": 2, "phase_name": "...", "focus_question": "...", "subquestions": [...], "sub_phase": "Comprehend"}
{"type": "overseer_phase_eval",    "action": "suggest_advance", "confirmed": [...], "contested": [...], "summary": "..."}
{"type": "phase_pause",            "phase_number": 2, "timeout_seconds": 60}
{"type": "phase_advanced",         "from_phase": 1, "to_phase": 2}
{"type": "phase_artifact_written", "phase_number": 1, "content": "..."}
{"type": "session_close_suggest",  "total_rounds": 127, "phases_complete": 5}
{"type": "verdict_generating"}
{"type": "verdict_complete",       "content": "..."}
{"type": "phase_continue",         "phase_number": 2, "reason": "user override"}
{"type": "drift_redirect",         "message": "...", "sub_phase": "Challenge"}
```

---

## 11. API Endpoints (new)

All stress-test endpoints in `backend/routers/stress_test.py`, prefix `/api/sessions/{id}/stress`:

```
POST /api/upload/stress-test                    — upload + extract text
POST /api/sessions/{id}/stress/analyse-documents — phase inference
POST /api/sessions/{id}/stress/reinterpret-phases — re-interpret after edits
POST /api/sessions/{id}/stress/confirm-phases   — lock phases
POST /api/sessions/{id}/stress/suggest-agents   — AI agent suggestion for stress test
GET  /api/sessions/{id}/stress/phases           — return phase definitions + status
GET  /api/sessions/{id}/stress/artifacts        — return all phase artifacts
```

---

## 12. Frontend Changes

### Setup page (Canvas.tsx) — Stress Test mode

**Sidebar additions (when mode = stress_test):**

1. Document upload area — drag-drop + file picker, uploaded files as removable cards
2. "Analyse Documents" button — after docs + problem statement
3. Min rounds per phase slider (10-40, default 20) with computed total + cost estimate

**Main area — phase cards (after analysis):**

- Vertical sequence of editable phase cards with connectors
- Each card: number, name (editable), document tags (draggable), focus question (editable), subquestions (editable list), rationale (read-only)
- "Re-interpret" button → sends edits, replaces cards
- "Confirm Phases" button → locks phases, switches main area to agent canvas

### Live session additions

1. **StatsBar** — phase indicator: "Phase 2 of 5 — Capability Map" + sub-phase: "Challenge"

2. **Phase pause card in LiveFeed** — full-width card with:
   - Overseer summary, confirmed/contested lists
   - "Advance to Phase N+1" / "Continue Phase N" buttons
   - 60s countdown timer with "Pause Timer" button
   - Buttons send WS commands

3. **Document sidebar** — collapsible left panel in live view. Documents grouped by phase. Current phase docs highlighted teal, previous dimmed, future greyed out.

4. **Artifact panel** — per-phase artifacts as collapsible sections when phases close

5. **Session close card** — same pattern: "Generate Final Verdict" / "Continue Reviewing" + 60s timer

### Results page additions

- Tab per phase artifact (Phase 1, Phase 2...) + Final Verdict tab (shown first, highlighted)
- Download individual artifact files + full ZIP

---

## 13. Output Files

```
stress_test_transcript_{timestamp}.md              — full session transcript
stress_test_phase_{N}_artifact_{timestamp}.md      — one file per phase
stress_test_verdict_{timestamp}.md                 — final readiness verdict
stress_test_summary_{timestamp}.zip                — all of the above
```

---

## 14. New Files Summary

| File | Purpose |
|---|---|
| `backend/engine/stress_brainstorm.py` | Phase-aware brainstorm loop |
| `backend/engine/stress_overseer.py` | StressOverseer class |
| `backend/services/stress_suggest.py` | Phase inference, re-interpret, agent suggestion |
| `backend/services/doc_extract.py` | Text extraction (PDF/DOCX/XLSX/CSV/TXT/MD) |
| `backend/routers/stress_test.py` | Stress test API endpoints |

## 15. Modified Files Summary

| File | Change |
|---|---|
| `backend/models/session.py` | Add stress_test to mode enum, add phases/uploaded_documents/current_phase_index columns |
| `backend/models/schemas.py` | Phase, UploadedDocument schemas, stress_test settings |
| `backend/routers/sessions.py` | Bidirectional WebSocket (command queue + receive loop) |
| `backend/services/session_runner.py` | Dispatch to run_stress_test() for stress_test mode, pass receive callable |
| `backend/engine/selector.py` | Optional stress_context parameter |
| `backend/main.py` | Mount stress_test router |
| `frontend/src/components/setup/ModeSelector.tsx` | Add Stress Test option |
| `frontend/src/pages/Canvas.tsx` | Document upload, phase cards, confirm flow, stress test setup |
| `frontend/src/components/session/LiveFeed.tsx` | Phase pause card, countdown, session close card |
| `frontend/src/components/session/StatsBar.tsx` | Phase + sub-phase indicator |
| `frontend/src/components/session/ArtifactPanel.tsx` | Per-phase collapsible artifacts |
| `frontend/src/pages/Results.tsx` | Per-phase tabs, verdict tab |
| `frontend/src/hooks/useWebSocket.ts` | Send commands (advance, continue, pause_timer) |
| `frontend/src/store/sessionStore.ts` | Phase, UploadedDocument types, stress_test settings |
| `requirements.txt` | pypdf, python-docx, openpyxl, pandas |

---

## 16. Build Order

1. Document upload endpoint + text extraction
2. Data model extensions (Phase, UploadedDocument, mode enum)
3. Phase inference + re-interpret endpoints
4. Agent suggestion for stress test
5. Frontend: mode selector + document upload + phase cards UI + confirm flow
6. Bidirectional WebSocket
7. StressOverseer class
8. Stress test brainstorm loop
9. Phase-aware selector
10. Phase pause/advance/continue mechanic (backend + frontend)
11. Per-phase artifact writing
12. Session close + final verdict generation
13. Frontend live session (StatsBar phase indicator, document sidebar, pause cards)
14. Results page (per-phase tabs, verdict tab, downloads)
15. End-to-end test
