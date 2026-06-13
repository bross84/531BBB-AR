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
