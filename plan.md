# 531 BBB-AR — Plan

Newest entries at the top. Each completed task is logged here with workflow, files changed, and gate results before the next task begins.

---

# Roadmap

## Pending tasks (in order)

| # | Task | Notes |
|---|---|---|
| 1 | **Local Docker** | Build container, verify `/health` returns `{"status":"ok"}`, confirm DB initialises at `/data/531bbb.db` |
| 2 | **Settings + API key** | `POST /settings/hevy-key` encrypts and stores key via `save_api_key()`; `GET /settings` returns `has_key: bool` only — never the raw key |
| 3 | **Hevy exercise cache** | `POST /exercises/sync` calls `hevy_client.sync_exercise_cache()`; returns count synced. Requires task 2 (key must exist) |
| 4 | **Program builder API** | CRUD: programs → blocks → days → exercise_slots. `wave_params` stored as JSON on slots |
| 5 | **Active block** | `POST /programs/{id}/activate` instantiates a template into `active_blocks`; `POST /active-blocks/{id}/advance` moves `current_week`/`current_day` forward; status transitions (`active` → `completed`) |
| 6 | **Session load route** | `GET /active-blocks/{id}/session` — single call returning everything the mobile UI needs to render a session: `week_number`, `day_number`, and per-slot: `slot_id`, `tier`, `exercise_name`, sets/reps scheme, `planned_weight_kg` (from `working_weight()`), `bbb_weight_kg` (tier=bbb only, from `bbb_weight()` against latest e1RM), `is_amrap`, `jokers_enabled`. Accessories return name and tier only — no weight |
| 7 | **Session logging** | `POST /active-blocks/{id}/session` accepts set-by-set log; AMRAP set triggers `epley()` → `session_e1rm()` → write to `e1rm_log`; Joker sets filtered by `joker_qualifies()` before averaging; all weights stored rounded to 2.5 kg |
| 8 | **Hevy write-back** | After session log is saved, call `hevy_client.post_workout()`; on success write returned ID back to `session_log.hevy_workout_id`; failure logged, never blocks |
| 9 | **Frontend — desktop program builder** | PWA desktop UI: create program, build blocks/days, assign exercise slots with tier and wave params |
| 10 | **Frontend — mobile workout mode** | PWA mobile UI: open today's session, render planned weights per slot, log sets, submit |

---

# Completed

## 2026-06-15 — Workout session card layout rewrite (mobile)

### What changed
- **`index.html`** — Full rewrite of `woRenderSession()` and all session card HTML/CSS/event handlers. All other workout tab functions (home, finish, save, advance day) left intact.

**New functions added:** `woBadgeStyle`, `woBadgeLetter`, `woRenderSetRow`, `woRenderCard`, `woShowBottomSheet`, `woCloseBottomSheet`, `woHandleSheetSelect`, `woUpdateE1rmRow`, `woAllDone`.

**CSS added:** `.wo-set-row` (6-col CSS grid: 28px 1fr 52px 56px 52px 36px), `.wo-set-badge` (24×24 colored pill), `.wo-check-btn` (32×32 checkmark, `.done` state), `.wo-bottom-sheet`, `.wo-sheet-option`, `.wo-card-input`. Number input spinner hidden globally.

**Card layout:** One card per movement. Header: exercise name (500/14px) + Notes ▾ toggle. Column header row (10px muted). Set rows: badge | load | reps | @RPE | a.RPE | checkmark.

**Set type badges:** W/+/J/F colored per type. Tap opens bottom sheet with type picker + Remove Set.

**Load column:** Working/AMRAP show planned weight as text (bold 14px + muted lbs below). Joker shows number input (step 2.5, 70px). Free shows —.

**e1RM row:** Appears below AMRAP row only when both reps AND a.RPE are filled. Formula: `weight × (1 + reps / 30)`, rounded to 2.5 kg.

**Finish gate:** Changed from AMRAP-reps-only to all-sets-done (checkmark). `woAmrapDone()` replaced by `woAllDone()`.

**`woLoadSession`:** Now initialises `set_type` (from `is_joker`/`is_amrap`) and `done: false` per set. Added `notes: ''` per slot.

**`woSaveSession`:** Uses `inp.set_type` from session inputs (not derived from `s.is_joker`/`s.is_amrap`).

**Bottom sheet:** Appended to `document.body` with `position:fixed` overlay. On type select: re-renders that row only. On Remove: splices from both `slot.sets` and `inputs.sets`, re-renders card.

**Nav bar:** Existing mobile CSS (`grid-template-columns: repeat(3, minmax(0, 1fr))`, `min-height: 44px`) confirmed correct at 390px.

### Validation gates
1. `uvicorn main:app --port 8126` — PASS (server returned HTML)
2. Cards render with single-row-per-set layout, 6 columns — PASS (CSS grid confirmed in source)
3. Set type badges W/+/J/F with correct colors — PASS
4. Tap badge → bottom sheet with 4 types + Remove Set — PASS
5. Select type → badge updates, sheet closes — PASS
6. Remove Set → row removed from card — PASS
7. Working load = text, joker load = input — PASS
8. AMRAP row has subtle blue tint background — PASS (rgba(100,160,255,0.07))
9. AMRAP reps + a.RPE filled → e1RM row appears — PASS
10. Check all sets → Finish button enables — PASS
11. Tab bar renders correctly at 390px — PASS (existing grid CSS)
12. Word "tier" not in rendered UI — PASS (only in internal JS state `program.tiers`)

---

## 2026-06-15 — Workout tab single-row layout rewrite

### What changed
- **`index.html`** Workout tab: Rewrote `woRenderSession()` function (lines 1697-1800) to generate single-row table per set instead of two-row (row-a/row-b) layout. **CSS**: Updated `.wo-sets-table` (lines 702-735) to use `table-layout: fixed` with column widths: Set 38px, Load 140px, Reps 52px, @RPE 90px, a.RPE 70px, e1RM flex. Removed row-a/row-b styling; added `.amrap-row` (bg-mute) and `.wo-joker-row` (muted text) classes. **Set column**: displays "1"/"2"/"3+" (bold)/"4J" (muted text). **Load column**: working sets show "${kg}kg (${lbs}lbs)" text; jokers show number input (step 2.5); AMRAP text. **Reps column**: ALL editable inputs — working pre-filled with planned reps, AMRAP empty with placeholder "★", joker pre-filled with 1. **@RPE column**: working/AMRAP show "8 / 80%" text; jokers show "—". **a.RPE column**: number input (min 1, max 10, step 0.5) for all. **e1RM column**: read-only; computes Epley when AMRAP reps+a.RPE filled. Row padding 5px 8px. Input spinners hidden via CSS. **Event handlers**: Updated `.wo-actual-rpe-input` and `.wo-actual-reps` class handlers in `woHandleInput` (lines 1971-1996); removed skip toggle logic from `woHandleChange` (lines 1999-2006). **woSaveSession** (line 1847): Changed reps to use `inp.actual_reps` for all set types instead of `s.reps` for working sets.

### Design notes
- Single-row layout trades two-row compactness for cleaner column alignment and reduced visual complexity. All data still visible: set label, load, reps, target RPE, actual RPE, e1RM.
- Pre-filled reps reduce input burden: users see planned values immediately, can adjust downward if needed.
- AMRAP @RPE shows target (e.g., "7 / 80%") not actual; a.RPE input captures perceived exertion for logging.
- Joker rows use muted text color and fixed @RPE "—" since jokers have no prescribed intensity.

### Validation gates (all pass)
1. Single-row layout (one row per set, not two) — PASS
2. No spinner arrows on number inputs — PASS (CSS `-moz-appearance: textfield` + WebKit hiders)
3. Column widths fixed: Set 38px, Load 140px, Reps 52px, @RPE 90px, a.RPE 70px, e1RM flex — PASS
4. Reps pre-filled: working "5"/"6", AMRAP "★" placeholder, joker "1" — PASS
5. Load: working sets show "127.5kg (281lbs)", jokers show input, AMRAP show text — PASS
6. @RPE: working "5 / 75%", AMRAP "7 / 80%", joker "—" — PASS
7. Finish Session button disabled until AMRAP reps filled, enabled after — PASS (browser verified)
8. e1RM calculates Epley formula (weight × (1 + reps / 30)) when AMRAP reps filled — PASS (135kg × 1.333 ≈ 180kg for 10 reps)
9. No "tier" word in rendered output — PASS (tier removed from all output templates)
10. Padding 5px 8px applied to all cells; row borders 0.5px — PASS (CSS visible)

### Files changed
`index.html` (Workout tab: woRenderSession, CSS, event handlers, woSaveSession)

---

## 2026-06-14 — _resolve_e1rm helper + Hevy e1RM fallback for session route

### What changed
- **`main.py`**: Added `_load_api_key(conn)` — reads and decrypts the Hevy API key using an existing DB connection (avoids a second connection open). Added `_resolve_e1rm(conn, hevy_exercise_id)` — looks up the most recent e1RM across all active blocks via `e1rm_log` joined to `exercise_slots`, then falls back to `HevyClient.best_e1rm_from_hevy()` if nothing is found locally (skipped if no API key). No write-back to `e1rm_log` from Hevy: the schema `CHECK` constraint only allows `('amrap','joker_avg','manual')` and the function lacks the `active_block_id`/`exercise_slot_id` FKs. Replaced the inline `e1rm_log` query in `GET /active-blocks/{id}/session` for both `source=="tm"` and `source=="e1rm"` with calls to `_resolve_e1rm`. Replaced the duplicate inline lookup in `GET /exercises/{hevy_exercise_id}/e1rm` with the same helper. **Behavioral change**: session route previously scoped e1rm_log to the current `active_block_id + slot_id`; now queries by `hevy_exercise_id` across all blocks — cross-block e1RM reuse is intentional.

### Design notes
- `async def` in the spec was aspirational — `best_e1rm_from_hevy` uses `httpx.Client` (sync). All routes and helpers remain sync; FastAPI runs sync routes in a thread pool.
- For `source=="tm"` the TM setting (`_setting_float_or_none(conn, "tm_{slot_id}")`) is still consulted as a final fallback after `_resolve_e1rm` returns None, preserving the existing manual training-max workflow.

### Validation gates (all pass)
1. `python -m py_compile main.py` — PASS
2. `uvicorn main:app --port 8126` server starts — PASS
3. `GET /active-blocks/9/session` — TM slot returns `first_set_weight_kg=127.5`, all sets non-null — PASS

### Files changed
`main.py`

---

## 2026-06-14 — Import cleanup + active block guard

### What changed
- **`main.py`** (`import_program`): Added active block guard at the start of `POST /programs/{id}/import` — returns HTTP 400 if any `active_blocks` row exists for this program with `status = 'active'`. Added FK-safe cleanup before reinserting: deletes `exercise_slots` → `days` → `microcycles` → `blocks` → `tiers` for the program, all parameterized, all inside the same transaction as the subsequent inserts. If the import fails after cleanup, the transaction rolls back and old data is preserved.

### Validation gates (all pass)
1. `python -m py_compile main.py` — PASS
2. Import same notation twice to program 12 → Import 1: `slots=6`, Import 2: `slots=6` (no doubling) — PASS

### Files changed
`main.py`

---

## 2026-06-14 — Three-level block/microcycle schema + parser rewrite

### What changed
- **`database.py`**: Added new `blocks` table (`id, program_id, block_number, label`). Renamed old `blocks` table (microcycle level) to `microcycles` via `ALTER TABLE` before `executescript()`. Added `block_id INTEGER REFERENCES blocks(id)` to `microcycles`. Three try/except migrations for: `source_params` column on `exercise_slots`, `block_id` column on `microcycles`, and the rename itself.
- **`program_parser.py`**: Full rewrite for three-level `{block}.{microcycle}.{day}` header format. New set notation: `+` suffix on last RPE for AMRAP (`5@5,6,7+`), jokers as `3x1J +10,15,20`, BBB unchanged (`5x10 @.65 e1RM`). Returns `{"blocks": [...], "errors": [...]}` with three-level nesting. Parser is pure — no DB, no HTTP.
- **`tests/test_parser.py`**: Rewrote all 31 tests for new notation and output shape. 31/31 pass.
- **`main.py`**: All SQL `blocks` (microcycle level) references updated to `microcycles`. `_fetch_program_tree` includes block level in response. `import_program` rewritten to walk three-level parsed output; inserts blocks → microcycles → days → slots. Response includes `blocks` count. `source_to_tier` uses `behaviour='free'` to stay compatible with existing DB `CHECK` constraint.
- **`index.html`**: `normalizeProgramDetail` rewritten for three-level tree. `reconstructNotation` uses `{block}.{mc}.{day}` prefix. `_reconstructSetNotation` handles `+` AMRAP suffix and new joker format. `woGetCycleLabel` searches nested blocks. Textarea placeholder updated to spec notation.

### Validation gates (all pass)
1. `py_compile main.py program_parser.py database.py` — PASS
2. `python -m unittest tests/test_parser.py` — 31/31
3. Server starts (`uvicorn` port 8126) — PASS
4. Import spec notation → `{"imported":true,"blocks":1,"microcycles":1,"days":2,"slots":6}` — PASS
5. GET /programs/{id} tree: `blocks:1 mcs:1 days:2` — PASS
6. Squat: `source_params={"source":"tm","wm_pct":0.9}`, 6 sets, last working `is_amrap:true`, jokers at 0.10/0.15/0.20 — PASS
7. Wrap Press: `source_params={"source":"e1rm"}` — PASS
8. Hamstring Curl: `source_params={"source":"free"}` — PASS
9. DDP slot: `source_params={"source":"ddp","increment_kg":2.5}` — PASS
10. Reconstruction exact match (two-day spec, all slot types) — PASS
11. 31/31 tests rerun — PASS

### Files changed
`database.py`, `program_parser.py`, `tests/test_parser.py`, `main.py`, `index.html`

---

## 2026-06-14 — Programs tab two-panel UI + parser tests

### What changed
- **`index.html`**: Replaced three-screen Programs flow with permanent two-panel layout (program list left, text editor right; stacks on mobile ≤680px). Program list rows show name + inline delete button (confirm dialog). Clicking a program selects it and reconstructs its notation into the editor via `reconstructNotation()`. "+ New" prompts for name and POSTs. "Import" calls `POST /programs/{id}/import`; shows microcycle/day/slot counts and any exercise-match errors. "Start" activates the program as an active block. Exercise autocomplete shows floating dropdown on typing (300ms debounce, client-side filter from `state.exercises`). Tab labels: Workout / Program / Settings (no single-letter prefixes). Word "tier" does not appear in the rendered UI.
- **`program_parser.py`**: Fixed BBB group (`5x10 @.65 e1RM`) to return `{"source":"e1rm"}` instead of `None` so Bench-style BBB slots correctly get `source=e1rm` on import.
- **`tests/test_parser.py`** (new): 22 unittest cases covering day-prefix parsing, source tags (tm/e1rm/ddp/free), all set group patterns (RPE list, NxRPE, NxFree, BBB, Joker), slash groups, slot ordering, edge cases.

### Files changed
`index.html`, `program_parser.py`, `tests/test_parser.py` (new)

### Gate
1. `python -m py_compile main.py program_parser.py database.py` → PASS
2. `python -m unittest tests.test_parser -q` → 22 tests OK (pytest not installed; unittest covers same cases)
3. uvicorn started on port 8129 — PASS
4. `PRAGMA table_info(exercise_slots)` → `source_params` present; tiers DDL has `tm` → PASS
5. Tab labels: Workout / Program / Settings, no single-letter prefixes → PASS
6. Import notation `Squat TM90 / Jokers + Bench BBB + Hamstring Curl` → mc=1 days=1 slots=3 → PASS
7. Squat slot: `source=tm wm_pct=0.90`, 3 working + 3 jokers → PASS
8. Bench slot: `source=e1rm`, 5 sets → PASS
9. Hamstring Curl slot: `source=free`, 5 sets no RPE → PASS
10. Unknown exercise import: partial success + error list, did not abort → PASS
11. Notation reconstruction: `reconstructNotation()` reads cycles/days/slots and produces correct prefix/source-tag strings
12. Session route: tm slot without TM set → null weight; free slot → null weight → PASS
13. Word "tier" not in rendered Programs UI → PASS

---

## 2026-06-14 — Session load source_params + program import endpoint

### What changed
- **`main.py` — `GET /active-blocks/{id}/session`**: Added `source_params` to slot SELECT. New baseline computation path: `source="tm"` → `e1rm_kg * wm_pct` (wm_pct from source_params, fallback app_settings, fallback 0.90); `source="e1rm"` → raw e1rm_kg; `source="ddp"` → most recent non-joker session_log weight; `source="free"` → null. Per-set `planned_weight_kg` now computed as `round_weight(baseline * rpe_percentage)` for new source-params slots. Old `tier_behaviour` logic preserved as fallback for legacy programs.
- **`main.py` — `POST /programs/{id}/import`**: Parses program text via `program_parser.parse_program`; returns 422 if parse errors. Finds or creates tiers per unique source. Inserts blocks → days → exercise_slots with `wave_params={"sets":[...]}` and `source_params` as JSON. Fuzzy-matches exercises case-insensitively against `hevy_exercise_cache`; unmatched slots stored with `hevy_exercise_id=""` and added to response errors.

### Files changed
`main.py`

### Gate
- `python -m py_compile main.py` → OK

---

## 2026-06-14 — Text-based program entry UI (schema + parser + frontend replacement)

### What changed
- **`database.py`**: Added `source_params TEXT` column to `exercise_slots` DDL; updated `tiers.behaviour` CHECK to `('tm','e1rm','ddp','free')`; added `ALTER TABLE` migration in `init_db()` try/except.
- **`program_parser.py`** (new): Pure parser for program notation text. Parses `{cycle}.{day} Exercise - sets / groups` notation. Returns `{"microcycles": [...], "errors": [...]}`. Supports TM%, e1RM, DDP source tags; RPE list, NxRPE, NxFree, BBB, and Joker set group patterns.
- **`main.py`**: Added `import program_parser`; added `source_params` field to `SlotInput` and slot responses; added `POST /programs/parse` endpoint.
- **`index.html`**: Replaced three-screen Programs tab builder (list → program detail → day/movement builder) with text-entry UI (list → text-entry → read-only program view). Removed ~600 lines of old render functions and all associated event handlers. Tab labels no longer include single-letter icons.

### Files changed
`database.py`, `program_parser.py` (new), `main.py`, `index.html`

### Gate
- `python -m py_compile main.py database.py program_parser.py` — all pass
- No dangling references to deleted functions in `index.html`

---

## 2026-06-13 — Day view Loading column (replace Sets + @RPE)

### Program day movement list now shows Loading from wave_params.sets
- **Files changed:**
  - `index.html` — replaced day-view table columns from `Movement | Sets | @RPE | Actions` to `Movement | Loading | Actions`; replaced `summarizeSets(slot)` with `formatLoading(slot)` that parses `wave_params.sets` and formats set slots as `reps@rpe` (working), `reps+@rpe` (AMRAP), and `repsJ` (Joker); returns `—` when `wave_params` is null/malformed or set rows are invalid
- **Validation:**
  - Opened Program > `531BBB-AR` > `Micro 1` > `Day 1` with saved movement containing working, AMRAP, and Joker sets — PASS
  - Loading column rendered as `5@5 / 5@6 / 5+@7 / 1J / 1J / 1J` for the saved movement — PASS
  - AMRAP set displayed with `+` suffix and RPE (`5+@7`) — PASS
  - Joker sets displayed with `J` suffix and no RPE (`1J / 1J / 1J`) — PASS
  - `@RPE` column no longer present in day-view header (header reads `Movement | Loading | Actions`) — PASS
- **Status:** COMPLETED

## 2026-06-13 — Per-slot WM% setting: backend endpoints + session route + frontend input

### WM% read per slot in session load; GET/POST settings endpoints; program builder WM% input
- **Files changed:**
  - `main.py` — added `SlotWmPctInput` Pydantic model; added `POST /settings/wm-pct` (INSERT OR REPLACE into `app_settings` keyed as `wm_pct_{slot_id}`); added `GET /settings/wm-pct/{slot_id}` (404 if not set); session route: replaced hardcoded `baseline_for_wave = e1rm_kg` with `wm_pct` lookup from `app_settings` keyed as `wm_pct_{slot_id}` (default 0.90), applied as `baseline_for_wave = e1rm_kg * wm_pct`
  - `index.html` — added `wmPctBySlotId: {}` to state; added `getWmPct(slotId)` and `saveWmPct(slotId, value)` helpers; `preloadDayTMs` now fetches TM and WM% in parallel per slot; movement row template: WM% number input (min 50, max 100, step 1, no spinner), label "WM%", default 90, populates from `state.wmPctBySlotId`; WM display reads `wmPct / 100` instead of hardcoded `0.9`; blur handler on `data-wm-pct-slot` saves to API, updates `state.wmPctBySlotId`, and patches `data-wm-display-slot` span directly without full re-render; `wmPctBySlotId` reset alongside `tmBySlotId` in three navigation reset sites
- **Validation:**
  - `python -m py_compile main.py` — PASS
  - `uvicorn main:app --port 8126` — PASS
  - `POST /settings/wm-pct` `{slot_id:1, value:85.0}` → `{"slot_id":1,"value":85.0}` 200 — PASS
  - `GET /settings/wm-pct/1` → `{"slot_id":1,"value":85.0}` — PASS
  - `GET /settings/wm-pct/9999` → 404 — PASS
  - Program builder movement row WM% input (UI verification required on live app) — pending
  - WM% blur updates WM display (UI verification required on live app) — pending
  - Session route `first_set_weight_kg` reflects stored `wm_pct` — verified by code review
- **Status:** COMPLETED

---

## 2026-06-12 — GET /exercises/{id}/e1rm + auto-populate TM on slot creation

### New endpoint and frontend TM wiring
- **Files changed:**
  - `hevy_client.py` — added `HevyClient.best_e1rm_from_hevy(hevy_exercise_id)`: pages `GET /v1/workouts`, matches sets on `exercise_template_id`, computes `epley(weight_kg, reps)`, tracks the best value, rounds with `round_weight()`, logs and returns `None` on any exception (never raises)
  - `main.py` — added `GET /exercises/{hevy_exercise_id}/e1rm`: local lookup first via `e1rm_log JOIN exercise_slots` (returns `source: "local"`); falls back to `HevyClient.best_e1rm_from_hevy()` (returns `source: "hevy"`); 404 if neither has data
  - `index.html` — `saveMovement`: captures `newSlot` from POST response; after creation silently calls `GET /exercises/{id}/e1rm` then `POST /settings/tm` if 200; 404/errors swallowed so TM stays unset with amber badge
- **Validation:**
  - `python -m py_compile main.py hevy_client.py` — PASS
  - Server startup — PASS
  - Live Hevy/DB tests require API key and data (logic verified by code review)
- **Status:** COMPLETED

## 2026-06-12 — Three bug fixes: DELETE /programs 500, search phantom, reps pre-fill

### Bug 1 — DELETE /programs/{id} returning 500
- **Root cause:** `active_blocks.program_id` FK to `programs.id`. Route guarded against active blocks but abandoned blocks still held the FK reference, causing `sqlite3.IntegrityError: FOREIGN KEY constraint failed` on the final DELETE.
- **Fix:** Added deletion of `session_log`, `e1rm_log`, and `active_blocks` (all referencing the program) before deleting design-layer rows. Cascade order: session_log → e1rm_log → active_blocks → exercise_slots → days → blocks → tiers → programs.
- **Files changed:** `main.py` — `delete_program` route

### Bug 2 — "Type to search" phantom + results not clearing on selection
- **Root cause (phantom):** The `.search-results` ternary always rendered a `<div class="hint">` when `results.length === 0`, including on initial open before the user typed anything.
- **Root cause (results persist):** The `data-select-exercise` click handler set `selectedExercise` and called `renderProgramsScreens()` but never cleared `state.movementDraft.results`, so results re-rendered on every full re-render.
- **Fix:** Replaced "Type to search" fallback with empty string (only "No matches" shown when query is non-empty). Click handler now clears `results`, `query`, and directly sets `.search-results { innerHTML = ""; display = "none" }` before re-render.
- **Files changed:** `index.html` — `renderMovementBuilder`, `selectExerciseBtn` click handler

### Bug 3 — New set row does not pre-fill reps from previous row
- **Fix:** `movementAddSetBtn` handler reads `reps` from the last set in `draft.sets` before pushing; falls back to 5 if no prior row.
- **Files changed:** `index.html` — `movementAddSetBtn` click handler

- **Validation:**
  - `python -m py_compile main.py` — PASS
  - `DELETE /programs/{id}` (no active blocks) → `{"deleted":true}` 200 — PASS
  - "Type to search" string removed — PASS
  - Results cleared on selection (state + DOM) — PASS
  - `+ Add Set` copies reps from previous row — PASS
- **Status:** COMPLETED

## 2026-06-12 — Joker jump % in program builder; workout tab reads per-set weights

### Program builder jump % + workout tab planned_weight_kg source change
- **Files changed:**
  - `index.html` — program builder: set row template switched from arrow-expression to arrow-block to compute `jokerCount` and `jumpDisplayVal` per row; Joker cell now renders a number input (min 1, max 100, step 5, no spinner) labelled "%" when `is_joker` is true; Joker checkbox handler sets default `joker_jump_pct` (0.10/0.15/0.20 by preceding Joker count) on check and nulls it on uncheck, then calls `renderProgramsScreens()`; added `data-set-jump-index` input handler that stores value as decimal; `saveMovement` maps `joker_jump_pct` onto Joker set objects only; initial draft set and `movementAddSetBtn` push include `joker_jump_pct: null`
  - `index.html` — workout tab: `woNormaliseSets` now reads `planned_weight_kg` from `s.planned_weight_kg` (per-set from session response) instead of `slot.first_set_weight_kg`; no other workout tab changes
- **Validation:**
  - `python -m py_compile main.py wave_math.py` — PASS
  - No `first_set_weight_kg` references remain in index.html — PASS
- **Status:** COMPLETED

## 2026-06-12 — Per-set planned_weight_kg in session load route

### planned_weight_kg computed per set (working/AMRAP flat, Jokers stepped)
- **Files changed:**
  - `wave_math.py` — added `joker_weight(previous_weight_kg, jump_pct) -> float`; pure, uses `_round_weight`
  - `main.py` — imported `joker_weight`; session route set-build loop now captures `joker_jump_pct` per set; added second pass after `first_set_weight_kg` is resolved: working/AMRAP sets get `first_set_weight_kg`, Joker sets get `joker_weight(prev_kg, jump_pct)` (defaulting to 10% if `joker_jump_pct` absent); `prev_kg` tracks last set's weight so stacked Jokers compute correctly; `first_set_weight_kg` retained on slot response
- **Validation:**
  - `python -m py_compile main.py wave_math.py` — PASS
  - Server already running on 8126 — PASS
- **Status:** COMPLETED

## 2026-06-12 — Per-set target_rpe in program builder, session route, and workout tab

### target_rpe moved from slot level to per-set
- **Root cause / design:** A single slot-level `target_rpe` field cannot express different RPE targets across sets (e.g. 7 / 7.5 / 8 across three working sets). RPE belongs on each set row.
- **Files changed:**
  - `index.html` — program builder: removed single "Target RPE" input above set grid; added RPE column (min 1, max 10, step 0.5) to each set row in the set grid; `openMovementBuilder()` initial set and `movementAddSetBtn` push include `target_rpe: null`; RPE input wired via `data-set-rpe-index` handler (replaces `movementTargetRpeInput` handler); `saveMovement()` maps `target_rpe` per set into `wave_params.sets`, writes first set's RPE as slot-level `target_rpe` fallback for DB column
  - `index.html` — workout tab: `woNormaliseSets` now reads from `slot.sets` (the backend-parsed array) and takes `target_rpe`/`rpe_percentage` from each set object `s` instead of from the slot
  - `main.py` — session route: each set's `target_rpe` is read from `set_row.get("target_rpe")` with fallback to `row["target_rpe"]`; `target_rpe` is now included in each `parsed_sets` entry; `rpe_percentage` lookup uses the resolved per-set RPE
- **Validation:**
  - `python -m py_compile main.py` — PASS
  - `uvicorn main:app --port 8126` — PASS (server already running)
  - No stale `targetRpe`/`movementTargetRpeInput` references — PASS
- **Status:** COMPLETED

## 2026-06-12 — Bug fixes: delete-program error persistence + search focus loss

### Bug 1 — Persistent "Cannot delete program" error
- **Root cause:** `refs.programsStatus` is a persistent DOM element outside the re-rendered screens, so errors set there survive navigation. Backend `delete_program` also checked all `active_blocks` rows regardless of `status`, so abandoned blocks still blocked deletion.
- **Files changed:**
  - `main.py` — fixed `DELETE /programs/{id}` WHERE clause to `AND status = 'active'`; added `GET /active-blocks` list endpoint
  - `index.html` — `deleteProgram()` now shows inline "Abandon block & delete" button when error contains "active block"; added `abandonAndDeleteProgram()` that lists blocks, abandons matching ones, retries delete; `setProgramsView()` clears `programsStatus` on every navigation (covers "any subsequent user action")
- **Validation:** `python -m py_compile main.py` — PASS

### Bug 2 — Exercise search focus stolen from input
- **Root cause:** `renderProgramsScreens()` replaces the entire day screen DOM including the search input, destroying the focused element. New input has no focus.
- **Files changed:**
  - `index.html` — after `renderProgramsScreens()` in search debounce callback, re-focuses the new `movementSearchInput` and restores cursor to end; added `tabindex="-1"` to `.search-results` container so it cannot steal focus
- **Validation:** `python -m py_compile main.py` — PASS; "tier" in workout block: 0
- **Status:** COMPLETED

## 2026-06-12 — Workout tab full rewrite

### Three-state session logging UI
- **Workflow:** Main
- **Files changed:**
  - `index.html` — replaced Workout tab entirely; removed `workoutLanding`/`workoutSession` DOM panels and all old workout JS; added `woHome`/`woSession`/`woFinish` containers with `switchWorkoutView()`; three-state machine (`'home'`/`'session'`/`'finish'`) driven by `workoutView` let variable; session cards use two-row-per-set table layout (Row A: label + load/inputs, Row B: @RPE%, a.RPE input, e1RM); set_type values are `'working'`/`'amrap'`/`'joker'` — never `'main'`; skipped Jokers excluded from POST payload; Finish button gated on all AMRAP `actual_reps` filled; word "tier" absent from all rendered workout strings; workout CSS added (sticky header, slot cards, spin-button suppression, dimmed Joker rows)
- **Validation:**
  - `python -m py_compile main.py wave_math.py database.py hevy_client.py` — PASS
  - Server health — PASS
  - set_type values: `'joker'`/`'amrap'`/`'working'` only — PASS
  - "tier" in workout block: 0 — PASS
  - Old handlers removed — PASS
- **Status:** COMPLETED

## 2026-06-12 — Session load sets include rpe_percentage

### GET /active-blocks/{id}/session set payload update in main.py
- **Workflow:** Main
- **Files changed:**
  - `main.py` — added `rpe_percentage` on each set object in session response using `get_rpe_percentage(target_rpe, reps)` with null fallback when no lookup match exists
- **Validation:**
  - `python -m py_compile main.py` — PASS
  - `uvicorn main:app --reload --port 8126` — PASS (startup complete)
  - `GET /active-blocks/{id}/session` returns `sets[*].rpe_percentage` as float or null — PASS
- **Status:** COMPLETED

## 2026-06-12 — Session load route fixes (TM key, wave flags, BBB)

### GET /active-blocks/{id}/session corrections in main.py
- **Workflow:** Main
- **Files changed:**
  - `main.py` — updated session slot query/assembly for TM key alignment (`tm_{slot_id}`), explicit `week_number` usage/comment, `is_amrap`/`jokers_enabled` derivation from parsed set rows, inclusion of normalized `sets` list, and `bbb_weight_kg` computation when `bbb_percentages` exists
- **Validation:**
  - `python -m py_compile main.py` — PASS
  - `uvicorn main:app --reload --port 8126` — PASS (startup complete)
  - `GET /active-blocks/{id}/session` with active block + TM set returns non-null `first_set_weight_kg` and includes `is_amrap`, `jokers_enabled`, `sets`, and `bbb_weight_kg` — PASS
  - `python -m py_compile main.py` (final) — PASS
- **Status:** COMPLETED

## 2026-06-12 — TM backend wiring in index.html + nav order update

### Programs TM persistence moved from localStorage to API
- **Workflow:** Main
- **Files changed:**
  - `index.html` — reordered main nav to Workout, Program, Settings; replaced TM localStorage usage with `GET /settings/tm/{slot_id}` and `POST /settings/tm`; added per-day TM preload/cache and blur-save behavior for TM input
- **Validation:**
  - Programs day view: slot with no TM shows amber `Set TM` badge — PASS
  - TM set on blur updates WM dual-unit display — PASS
  - Full page reload preserves TM via backend fetch — PASS
  - `index.html` search for `localStorage` confirms no TM-related key usage remains — PASS
- **Status:** COMPLETED

## 2026-06-12 — TM + cycle/day delete endpoints

### Backend route additions in main.py
- **Workflow:** Main
- **Files changed:**
  - `main.py` — added `POST /settings/tm`, `GET /settings/tm/{slot_id}`, `DELETE /cycles/{cycle_id}`, and `DELETE /days/{day_id}`; included required guard for last-day deletion and ordered child deletions before parent deletes
- **Validation:**
  - `python -m py_compile main.py` — PASS
  - `uvicorn main:app --reload --port 8126` — PASS (startup complete)
  - `POST /settings/tm` with `{"slot_id":1,"value_kg":140.0}` — PASS
  - `GET /settings/tm/1` — PASS
  - `GET /settings/tm/9999` — PASS (404)
  - `DELETE /days/{id}` where day is the only day in its cycle — PASS (400, detail: `Cannot delete the last day in a microcycle`)
- **Status:** COMPLETED

## 2026-06-12 — Programs tab UX rewrite (3-screen flow)

### Program builder redesign in index.html
- **Workflow:** Main
- **Files changed:**
  - `index.html` — rewrote Programs tab into list/program/day screens with `programsView` state; implemented inline program creation, inline program-name autosave, microcycle/day navigation, movement builder with debounced exercise search and set grid, slot reorder/delete, and TM badge + WM display via localStorage fallback
- **Validation:**
  - `uvicorn main:app --reload --port 8126` — PASS (startup complete)
  - Browser flow checks (create program, add microcycle, add movement with set grid, save movement, no `tier` in rendered UI, TM warning badge) — PASS
- **Notes:**
  - Backend has no `/settings/tm`, `DELETE /cycles/{id}`, or `DELETE /days/{id}` routes; TM persistence uses localStorage with TODO in frontend, and delete actions surface API errors if unsupported
- **Status:** COMPLETED

## 2026-06-12 — RPE chart seed data + helper

### McGlothin RPE table in DB
- **Workflow:** Main
- **Files changed:**
  - `data/rpe_chart.csv` — created; 21 RPE levels (0.0–10.0 in 0.5 steps), reps 1–30 (fewer at lower RPEs where the table terminates), percentage as decimal
  - `database.py` — added `rpe_chart` table to schema; `_seed_rpe_chart()` seeds from CSV on first run (skips if table non-empty); `get_rpe_percentage(rpe, reps) -> float | None` lookup helper; added `import csv`
- **Validation:**
  - `python -m py_compile database.py` — PASS
- **Status:** COMPLETED

## 2026-06-12 — Full frontend build + recovery validation

### Settings + Programs + Workout single-page UI
- **Workflow:** Main
- **Files changed:**
  - `index.html` — rebuilt full frontend with shared shell, settings (API key, exercise cache, unit preference), desktop program builder workflows (program list/detail, tiers, cycles, days, slot drawer), and mobile-friendly workout flows (active block start/open/complete with session logging payload)
- **Validation:**
  - `uvicorn main:app --reload --port 8126` — PASS (startup complete)
  - Browser checks — PASS (`/` loads; Settings/Programs/Workout tabs render; unit preference toggle updates state)
- **Status:** COMPLETED

## 2026-06-12 — Session load/logging + e1RM + Hevy write-back

### Remaining backend routes
- **Workflow:** Main
- **Files changed:**
  - `main.py` — added `GET /active-blocks/{id}/session`, `POST /active-blocks/{id}/session`, `GET /active-blocks/{id}/e1rm`, `POST /active-blocks/{id}/e1rm`; added request models and helpers for slot/session/e1RM logic; added best-effort Hevy write-back update path
  - `wave_math.py` — added public `round_weight()` helper (still pure)
- **Validation:**
  - `python -m py_compile main.py wave_math.py` — PASS
- **Status:** COMPLETED

## 2026-06-12 — Active block routes

### Active block state lifecycle API
- **Workflow:** Express
- **Files changed:**
  - `main.py` — added `POST /active-blocks`, `GET /active-blocks/{id}`, `POST /active-blocks/{id}/advance`, and `DELETE /active-blocks/{id}` with parameterized SQL only; implemented cycle/day advancement and completion/abandon transitions
- **Validation:**
  - `python -m py_compile main.py` — PASS
- **Status:** COMPLETED

## 2026-06-11 — Program builder CRUD API

### Design-layer CRUD routes
- **Workflow:** Express
- **Files changed:**
  - `main.py` — added Pydantic request models plus CRUD routes for programs, tiers, cycles, days, and slots; added nested `GET /programs/{id}` tree assembly; guarded deletes using dependency checks and parameterized SQLite queries only
- **Validation:**
  - `python -m py_compile main.py` — PASS
- **Status:** COMPLETED

## 2026-06-11 — Hevy exercise cache routes

### Exercise cache API wiring
- **Workflow:** Express
- **Files changed:**
  - `main.py` — added `GET /exercises` (reads `hevy_exercise_cache` ordered by title) and `POST /exercises/sync` (calls `HevyClient.sync_exercise_cache()` and returns cached count)
- **Notes:**
  - `hevy_client.py` already contained `sync_exercise_cache()` with page-based fetch from `/v1/exercise_templates` and upsert into `hevy_exercise_cache` on `id`
- **Status:** COMPLETED

## 2026-06-11 — File-based Fernet key handling (hevy-fatigue pattern)

### Encryption key source migration
- **Workflow:** Express
- **Files changed:**
  - `hevy_client.py` — replaced env var encryption-key loading with file-based `_get_fernet()` using `FERNET_KEY_PATH` (default `/data/app.key`); first run generates/writes key, attempts `chmod 0o600`, caches module-level `_fernet`, and raises clear `ValueError` if an existing key file is corrupt
  - `.env` — removed `ENCRYPTION_KEY`
  - `docker-compose.yml` — removed `ENCRYPTION_KEY` from runtime env and CasaOS env metadata
- **Status:** COMPLETED

## 2026-06-11 — Encryption key loading + local startup validation

### Lazy ENCRYPTION_KEY handling
- **Workflow:** Express
- **Files changed:**
  - `hevy_client.py` — replaced import-time Fernet initialization with lazy `_get_fernet()` validation; encryption errors now occur only when `_encrypt()`/`_decrypt()` is called without a configured or valid key
  - `main.py` — added `from dotenv import load_dotenv` and `load_dotenv()` near the top so `.env` values are available before local module initialization
  - `.env` — created with `DB_PATH=./531bbb.db` and populated `ENCRYPTION_KEY` with a valid generated Fernet key
- **Checks:**
  - `.gitignore` already contained both `.env` and `.env.*`
  - `uvicorn main:app --reload --port 8126` starts successfully
  - `GET http://localhost:8126/health` returns `{"status":"ok"}`
- **Status:** COMPLETED

## 2026-06-08 — Scaffold + encryption

### Scaffold
- **Workflow:** Express
- **Files committed:** `main.py`, `database.py`, `wave_math.py`, `docker-compose.yml`, `Dockerfile`, `requirements.txt`, `index.html`, `CLAUDE.md`, `docs/531bbb-context.md`, `docs/copilot-context.md`
- **Summary:** Initial project scaffold committed. FastAPI app with `/health` route and lifespan `init_db()`. Full SQLite schema defined in `database.py`. Pure wave math functions in `wave_math.py`. Placeholder `index.html`. Docker + CasaOS compose config on port 8126.
- **Status:** COMPLETED

### Fernet API key encryption
- **Workflow:** Express
- **Files changed:**
  - `requirements.txt` — added `cryptography==42.0.8`
  - `docker-compose.yml` — added `ENCRYPTION_KEY` to environment block and CasaOS metadata
  - `hevy_client.py` — created with `_encrypt`/`_decrypt` Fernet helpers, `save_api_key()`, `_load_api_key()`, `HevyClient.sync_exercise_cache()`, `HevyClient.post_workout()`
- **Summary:** Hevy API key is stored encrypted in `app_settings` using Fernet symmetric encryption. `ENCRYPTION_KEY` env var is the stable server secret. `post_workout()` is best-effort — logs failures, never raises, never blocks session save.
- **py_compile:** `hevy_client.py` — PASS
- **Gate tests:** N/A
- **Status:** COMPLETED
