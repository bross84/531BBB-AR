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
