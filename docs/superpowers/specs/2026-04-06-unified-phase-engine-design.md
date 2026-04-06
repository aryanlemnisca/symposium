# Unified Phase-Based Engine — Design Spec

## Problem

Product and Problem Discussion modes run as flat 50-round loops with no structure, no drift detection, no phase progression, and weak context management. Stress test mode has all of these. The three modes share almost no orchestration code despite having the same core loop pattern.

## Solution

Extract shared phase-loop logic into reusable components. Each mode keeps its own engine file but imports from shared modules. This gives each mode the same quality of orchestration while keeping codebases independent for future changes.

## Architecture

```
backend/engine/
  # Shared components (new)
  phase_loop.py          — core per-phase loop (sub-phases, agent calls, streaming)
  phase_overseer.py      — drift checks, evaluation, phase advancement decisions
  phase_artifacts.py     — per-phase structured artifact generation

  # Mode-specific engines (separate files)
  product_brainstorm.py  — Product mode orchestration
  problem_brainstorm.py  — Problem mode orchestration
  stress_brainstorm.py   — Stress test orchestration (refactored)

  # Mode-specific outputs (separate files)
  synthesis.py           — PRD generation (product only)
  conclusion.py          — Conclusion report (problem only)
  verdict.py             — Verdict + readiness (stress test only, extracted from stress_overseer)
  executive_summary.py   — Executive summary (all modes, extracted from stress_brainstorm)

  # Shared utilities (existing, enhanced)
  gate.py                — speech gate (unchanged)
  selector.py            — hybrid selector (enhanced with sub-phase awareness)
  clients.py             — model client factory (unchanged)
  tools.py               — web search tool (unchanged)
  config.py              — engine config (extended with phases)

  # New
  phase_suggest.py       — AI phase generation for product/problem modes

  # Removed
  brainstorm.py          — replaced by product_brainstorm.py + problem_brainstorm.py
  overseer.py            — replaced by phase_overseer.py
  convergence.py         — replaced by overseer evaluation logic
  artifact.py            — replaced by phase_artifacts.py
  summary.py             — rolling summary moved into phase_loop.py
```

## Flow (all modes)

```
Problem Statement (+ docs for stress test)
  → AI generates phases (focus questions, subquestions, artifact schema)
  → User confirms/edits phases
  → AI suggests agents
  → User configures rounds/settings
  → Begin Symposium
    → Per-phase loop (overseer-driven advancement)
  → Mode-specific final output
```

## Default Phase Templates

### Product Mode (6 phases)

| # | Phase | Purpose |
|---|-------|---------|
| 1 | Problem & User Understanding | Define the pain, who has it, why it matters |
| 2 | Research & Landscape | Web search for market data, competitors, benchmarks |
| 3 | Solution Ideation | Propose solutions informed by research |
| 4 | Feasibility & Critique | Poke holes, technical/business viability (**critical**) |
| 5 | Convergence & Prioritization | Narrow down, pick direction |
| 6 | Product Detailing & Architecture | Specifics, UX, technical decisions |

### Problem Mode (5 phases)

| # | Phase | Purpose |
|---|-------|---------|
| 1 | Problem Decomposition | Break down the problem, identify dimensions |
| 2 | Research & Context | Web search for prior work, data, case studies |
| 3 | Perspective Exploration | Different viewpoints, frameworks, approaches |
| 4 | Tension Resolution | Resolve disagreements, find common ground (**critical**) |
| 5 | Synthesis & Recommendations | Final positions, actionable recommendations |

### Stress Test Mode

Phases auto-generated from uploaded documents (existing behavior). AI marks critical phases based on document importance.

All templates are defaults — user can delete, reorder, add, or edit phases before confirming.

## Shared Components

### phase_loop.py — Core Per-Phase Loop

The main loop that all three engines call. Handles:
- Agent selection via hybrid selector
- Speech gate filtering
- Streaming agent responses
- Emitting events (agent_message, agent_message_chunk, stats)
- Delegating to phase_overseer for drift/evaluation

Each mode engine calls `run_phase()` per phase, passing mode-specific context builder.

```python
async def run_phase(
    agents: dict,
    support_agent: AssistantAgent,
    phase: dict,
    context_builder: Callable,  # mode-specific
    config: EngineConfig,
    emit: EventCallback,
    state: PhaseLoopState,      # tracks rounds, last_spoke, persona_turns
) -> PhaseResult:
    """Run a single phase. Returns messages, artifact, stats."""
```

### phase_overseer.py — Oversight & Advancement

Generalized from stress_overseer.py. Handles:
- Sub-phase progression (Comprehend → Challenge → Cross-examine → Synthesize → Conclude)
- Keyword drift check (every round, zero cost)
- LLM drift check (every 3 rounds)
- Full evaluation (every 5 rounds) — checks if all subquestions are addressed
- Phase advancement decision — no user intervention, overseer decides
- Phase directive generation at phase start
- Carry-forward of confirmed/contested items across phases

### phase_artifacts.py — Structured Artifact Generation

Generates per-phase artifacts when a phase ends:

```markdown
## Phase N: {name}

### Confirmed
- [item] — [evidence] — [accept]

### Contested
- [claim] — [objection] — [who raised it] — [status]

### Must Address
- [blocking issues]

### Open Questions
- [specific questions] — [why they matter]
```

Decision tags: `[accept]`, `[revise]`, `[reopen]`, `[defer]`

## Mode-Specific Engines

### product_brainstorm.py

```python
async def run_product_session(config, phases, emit) -> outputs:
    # 1. Build agents
    # 2. For each phase: call phase_loop.run_phase() with product context builder
    # 3. Run PRD panel (reads all phase artifacts, not just living artifact)
    # 4. Generate synthesis + PRD
    # 5. Generate executive summary
    # Returns: phase_artifacts + prd + synthesis + executive_summary + transcript
```

Context builder: problem statement + previous phase artifacts.

### problem_brainstorm.py

```python
async def run_problem_session(config, phases, emit) -> outputs:
    # 1. Build agents
    # 2. For each phase: call phase_loop.run_phase() with problem context builder
    # 3. Generate conclusion report (from all phase artifacts)
    # 4. Generate executive summary
    # Returns: phase_artifacts + conclusion + executive_summary + transcript
```

Context builder: problem statement + previous phase artifacts.

### stress_brainstorm.py (refactored)

```python
async def run_stress_test(config, phases, documents, review_instructions, emit) -> outputs:
    # 1. Build agents
    # 2. For each phase: call phase_loop.run_phase() with stress context builder
    # 3. Generate verdict
    # 4. Generate executive summary
    # Returns: phase_artifacts + verdict + executive_summary + transcript
```

Context builder: problem statement + full document text + review instructions + previous phase artifacts.

## Sub-Phases (all modes)

Each phase progresses through 5 sub-phases based on round progress:

| Sub-Phase | % of Phase | Purpose |
|-----------|-----------|---------|
| Comprehend | 0-20% | Understand the topic, state initial positions |
| Challenge | 20-45% | Poke holes, question assumptions |
| Cross-examine | 45-65% | Defend or concede points with evidence |
| Synthesize | 65-85% | Build confirmed/contested/open list |
| Conclude | 85-100% | Final positions, no new challenges |

## Critical Phase Enforcement

Only phases marked `critical: true` enforce minimum rounds before the overseer can evaluate for advancement. Non-critical phases can end early if all subquestions are addressed.

## Agent Selection Enhancement

Hybrid selector gets sub-phase awareness for all modes (currently only stress test):

- **Comprehend**: Pure rotation — everyone states their view
- **Challenge**: Prefer challengers, outsiders
- **Cross-examine**: Prioritize agents whose claims were challenged
- **Synthesize**: Prefer agents who can commit to positions
- **Conclude**: Rotation for final statements

## Context Management (all modes)

- **Current phase**: Full conversation history for this phase only
- **Previous phases**: Only their final artifacts carry forward
- **Documents** (stress test only): Full text always available

Replaces the old approach of accumulating all messages across the entire session.

## Phase Suggestion Endpoint

New endpoint for Product/Problem modes:

```
POST /api/suggest/phases
{
  "problem_statement": "...",
  "mode": "product" | "problem"
}
→ {
  "phases": [
    {
      "number": 1,
      "name": "Problem & User Understanding",
      "focus_question": "What is the core problem and who experiences it?",
      "key_subquestions": ["Who is the primary user?", "What workaround exists today?"],
      "artifact_schema": ["Confirmed", "Contested", "Must Address", "Open Questions"],
      "critical": false
    }
  ]
}
```

Uses the default templates as a base but customizes focus questions and subquestions based on the problem statement.

Stress test keeps its existing phase generation from uploaded documents.

## Final Outputs

### Product Mode
- Per-phase artifacts (6)
- PRD synthesis (reads all phase artifacts + PRD panel discussion)
- Executive summary
- Transcript

### Problem Mode
- Per-phase artifacts (5)
- Conclusion report (reads all phase artifacts)
- Executive summary
- Transcript

### Stress Test Mode
- Per-phase artifacts (N)
- Verdict (blocking/non-blocking/confirmed/contradictions)
- Executive summary
- Transcript

## Bug Fixes Included

### 1. Min rounds enforcement
Only run phase evaluation after minimum rounds for critical phases. Non-critical phases can advance early.

### 2. Overseer injection counter
Track `total_overseer_injections` in all modes. Include in stats dict and transcript header.

## Config Extensions

`EngineConfig` gets:
- `phases: list[dict]` — phase definitions with focus questions, subquestions, critical flag
- `documents: list[dict]` — uploaded documents (stress test)
- `review_instructions: str` — review context (stress test)

## Execution Plan

### Step 1: Shared Components
Create `phase_loop.py`, `phase_overseer.py`, `phase_artifacts.py`. Extract and generalize logic from `stress_brainstorm.py` and `stress_overseer.py`.

### Step 2: Phase Suggestion
Create `phase_suggest.py` + API endpoint. Add phase suggestion UI to Product/Problem setup flow (similar to existing stress test flow).

### Step 3: Refactor Stress Test
Refactor `stress_brainstorm.py` to use shared components. Verify existing behavior preserved. Fix min rounds bug and overseer counter bug.

### Step 4: Product Engine
Create `product_brainstorm.py` using shared components. Adapt `synthesis.py` and `prd_panel.py` to read phase artifacts. Add executive summary.

### Step 5: Problem Engine
Create `problem_brainstorm.py` using shared components. Adapt `conclusion.py` to read phase artifacts. Add executive summary.

### Step 6: Extract Executive Summary
Move `_generate_executive_summary` into `executive_summary.py`. All modes import from there.

### Step 7: Update Session Runner
Update `session_runner.py` to call the correct mode engine and pass phase config.

### Step 8: Frontend — Phase Setup for Product/Problem
Add phase confirmation UI to Product/Problem setup (reuse existing stress test PhaseCards component). Add phase suggestion API call after problem statement is entered.

### Step 9: Frontend — Phase Artifacts Display
Update Results page to display per-phase artifacts for all modes (reuse existing stress test artifact tabs).

### Step 10: Cleanup
Remove old `brainstorm.py`, `overseer.py`, `convergence.py`, `artifact.py`. Update imports.
