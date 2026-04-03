# Symposium — Stress Test Mode
### Addition to existing Symposium implementation
### Hand this to Claude Code after PRD and Conclusion modes are working

---

## CONTEXT

Symposium already has two working modes: Product Discussion (→ PRD) and Conclusion (→ Conclusion Report). This document specifies a third mode: **Stress Test**. It shares all existing infrastructure — canvas, agents, gate, selector, memory doc, Overseer, WebSocket streaming — but adds document upload, phase management, and a new Overseer-controlled session flow.

Do not rebuild anything that already works. Add Stress Test as an additive layer.

---

## 1. WHAT STRESS TEST MODE DOES

The user uploads documents (a roadmap, a strategy pack, a research report, any set of related documents). Agents read the full document set and stress-test it phase by phase — challenging logic, finding weaknesses, confirming what is sound, and producing a structured review artifact per phase. The session ends with a final readiness verdict.

This mode is designed for: roadmap reviews, strategy stress-tests, research pack challenges, pre-meeting document validation.

It is explicitly NOT a brainstorm. Agents do not generate new ideas. They review, challenge, and confirm existing ones.

---

## 2. HOW IT DIFFERS FROM PRODUCT AND CONCLUSION MODES

| | Product / Conclusion | Stress Test |
|---|---|---|
| Documents | Optional context | Required — the thing being reviewed |
| Problem statement | Defines what to debate | Defines what to stress-test and why |
| Phases | Single continuous session | Multiple phases, each focused on specific docs |
| Overseer role | Constraint reminders + artifact | Phase manager + phase artifacts + final verdict |
| Session end | Max rounds or consensus | Min (phases × min_per_phase) rounds, then Overseer-controlled close |
| Agent panel | User builds from library | Overseer suggests based on docs, user accepts/edits |
| Output | PRD or Conclusion report | Per-phase artifacts + final readiness verdict |

Everything else is identical: gate, selector, memory doc, canvas, streaming, save/resume.

---

## 3. PRE-SESSION FLOW (new — Stress Test only)

This happens before the session starts, on the canvas setup page.

### Step 1 — Document Upload
- User uploads documents: PDF, DOCX, TXT, MD, XLSX, CSV
- No file limit specified — accept as many as the user uploads
- Max 20MB per file
- Files displayed as cards below the problem statement
- All files are extracted to plain text for agent context

### Step 2 — Problem Statement
- Same field as other modes
- In Stress Test the framing is: "What are you stress-testing and what must the review answer?"
- AI inline suggestions and review button work the same way
- Must-contain for Stress Test problem statement:
  - What the documents represent (what work product is being reviewed)
  - What decision the review is meant to support
  - What a good review outcome looks like
  - What is out of scope for the review

### Step 3 — Phase Definition Loop (new)

After documents are uploaded and problem statement is written, user clicks **"Analyse Documents."**

The system sends all document text + problem statement to Gemini Flash and returns a proposed phase breakdown. This is shown to the user as editable phase cards on the canvas before the session starts.

**Phase inference prompt:**
```
You are analysing a set of documents that a user wants to stress-test using a multi-agent review board.

Problem statement:
{problem_statement}

Documents uploaded:
{document_list_with_summaries}

Propose a logical phase breakdown for the review. Each phase should:
- Focus on a coherent subset of the documents
- Have a clear question to answer
- Be sequenced so earlier phases inform later ones
- Take approximately 20-30 rounds of agent debate to exhaust

Return JSON:
{
  "phases": [
    {
      "number": 1,
      "name": "short phase name",
      "documents": ["doc1.pdf", "doc2.docx"],
      "focus_question": "the primary question this phase must answer",
      "key_subquestions": ["subquestion 1", "subquestion 2", "subquestion 3"],
      "rationale": "why these documents and this question go together"
    }
  ],
  "total_phases": N,
  "suggested_min_rounds_per_phase": N,
  "suggested_total_min_rounds": N
}
```

**The loop:**
1. Overseer proposes phases → shown as editable cards to user
2. User can: rename a phase, change its focus question, move a document to a different phase, merge two phases, split a phase, add a phase, delete a phase
3. User clicks **"Re-interpret"** → Overseer reads the edits and proposes an updated version with a brief explanation of what changed and why
4. This repeats until user clicks **"Confirm Phases"**
5. Session cannot start until phases are confirmed

### Step 4 — Agent Panel Suggestion (new)

After phases are confirmed, if the user has not yet placed agents on the canvas, the system suggests a panel.

**Agent suggestion prompt for Stress Test:**
```
You are designing a review board for a multi-agent stress-test session.

The documents being reviewed:
{document_summaries}

The confirmed phases:
{phases}

Suggest 4-6 agents with distinct review lenses that together cover:
- The domain knowledge needed to evaluate the documents
- At least one agent whose job is to find contradictions and weak logic
- At least one agent who represents the human/execution reality
- The right adversarial tension to produce a genuine stress-test (not a rubber stamp)

Return JSON array:
[{
  "name": "Agent_Name",
  "role_tag": "2-3 word label",
  "mission": "one sentence",
  "lens": "what this agent specifically looks for in the documents",
  "web_search": true/false,
  "web_search_rationale": "one sentence",
  "full_persona": "complete persona following the standard must-contain structure"
}]
```

User sees suggested agents as draggable cards. They can:
- Accept any agent as-is (drag to canvas)
- Edit an agent before accepting
- Replace an agent with one from the library
- Add additional agents
- Ignore suggestions entirely and build the panel from scratch

---

## 4. SESSION MECHANICS (modifications to existing system)

### 4.1 Full document context from round 1

In Stress Test mode, all uploaded documents are included in every agent's context from the start. This is different from other modes where documents are optional context.

The document injection order in agent context:
```
1. Problem statement + phase plan (what the session is doing)
2. All uploaded documents (full text, all of them)
3. Memory doc (from round 11 onwards)
4. Last 15 raw messages verbatim (from round 11 onwards)
5. Current phase directive (what phase is active, what question must be answered)
6. Agent's own persona
```

### 4.2 Phase directive

The Overseer injects a phase directive at the start of each phase. This is a structured system message that tells agents:
- Which phase is now active
- What the focus question is
- What the key subquestions are
- What has been confirmed in previous phases (carried forward from artifacts)
- What must NOT be re-debated (already settled)

Format:
```
[PHASE {N} NOW ACTIVE]

Focus: {phase_name}
Primary question: {focus_question}

Key questions to resolve this phase:
· {subquestion_1}
· {subquestion_2}
· {subquestion_3}

Carried forward from previous phases:
CONFIRMED: {list of confirmed items}
CONTESTED: {list of unresolved items from previous phases}

Do not re-open confirmed items unless you find a direct contradiction
in the current phase documents. Stay focused on Phase {N}.
```

### 4.3 Phase-aware selector

The hybrid selector in Stress Test mode adds phase awareness to its LLM contextual pick. The selector prompt includes the current phase focus question and prioritises agents whose lens is most relevant to the current phase documents.

Add to the existing `_SELECTOR_PROMPT`:
```
Current phase: {phase_name}
Phase focus: {focus_question}
Phase-relevant agents: {agents whose lens directly applies to this phase}

Prioritise phase-relevant agents unless another agent has a specific
cross-cutting challenge to make.
```

### 4.4 Minimum rounds enforcement

Minimum rounds are dynamic — calculated from user input, not hardcoded.

**User sets one value before the session starts:**
```
Min rounds per phase:  user_setting  (default: 20, range: 10–40)
```

**System calculates total minimum automatically:**
```python
STRESS_TEST_MIN_ROUNDS_PER_PHASE = user_setting          # from UI slider
STRESS_TEST_MIN_TOTAL_ROUNDS     = len(confirmed_phases) * STRESS_TEST_MIN_ROUNDS_PER_PHASE
```

**Examples:**
```
5 phases × 20 rounds = 100 minimum total
3 phases × 20 rounds =  60 minimum total
2 phases × 15 rounds =  30 minimum total
```

**UI — one slider on the Stress Test setup page:**
```
Minimum rounds per phase:  [────●────]  20
                            10          40

Estimated minimum total:  100 rounds  (5 phases × 20)
Estimated cost:           ~$2.80
```

The estimated total and cost update live as the user moves the slider or as phases are added/removed during the phase definition loop.

The Overseer cannot suggest phase advancement until the current phase has run for at least `STRESS_TEST_MIN_ROUNDS_PER_PHASE` rounds.

The Overseer cannot suggest session close until `STRESS_TEST_MIN_TOTAL_ROUNDS` has been reached.

These are minimums — the Overseer may run longer if discussion is not exhausted.

### 4.5 Overseer phase evaluation

Every 5 rounds (not 10 as in other modes — review sessions need tighter Overseer monitoring), the Overseer evaluates:

1. Has the phase focus question been answered?
2. Have all key subquestions been addressed?
3. Has the minimum round count been reached?
4. Is the discussion still productive or has it started repeating?

If all four conditions are met, the Overseer emits a phase completion suggestion (see 4.6). Otherwise it emits a standard constraint reminder (same as other modes) with the current phase's confirmed/contested tally.

**Overseer phase evaluation prompt:**
```
You are monitoring a stress-test review session.

Current phase: {phase_name}
Focus question: {focus_question}
Key subquestions: {subquestions}
Rounds completed this phase: {count}
Minimum required: {STRESS_TEST_MIN_ROUNDS_PER_PHASE}

Recent messages (last 10):
{recent_messages}

Evaluate:
1. Has the focus question been substantially answered? (yes/partial/no)
2. Which subquestions are resolved? Which are still open?
3. Is the discussion still generating new insights or repeating?
4. Has minimum round count been reached? (yes/no)

If all subquestions are addressed AND minimum rounds reached AND discussion is repeating:
→ Return action: "suggest_advance"
   With: confirmed items, contested items, open questions, summary

Otherwise:
→ Return action: "continue"
   With: what still needs to be resolved, which subquestions need more debate

Return JSON:
{
  "action": "suggest_advance" | "continue",
  "confirmed": ["item 1", "item 2"],
  "contested": ["item 1"],
  "open_questions": ["question 1"],
  "continue_reason": "what still needs debate (if action is continue)",
  "summary": "2-3 sentence summary of phase findings (if action is suggest_advance)"
}
```

### 4.6 Phase advancement pause

When the Overseer returns `action: "suggest_advance"`:

1. Session **pauses** — no new agent messages are generated
2. A phase completion card appears in the live feed:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[OVERSEER — Phase {N} Review Complete]

{summary}

CONFIRMED THIS PHASE:
· {item}
· {item}

CONTESTED (unresolved):
· {item}

OPEN QUESTIONS:
· {question}

Recommended: Advance to Phase {N+1}

[ADVANCE TO PHASE {N+1}]   [CONTINUE PHASE {N}]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

3. 60-second timer starts — if no user input, session auto-advances
4. If user clicks **[CONTINUE PHASE N]** — session resumes, Overseer notes this and re-evaluates after 5 more rounds
5. If user clicks **[ADVANCE TO PHASE N+1]** — Overseer writes the phase artifact, then injects the Phase N+1 directive, session resumes

### 4.7 Session close

After `STRESS_TEST_MIN_TOTAL_ROUNDS` is reached AND the final phase is complete, the Overseer emits a session close suggestion using the same pause mechanism:

```
[OVERSEER — Review Complete]

All {N} phases have been reviewed.
Total rounds: {count}

[GENERATE FINAL VERDICT]   [CONTINUE REVIEWING]
```

If user clicks **[GENERATE FINAL VERDICT]** — synthesis runs and produces the final readiness verdict.

If user clicks **[CONTINUE REVIEWING]** — session continues, Overseer re-evaluates every 5 rounds.

---

## 5. ARTIFACT SYSTEM (modifications to existing)

### 5.1 Per-phase artifact

Written by the Overseer when a phase closes (user clicks Advance or auto-advances).

Structure:
```
PHASE {N} — {PHASE_NAME}
Documents reviewed: {doc list}
Rounds: {start} to {end}
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
```

**Phase artifact prompt:**
```
Write the Phase {N} review artifact for a stress-test session.

Phase name: {phase_name}
Documents reviewed: {docs}
Focus question: {focus_question}

Agent discussion (full phase):
{phase_messages}

Produce the artifact in the exact format specified. Be specific — name
documents, name agents who raised issues, quote specific claims that
were challenged. No vague summaries. Every item must be actionable.

A reader who was not in the session must be able to read this artifact
and know exactly what was found, what was confirmed, and what must change.
```

### 5.2 Final readiness verdict

Produced after all phases are complete. Reads all phase artifacts.

Structure:
```
STRESS TEST — FINAL READINESS VERDICT
Documents reviewed: {list}
Total phases: {N}
Total rounds: {count}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OVERALL VERDICT
READY / NOT READY / CONDITIONALLY READY

[One paragraph explaining the verdict]

BLOCKING ISSUES
[Must be resolved before the next step — specific, actionable]
· {issue}: {what must change}

NON-BLOCKING ISSUES
[Should be addressed but do not block progress]
· {issue}: {recommendation}

CONFIRMED SOUND — DO NOT REVISIT
[Items that survived stress-testing across all phases]
· {item}

CROSS-PHASE CONTRADICTIONS
[Places where findings in one phase conflict with another]
· {contradiction}: {which phases · what the conflict is}

RECOMMENDED FIRST ACTION
[The single most important thing to do before proceeding]
```

**Final verdict prompt:**
```
You are producing the final readiness verdict for a stress-test review session.

The following phase artifacts were produced during the session:
{all_phase_artifacts}

Produce the final verdict in the exact format specified. The verdict must:
- Give a clear overall verdict (Ready / Not Ready / Conditionally Ready)
- List only genuine blocking issues — not things that are merely imperfect
- Confirm items that genuinely survived challenge
- Identify any contradictions between phase findings
- Give one specific recommended first action

Be direct. Do not hedge. This verdict will be used to make a real decision.
```

---

## 6. OUTPUT FILES (Stress Test)

```
stress_test_transcript_{timestamp}.md     — full session transcript
stress_test_phase_{N}_artifact_{timestamp}.md  — one file per phase
stress_test_verdict_{timestamp}.md        — final readiness verdict
stress_test_summary_{timestamp}.zip       — all of the above
```

---

## 7. NEW DATA MODELS

Add to existing session data model:

```python
# Additions to Session model
mode: enum (product | conclusion | stress_test)   # extend existing enum
uploaded_documents: list[UploadedDocument]         # new field
phases: list[Phase] | None                         # new field — Stress Test only
current_phase_index: int | None                    # new field

class UploadedDocument:
    id: str
    filename: str
    filetype: str
    content_text: str        # extracted plain text
    size_bytes: int
    uploaded_at: datetime

class Phase:
    number: int
    name: str
    documents: list[str]     # document IDs assigned to this phase
    focus_question: str
    key_subquestions: list[str]
    rationale: str
    status: enum (pending | active | complete)
    start_round: int | None
    end_round: int | None
    artifact: str | None     # artifact content when phase closes
    confirmed: list[str]     # confirmed items from this phase
    contested: list[str]     # unresolved items
    open_questions: list[str]
```

---

## 8. NEW WEBSOCKET MESSAGE TYPES

Add to existing WebSocket message types:

```json
{ "type": "phase_directive",       "phase_number": 2, "phase_name": "...", "focus_question": "...", "subquestions": [...] }
{ "type": "overseer_phase_eval",   "action": "suggest_advance", "confirmed": [...], "contested": [...], "summary": "..." }
{ "type": "phase_pause",           "phase_number": 2, "timeout_seconds": 60 }
{ "type": "phase_advanced",        "from_phase": 1, "to_phase": 2 }
{ "type": "phase_artifact_written","phase_number": 1, "content": "..." }
{ "type": "session_close_suggest", "total_rounds": 127, "phases_complete": 5 }
{ "type": "verdict_generating"     }
{ "type": "verdict_complete",      "content": "..." }
{ "type": "phase_continue",        "phase_number": 2, "reason": "user override" }
```

---

## 9. NEW API ENDPOINTS

Add to existing API:

```
POST /api/sessions/{id}/analyse-documents
     → triggers phase inference, returns proposed phases

POST /api/sessions/{id}/confirm-phases
     → locks phase plan, enables session start

POST /api/sessions/{id}/advance-phase
     → user manually advances phase (overrides Overseer)

POST /api/sessions/{id}/continue-phase
     → user overrides Overseer suggestion to advance

GET  /api/sessions/{id}/phases
     → returns all phase definitions + current status

GET  /api/sessions/{id}/artifacts
     → returns all phase artifacts written so far

POST /api/upload/stress-test
     → uploads documents for Stress Test mode
     → extracts text, returns doc_id + preview
```

---

## 10. FRONTEND ADDITIONS

### Pre-session phase definition UI
- Phase cards on canvas — each card shows: phase name, documents assigned, focus question, subquestions
- Cards are editable inline
- **Re-interpret** button sends edits back to Overseer
- **Confirm Phases** button locks the plan and enables Begin Symposium
- Phase cards shown in sequence with visual connector between them

### Live session additions
- Phase indicator in stats bar — "Phase 2 of 5 — Capability Map + Scoring"
- Phase advancement pause card in live feed (as described in 4.6)
- Per-phase artifact appears as a collapsible section in the artifact panel when phase closes
- Document list shown in sidebar — documents highlighted when their phase is active

### Results page additions
- Tab per phase artifact (Phase 1, Phase 2, Phase 3...)
- Final Verdict tab shown prominently
- All artifacts + verdict downloadable as individual files or ZIP

---

## 11. DOCUMENT TEXT EXTRACTION

Extract plain text from all uploaded file types before session starts:

```python
# PDF → use pypdf or pdfminer
# DOCX → use python-docx or pandoc
# XLSX/CSV → convert to markdown table format
# TXT/MD → use as-is

# All extracted text stored in UploadedDocument.content_text
# Injected into agent context as:

UPLOADED DOCUMENTS
══════════════════

[Document 1: {filename}]
{content_text}

[Document 2: {filename}]
{content_text}

...
```

Libraries needed:
```
pypdf
python-docx
openpyxl
pandas  (for CSV/XLSX → markdown table)
```

---

## 12. BUILD ORDER FOR THIS ADDITION

Build in this order — do not start next item until current one works:

1. **Document upload endpoint** — accept files, extract text, store, return doc_id
2. **Phase inference** — send docs + problem statement to Gemini Flash, return proposed phases
3. **Phase definition UI** — editable phase cards on canvas, Re-interpret loop, Confirm button
4. **Agent suggestion for Stress Test** — Overseer reads docs, suggests panel
5. **Session data model extensions** — Phase, UploadedDocument models, DB migrations
6. **Document context injection** — all docs fed into agent context from round 1
7. **Phase directive injection** — Overseer injects phase directive at phase start
8. **Phase-aware selector** — add phase context to existing selector prompt
9. **Overseer phase evaluation** — every 5 rounds, evaluate phase exhaustion
10. **Phase pause mechanic** — pause session, emit pause card, 60s timer, user buttons
11. **Phase artifact writing** — write artifact when phase closes, store, display
12. **Min rounds enforcement** — STRESS_TEST_MIN_ROUNDS_PER_PHASE + STRESS_TEST_MIN_TOTAL_ROUNDS
13. **Session close mechanic** — Overseer suggests close, same pause pattern
14. **Final verdict generation** — reads all phase artifacts, produces verdict
15. **Results page** — per-phase artifact tabs, verdict tab, download buttons
16. **End-to-end test** — run a full Stress Test session with the Lemnisca wet lab documents

---

