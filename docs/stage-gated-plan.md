# Stage-Gated Plan

## Completed

### 2026-06-12 - Session set rpe_percentage field
- Scope: Added set-level rpe_percentage in GET /active-blocks/{id}/session using get_rpe_percentage(target_rpe, reps).
- Gates:
1. python -m py_compile main.py: PASS
2. uvicorn main:app --reload --port 8126 startup: PASS
3. GET /active-blocks/{id}/session returns sets[*].rpe_percentage as float or null: PASS
- Notes:
1. PRAGMA table_info verified for rpe_chart before implementing lookup usage.

### 2026-06-12 - Session route fix for TM/week/set flags/BBB
- Scope: Fixed GET /active-blocks/{id}/session to use tm_{slot_id}, explicit week_number semantics, derived set flags, and BBB weight output.
- Gates:
1. python -m py_compile main.py: PASS
2. uvicorn main:app --reload --port 8126 startup: PASS
3. GET /active-blocks/{id}/session with active block + TM set returns non-null first_set_weight_kg: PASS
4. Session slot payload includes is_amrap, jokers_enabled, sets, and bbb_weight_kg: PASS
5. python -m py_compile main.py (final): PASS
- Notes:
1. PRAGMA table_info verified for active_blocks, blocks, days, tiers, exercise_slots, e1rm_log, and app_settings before edits.

### 2026-06-12 - TM API wiring in Programs UI
- Scope: Replaced TM localStorage access in index.html with backend TM endpoints and updated nav order to Workout, Program, Settings.
- Gates:
1. Day view slot with no TM shows amber Set TM badge: PASS
2. Enter TM and blur saves value and shows WM dual-unit format: PASS
3. Reload page retains TM via backend fetch: PASS
4. localStorage search confirms no TM-related key usage remains in index.html: PASS

### 2026-06-12 - TM + delete endpoint backend work
- Scope: Added training-max settings endpoints and microcycle/day delete endpoints in main.py with guard rails and ordered deletes.
- Gates:
1. python -m py_compile main.py: PASS
2. uvicorn main:app --reload --port 8126 startup: PASS
3. POST /settings/tm with slot_id=1, value_kg=140.0: PASS
4. GET /settings/tm/1: PASS
5. GET /settings/tm/9999 returns 404: PASS
6. DELETE /days/{id} when only day in cycle returns 400 with expected detail: PASS
- Notes:
1. Column usage was verified with PRAGMA table_info for app_settings, blocks, days, and exercise_slots before implementing new SQL.

### 2026-06-12 - Programs tab UX rewrite
- Scope: Rebuilt Programs tab in index.html to a three-screen flow (list -> program -> day) with mobile-first layout.
- Gates:
1. Server startup on port 8126: PASS
2. Create program and open detail immediately: PASS
3. Add microcycle and auto-navigate to Day 1: PASS
4. Add movement with exercise search and immediate set grid: PASS
5. Save movement and render in day list: PASS
6. Ensure rendered UI does not contain the word "tier": PASS
7. Unsaved movement TM warning badge (Set TM, amber class): PASS
- Notes:
1. TM persistence is localStorage fallback keyed by slot id with TODO for backend endpoint.
2. Delete cycle/day UI is implemented with confirmation and API calls; backend delete routes are currently missing.
