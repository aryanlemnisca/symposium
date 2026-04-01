# Symposium — Full Product Specification
### Internal Brainstorming Canvas · Lemnisca · v1.0

---

## 1. PRODUCT OVERVIEW

**Symposium** is an internal web application for the Lemnisca team that lets users design structured multi-agent AI brainstorming sessions on a visual canvas. Users assemble a panel of AI agents, each with a distinct persona, define a problem or goal, configure session rules, and watch a structured debate unfold in real time. Sessions end with a structured output document — a PRD, a conclusion report, or a decision summary — that can be downloaded.

The product is purpose-built for Lemnisca's internal strategic and product work. It is not a consumer product and has no public access.

**Core value:** Replace unstructured AI prompting with disciplined multi-perspective debate that produces defensible, structured outputs.

---

## 2. FULL FEATURE LIST

### 2.1 Authentication
- Single shared password (e.g. `symposium2025`)
- No per-user accounts in v1
- Password stored as an environment variable on the server
- Session token stored in localStorage; auto-expires after 24 hours
- No registration flow — just a login screen with a password field

### 2.2 Canvas — Session Setup

**The canvas is the primary UI.** It is a free-form interactive workspace where the user builds a session before running it.

#### Problem Statement Panel (left sidebar or top panel)
- Large text area: **Problem Statement**
  - Placeholder: *"Describe the problem, goal, or question this session should address..."*
  - Character guidance: 100–1000 characters recommended
  - Must-contain checklist shown below the field (see Section 5)
  - AI inline suggestions as user types (debounced 800ms after keystroke stops)
  - AI suggestion appears as greyed ghost text or a floating suggestion chip
  - **"Review my Problem Statement"** button triggers a full AI review with structured feedback
- **Mode selector** (pill toggle):
  - `Product Discussion` → output is a PRD
  - `Problem Discussion` → output is a Conclusion Report
- **Rounds slider**: 20 / 50 / 80 / 100 (with cost estimate shown: ~$0.51 / ~$1.27 / ~$2.40 / ~$3.80)
- **Advanced Settings** (collapsed by default, expandable):
  - Gate start round (default: 10)
  - Overseer interval (default: 10)
  - Temperature (default: 0.70, range 0.3–1.0)
  - Min rounds before consensus termination (auto-set to MAX_ROUNDS - 5, user can override)

#### Canvas Area (main area)
- Clean infinite canvas with a subtle grid
- User drags Agent Cards from the right sidebar onto the canvas
- Each Agent Card is a circle node when dropped
- Nodes can be freely repositioned by dragging
- Connecting lines are drawn automatically between all nodes (indicating they are in the same session) — decorative only, not functional routing
- Active speaker node pulses/glows during live session
- Canvas state (node positions) is saved with the session

#### Agent Node
Each node on the canvas represents one agent. Clicking a node opens an **Agent Configuration Panel** (slide-in drawer):

- **Agent Name** — text field
- **Model** — dropdown (Gemini models only):
  - `gemini-3.1-pro-preview` (default, main brainstorm quality)
  - `gemini-2.5-flash` (faster, cheaper — suitable for support roles)
- **Persona Definition** — large text area
  - Must-contain checklist shown below (see Section 5)
  - AI inline suggestions as user types
  - **"Review my Persona"** button for full AI review
- **Tools** (toggle switches per agent):
  - Web Search (on/off)
  - *(code execution: not in v1)*
- **Role tag** (optional label shown on the node): e.g. *Challenger*, *Domain Expert*, *Outsider*

#### Right Sidebar — Agent Library
- **Blank Agent** card (always at top) — drag to canvas, configure from scratch
- **Library** section — pre-built agent cards grouped by category:
  - **Lemnisca Default** (6 agents): Fermentation_Veteran, Ops_Leader, MSAT_Lead, Product_Thinker, First_Principles_Outsider, BioChem_Professor — each pre-loaded with full verbatim personas
  - **General** (future): Devil's Advocate, Domain Expert, Market Analyst, etc.
- **AI Suggest Agents** button — based on the current problem statement, AI recommends 3–5 agent archetypes with suggested personas. User can drag any suggested agent directly onto the canvas.
- Search/filter bar for the library

#### Document Upload (v1)
- **"+ Attach Context Document"** button in the Problem Statement panel
- Accepts PDF, DOCX, TXT, MD (max 10MB per file, max 3 files)
- Uploaded documents are injected into the problem statement context that all agents receive at session start
- Files shown as small chips below the problem statement; removable
- Files are stored temporarily for the session duration only — not persisted beyond the session

#### Session Templates
- **"Save as Template"** button in the canvas toolbar
- Saves: agent configurations (name, model, persona, tools, node positions), problem statement template (optional), mode, rounds, advanced settings
- Saved templates appear in a **Templates** tab in the right sidebar
- **Lemnisca Default** template is pre-loaded and cannot be deleted (read-only)
- User-saved templates can be renamed and deleted
- After a session completes, a modal appears: **"Save this canvas configuration as a template?"** (Yes / Not now)

### 2.3 Session Execution — Live View

When the user clicks **"Begin Symposium"**:

1. Canvas transitions to **Live Mode** — setup controls are locked
2. Layout switches to a **split view**:
   - **Left panel (40%)**: Canvas remains visible — agent nodes shown, active speaker pulses
   - **Right panel (60%)**: Live chat feed — messages stream in one at a time

#### Live Chat Feed
- Each message appears with:
  - Agent name + role tag
  - Round number (e.g. `Round 7 / 50`)
  - Full message content (streaming, token by token)
  - Timestamp
- **Overseer messages** appear as distinct system messages — different background colour (e.g. dark grey band), labelled `[OVERSEER — Round 10]`
- **Gate skip notifications** appear as small inline chips: `BioChem_Professor skipped — no new contribution`
- **Convergence events** appear as system notifications: `[Convergence detected → forcing First_Principles_Outsider]`
- Auto-scroll to bottom; user can scroll up to read history without disrupting auto-scroll (detects manual scroll, pauses auto-scroll, resumes when user scrolls back to bottom)

#### Living Artifact Panel
- Sits below the canvas in live mode (or accessible as a collapsible panel)
- Shows the artifact being built in real time as Overseer writes each section
- Sections appear progressively at milestone rounds (20, 40, 55, 65, 75)
- Each section fades in when written
- Labelled clearly: `Section 1 — C-Level Verdicts (written at round 20)`

#### Session Stats Bar (top of live view)
- Rounds completed / total
- Gate skips (count + %)
- Overseer injections
- C-levels covered (C1 ✓ C2 ✓ C3 ✗ C4 ✓ C5 ✗) — shown as coloured dots
- Live cost estimate (running total based on token counts)

#### Post-Brainstorm
After MAX_ROUNDS or consensus termination:
- Session enters **PRD / Conclusion Phase** automatically
- A banner appears: `"Brainstorm complete. Running PRD panel (10 rounds)..."` or `"Brainstorm complete. Generating Conclusion Report..."`
- PRD mini-panel runs automatically (Product mode) or synthesis runs (Problem Discussion mode)
- Both phases visible in the chat feed, clearly separated by a section divider
- When fully complete, a **"Session Complete"** banner appears with export options

### 2.4 Session Output

#### Product Mode output:
- `lemnisca_transcript.md` — full brainstorm
- `lemnisca_artifact.md` — Living Artifact
- `lemnisca_synthesis.md` — synthesis report
- `lemnisca_prd.md` — build-ready PRD

#### Problem Discussion mode output:
- `lemnisca_transcript.md` — full brainstorm
- `lemnisca_artifact.md` — Living Artifact
- `lemnisca_conclusion.md` — structured conclusion report

All files are generated at session end and available for download as:
- Individual `.md` files
- Single `.zip` archive containing all files

#### Output rendered in dashboard
- After session completion, user lands on a **Session Results** page
- Each output document is rendered as formatted Markdown in a tabbed view
- Tabs: `Transcript` | `Artifact` | `PRD` (or `Conclusion`) | `Synthesis`
- Download buttons available on each tab and as a bulk zip

### 2.5 Session History

- **Sessions page** lists all past sessions
- Each session shows: name (auto-generated from problem statement first 60 chars), mode, date, rounds completed, status (complete / interrupted)
- Sessions are **resumable** — clicking "Resume" reloads the canvas state and allows re-running from scratch (does not continue mid-session; resuming means re-running with same configuration)
- Sessions can be renamed, duplicated, or deleted
- Session data stored in SQLite (local) or PostgreSQL (hosted)

### 2.6 AI Suggestions System

Two modes:

**1. Inline suggestions** (triggered automatically)
- Problem Statement field: after 800ms of inactivity, sends current text to Gemini Flash with a suggestion prompt
- Returns a single improvement suggestion shown as a floating chip below the field
- Examples: *"Consider specifying the target user more precisely"*, *"Add a constraint — what is out of scope?"*
- User can accept (inserts text) or dismiss

**2. On-demand review** (triggered by button)
- **"Review my Problem Statement"** — sends full text to Gemini and returns structured feedback:
  - Missing must-contain elements (see Section 5)
  - Clarity score (Low / Medium / High) with one-line rationale
  - 2–3 specific improvement suggestions
  - Example rewrite (collapsible)
- **"Review my Persona"** — same pattern for agent personas:
  - Missing sections checklist
  - Distinctiveness check (is this persona too similar to another agent on the canvas?)
  - One-line summary of what this agent adds to the panel

**3. "Suggest Agents" button**
- Sends problem statement to Gemini Flash
- Returns 3–5 agent archetypes with:
  - Suggested name
  - One-line mission
  - Draft persona (user can edit before dragging to canvas)
  - Recommended model

---

## 3. USER FLOWS

### Flow A — New Session from Scratch
1. Login with password → land on Sessions page
2. Click **"+ New Session"**
3. Canvas opens (blank)
4. Type problem statement → inline AI suggestions appear
5. Select mode (Product / Problem Discussion)
6. Set rounds (default: 50)
7. Drag agents from library (or blank) onto canvas → configure each
8. Optionally attach context documents
9. Click **"Review Setup"** for full AI review → address flagged issues
10. Click **"Begin Symposium"**
11. Watch live feed + canvas + artifact building
12. Session completes → results page loads
13. Modal: *"Save this canvas as a template?"*
14. Browse output tabs → download files

### Flow B — From Template
1. Login → Sessions page
2. Click **"+ New Session"** → select **"Start from Template"**
3. Template library shows → select **"Lemnisca Default"** (or saved template)
4. Canvas pre-populates with saved agents
5. Edit problem statement and any agent configs
6. Proceed from step 9 above

### Flow C — Resume Session
1. Sessions page → click a past session
2. Session Results page loads with previous output
3. Click **"Re-run"** — canvas reloads with same configuration
4. User can modify before running again

---

## 4. TECHNICAL ARCHITECTURE

### Stack
- **Frontend**: React (Vite) + TypeScript
- **Canvas**: React Flow (node/edge drag-and-drop canvas library)
- **Backend**: FastAPI (Python) — keeps AutoGen + Gemini integration native
- **Database**: SQLite (local v1) → PostgreSQL (hosted v2)
- **Streaming**: WebSockets (FastAPI WebSocket endpoint → React client)
- **Auth**: Simple middleware checking password hash against env var
- **File storage**: Local filesystem (v1) → S3-compatible (v2)

### Key backend services
```
/api/sessions         GET (list), POST (create)
/api/sessions/{id}    GET (detail), PATCH (rename), DELETE
/api/sessions/{id}/run   POST → starts session, returns WebSocket URL
/api/sessions/{id}/export  GET → returns zip of output files
/api/templates        GET (list), POST (save), DELETE
/api/suggest/agents   POST (problem statement → agent suggestions)
/api/suggest/review   POST (text + type → structured review)
/api/upload           POST (document upload → returns doc_id)
```

### WebSocket message types (server → client)
```json
{ "type": "agent_message",    "source": "BioChem_Professor", "content": "...", "round": 7, "streaming": true }
{ "type": "agent_message_end","source": "BioChem_Professor", "round": 7 }
{ "type": "overseer",         "content": "...", "round": 10 }
{ "type": "gate_skip",        "agent": "Ops_Leader", "round": 12 }
{ "type": "artifact_section", "section_num": 1, "section_name": "C-Level Verdicts", "content": "..." }
{ "type": "convergence",      "forced_next": "First_Principles_Outsider" }
{ "type": "stats",            "rounds": 7, "gate_skips": 1, "c_coverage": {"C1": true, ...} }
{ "type": "phase_transition", "phase": "prd_panel" }
{ "type": "session_complete", "terminated_by": "consensus" }
{ "type": "error",            "message": "..." }
```

### Session data model
```python
Session:
  id: str (UUID)
  name: str
  mode: enum (product | problem_discussion)
  problem_statement: str
  document_ids: list[str]
  agents: list[AgentConfig]
  settings: SessionSettings
  status: enum (draft | running | complete | error)
  created_at: datetime
  completed_at: datetime | None
  transcript: str | None
  artifact: dict | None
  outputs: dict[str, str] | None  # filename → content
  canvas_state: dict  # node positions

AgentConfig:
  id: str
  name: str
  model: str
  persona: str
  tools: list[str]
  role_tag: str | None
  canvas_position: {x: float, y: float}

SessionSettings:
  max_rounds: int
  temperature: float
  gate_start_round: int
  overseer_interval: int
  min_rounds_before_convergence: int
  prd_panel_rounds: int
```

### Backend session runner
- Inherits all logic from current `lemnisca_panel_v7.py`
- Modularised into the `lemnisca/` package (config, personas, gate, selector, overseer, artifact, summary, brainstorm, prd, outputs, agents, utils)
- Session runner wraps the existing `run_brainstorm()` and `run_prd_mini_panel()` functions
- All `print()` calls replaced by WebSocket `send()` calls
- Agent personas and problem statement come from the session config, not hardcoded constants

---

## 5. MUST-CONTAIN GUIDELINES

These are enforced by the AI review system and shown as checklists in the UI. Not blocking — user can ignore and proceed — but the review system will flag missing items.

### Problem Statement must-contain checklist
- [ ] **Target user** — who specifically is experiencing this problem?
- [ ] **Context** — what situation are they in when this pain occurs?
- [ ] **Core constraint** — what is non-negotiable? (e.g. "must be free", "no IT integration")
- [ ] **Out of scope** — what are you explicitly not solving?
- [ ] **Success definition** — what does a good output from this session look like?
- [ ] **Domain anchoring** — enough specific context for agents to reason concretely (not generic)

### Agent Persona must-contain checklist
Each persona should include at least:
- [ ] **One-line mission** — what this agent is here to do
- [ ] **Background / worldview** — where they come from, what shapes their thinking
- [ ] **What they care about most** — 3–5 bullet points
- [ ] **What they distrust or reject** — specific, not generic
- [ ] **Default questions they ask** — at least 3 concrete questions
- [ ] **Biases / blind spots** — honest acknowledgment
- [ ] **What a good idea looks like to them**
- [ ] **What a bad idea looks like to them**
- [ ] **How they interact with others** — confrontational? methodical? provocative?
- [ ] **Style** — tone, register, speech patterns

### Agent Panel health checks (shown before "Begin Symposium")
- Minimum 2 agents required (soft warning below 3)
- No two agents with identical or near-identical personas (similarity check via embedding)
- At least one agent with a "challenger" orientation (agent who is likely to disagree)
- Problem statement reviewed (warning if not reviewed)

---

## 6. UI DESIGN PRINCIPLES

- **Dark theme** — consistent with Lemnisca's existing deck design (dark navy base)
- **Accent colour** — teal (matching FermentIQ brand)
- **Canvas**: dark background, subtle dot grid, nodes as glowing circles with agent name label
- **Active speaker node**: pulsing outer ring animation during message generation
- **Typography**: clean sans-serif, high contrast
- **Information density**: the live view should feel like a control room, not a chat app — data-rich but not cluttered
- **Streaming text**: monospace or semi-monospace for agent messages to evoke terminal/technical feel
- **Overseer messages**: distinct visual treatment — darker background band, `[SYS]` tag prefix, muted colour

---

## 7. AI SUGGESTION PROMPTS (reference for implementation)

### Problem Statement inline suggestion
```
System: You are a brainstorming session design assistant. Be concise and specific.
User: The user is writing a problem statement for a multi-agent AI brainstorming session.
Current text: "{current_text}"
Identify the single most important missing element or improvement.
Return ONE short suggestion (max 15 words). If the text is already strong, return "NONE".
```

### Problem Statement full review
```
System: You are a brainstorming session design expert.
User: Review this problem statement for a multi-agent AI discussion session:

"{problem_statement}"

Return JSON:
{
  "clarity": "Low|Medium|High",
  "clarity_reason": "one sentence",
  "missing": ["list of missing must-contain elements"],
  "suggestions": ["2-3 specific improvement suggestions"],
  "rewrite": "improved version of the problem statement"
}
```

### Persona full review
```
System: You are an expert in designing AI agent personas for structured debate.
User: Review this agent persona:

Name: {agent_name}
Persona: {persona_text}

Other agents on this panel:
{other_agents_summary}

Return JSON:
{
  "missing_sections": ["list of missing must-contain sections"],
  "distinctiveness": "High|Medium|Low",
  "distinctiveness_reason": "one sentence",
  "suggestions": ["2-3 specific improvement suggestions"]
}
```

### Agent suggestions from problem statement
```
System: You are an expert in designing multi-agent brainstorming panels.
User: Based on this problem statement, suggest 4 agent archetypes that would create productive tension and cover the most important perspectives.

Problem: "{problem_statement}"
Mode: {mode}

Return JSON array of 4 agents:
[{
  "name": "short descriptive name",
  "mission": "one sentence mission",
  "persona": "full persona text following the standard structure",
  "model": "gemini-3.1-pro-preview|gemini-2.5-flash",
  "rationale": "one sentence — why this agent adds value to this panel"
}]
```

---

## 8. OUTPUT FORMATS

### Product Discussion → PRD
Follows the existing `lemnisca_prd_*.md` template:
1. Product Name and One-Line Description
2. Target User
3. Trigger Moment
4. Required Inputs
5. Processing Logic
6. Output
7. Trust Mechanism
8. v1 Scope
9. Wedge Mechanic
10. Team Ownership
11. Unresolved Questions Before Build Starts

### Problem Discussion → Conclusion Report
New template:
1. Problem Restated (one paragraph)
2. Key Agreements (what the panel definitively concluded)
3. Key Tensions (where disagreement remained and why it matters)
4. Recommended Direction (the panel's strongest supported conclusion)
5. Dissenting Views (minority positions worth preserving)
6. Open Questions (specific questions that would change the direction if answered)
7. Next Steps (concrete actions)

---

## 9. V1 SCOPE — EXPLICIT BOUNDARIES

### In v1
- Canvas with drag-and-drop agent nodes (React Flow)
- Agent library with Lemnisca Default 6-persona template
- Blank agent + library + AI-suggested agents
- Problem Statement with inline AI suggestions and full review
- Persona definition with inline AI suggestions and full review
- Document upload (PDF, DOCX, TXT, MD — max 3 files, 10MB each)
- Two session modes: Product Discussion, Problem Discussion
- Rounds: 20 / 50 / 80 / 100
- Advanced settings panel
- WebSocket streaming live feed
- Overseer messages visible in feed
- Living Artifact building in real-time
- Session stats bar
- Auto PRD panel after brainstorm
- Session save + resume
- Template save/load
- Download outputs (individual MD files + ZIP)
- Local deployment (localhost)
- Single shared password auth
- SQLite database
- Gemini models only (Pro + Flash)
- Web search tool per agent (toggle)
- Session history page

### Not in v1 (explicitly deferred)
- Red Team mode
- Hosted deployment (v2)
- Per-user accounts (v2)
- Google Docs export (v2)
- Mid-session user intervention (v2)
- Code execution tool (v2)
- Custom MCP tools (v2)
- Public template library (v2)
- Non-Gemini models (v2)
- Mobile-responsive layout (v2)
- Real-time collaborative editing (v2)
- Webhooks / API access (v2)

---

## 10. FILE STRUCTURE (target)

```
symposium/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── routers/
│   │   ├── sessions.py
│   │   ├── templates.py
│   │   ├── suggest.py
│   │   └── upload.py
│   ├── services/
│   │   ├── session_runner.py      # wraps lemnisca package, emits WS events
│   │   ├── ai_suggest.py          # problem statement + persona review
│   │   └── export.py              # output file generation
│   ├── models/
│   │   ├── session.py
│   │   ├── template.py
│   │   └── agent.py
│   ├── database.py
│   ├── auth.py
│   └── lemnisca/                  # modularised session engine
│       ├── __init__.py
│       ├── config.py
│       ├── personas.py
│       ├── utils.py
│       ├── gate.py
│       ├── selector.py
│       ├── overseer.py
│       ├── artifact.py
│       ├── summary.py
│       ├── agents.py
│       ├── brainstorm.py
│       ├── prd.py
│       └── outputs.py
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Sessions.tsx
│   │   │   ├── Canvas.tsx         # setup + live view
│   │   │   └── Results.tsx
│   │   ├── components/
│   │   │   ├── canvas/
│   │   │   │   ├── AgentNode.tsx
│   │   │   │   ├── AgentDrawer.tsx
│   │   │   │   └── AgentLibrary.tsx
│   │   │   ├── session/
│   │   │   │   ├── LiveFeed.tsx
│   │   │   │   ├── ArtifactPanel.tsx
│   │   │   │   └── StatsBar.tsx
│   │   │   ├── setup/
│   │   │   │   ├── ProblemStatement.tsx
│   │   │   │   ├── ModeSelector.tsx
│   │   │   │   └── AdvancedSettings.tsx
│   │   │   └── shared/
│   │   │       ├── MarkdownRenderer.tsx
│   │   │       └── ReviewPanel.tsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useSession.ts
│   │   │   └── useAISuggest.ts
│   │   ├── store/                 # Zustand state
│   │   │   ├── sessionStore.ts
│   │   │   └── canvasStore.ts
│   │   └── api/
│   │       └── client.ts
│   └── package.json
├── .env.example
├── requirements.txt
└── README.md
```

---

## 11. ENVIRONMENT VARIABLES

```bash
# Required
SYMPOSIUM_PASSWORD=symposium2025       # single shared password
GEMINI_API_KEY=your_key_here           # Gemini API key (user pastes on first use OR set here)

# Optional (local defaults shown)
DATABASE_URL=sqlite:///./symposium.db
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
MAX_UPLOAD_SIZE_MB=10
```

**API key handling:** User can either set `GEMINI_API_KEY` in `.env` (team default) or paste their own key in a settings panel in the UI. If pasted in UI, it is stored in the browser's localStorage only — never sent to the backend except as part of session config. Backend uses it for that session only.

---

## 12. FIRST BUILD PRIORITY ORDER

For Claude Code — build in this order:

1. **Backend foundation**: FastAPI app, database models, auth middleware, basic CRUD for sessions
2. **Lemnisca engine modularisation**: Split `lemnisca_panel_v7.py` into the `lemnisca/` package with WebSocket emit replacing print statements
3. **WebSocket session runner**: Connect engine to WS endpoint, verify streaming works end-to-end
4. **Frontend skeleton**: React + Vite setup, routing, login page, sessions list page
5. **Canvas**: React Flow canvas, agent nodes, agent library sidebar, agent drawer
6. **Problem statement + setup UI**: Problem statement panel, mode selector, rounds slider, document upload
7. **AI suggestions**: Inline suggestions + review buttons (both problem statement and persona)
8. **Live session view**: Split canvas/feed layout, streaming messages, overseer messages, stats bar, artifact panel
9. **Results page**: Tabbed output viewer, download buttons
10. **Session history + templates**: Save/resume sessions, save/load templates, post-session modal
11. **Polish**: Dark theme, animations (active speaker pulse), responsive layout fixes

---

*Document version: 1.0 — April 2026*
*Prepared for handoff to Claude Code*