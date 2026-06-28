# 531 BBB-AR — Project Context

Source of truth for architecture, schema, wave math rules, and constraints.  
Read this file at the start of every task. Do not proceed if it is missing.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI |
| Database | SQLite at `/data/531bbb.db` inside Docker — `sqlite3` stdlib, no ORM |
| Frontend | Vanilla JS, single `index.html` — all HTML, CSS, JS in one file, no bundler |
| HTTP client | `httpx` (async) for Hevy API calls |
| Deployment | Docker + docker-compose on CasaOS homelab |
| Port | 8126 (8125 reserved by sibling service `hevy-fatigue`) |
| PWA | Used as desktop PWA and mobile PWA |

**Allowed frontend libraries:** Chart.js only. No frameworks, no build step.

---

## Key files

| File | Purpose |
|---|---|
| `main.py` | FastAPI app entry point, all API route definitions |
| `database.py` | `init_db()`, schema DDL, `get_db()` helper |
| `wave_math.py` | Pure functions — e1RM, Joker filter, weight rounding, BBB weight |
| `hevy_client.py` | Hevy API HTTP client — exercise cache sync, workout write-back |
| `index.html` | Entire frontend |
| `docker-compose.yml` | Deployment — contains CasaOS metadata, **do not alter** |
| `requirements.txt` | Must stay in sync with all imports in `.py` files |

---

## Program model

Programs are program-agnostic. Tiers, wave structure, sets, reps, and percentages are all user-defined per program. There are no hardcoded tier names.

### Tiers

Each program defines its own tiers. A tier has a name (user-defined), a behaviour, and a display order. Four behaviours are supported:

| Behaviour | Description |
|---|---|
| `percentage` | Weight = training max or e1RM × percentage from `wave_params` |
| `fixed` | User sets the weight — app tracks it but does not compute it |
| `progression` | Fixed weight that auto-increments by a configured amount when rep target is hit |
| `free` | No prescribed weight or sets — free log only |

### Wave structure

Wave structure is defined per exercise slot via `wave_params` JSON. There is no assumed number of microcycles or days. Microcycles are numbered and user-labeled — they are not calendar weeks.

### RPE

All programs derive percentages from RPE. Each exercise slot stores a `target_rpe`. Session log stores both `target_rpe` and `actual_rpe` so drift between intended and actual can be tracked over time. The RPE → percentage lookup table lives in `app_settings`.

### Microcycles

Training cycles are called microcycles, not weeks. They have no fixed length in days. The label is freeform — "Micro 1", "Wave 1", etc.

---

## Wave math rules (`wave_math.py`)

All functions in `wave_math.py` are **pure**: no DB access, no HTTP calls, no side effects. This is a hard invariant.

### Constants

```python
JOKER_BAND = 0.05   # ±5% band for Joker qualification
ROUND_TO_KG = 2.5   # all displayed/stored weights rounded to nearest 2.5 kg
```

### Epley formula

```python
def epley(weight_kg: float, reps: int) -> float:
    if reps == 1:
        return weight_kg
    return weight_kg * (1 + reps / 30)
```

Used to compute e1RM from any (weight, reps) pair.

### Joker qualification

```python
def joker_qualifies(joker_e1rm: float, amrap_e1rm: float) -> bool:
    return abs(joker_e1rm - amrap_e1rm) / amrap_e1rm <= JOKER_BAND
```

Joker sets with **no RPE logged** are excluded before this function is called — the caller is responsible for filtering them out.

### Session e1RM

```python
def session_e1rm(amrap_e1rm: float, joker_sets: list[tuple[float, float]]) -> float:
```

- `joker_sets` — list of `(weight_kg, reps)` for RPE-logged Jokers only.
- Jokers outside ±5% band are silently excluded.
- Result is the mean of the AMRAP e1RM and all qualifying Joker e1RMs.
- This value is written to `e1rm_log` with `source = 'amrap'` (AMRAP only) or `source = 'joker_avg'` (averaged with Jokers).

### Working weight (Main sets)

```python
def working_weight(training_max_kg: float, week_number: int, wave_params: dict) -> float:
    pct = wave_params["percentages"][week_number - 1]
    return _round_weight(training_max_kg * pct)
```

`wave_params["percentages"]` is a 3-element list indexed by `week_number - 1`.

### BBB weight

```python
def bbb_weight(e1rm_kg: float, week_number: int, wave_params: dict) -> float:
    pct = wave_params["bbb_percentages"][week_number - 1]
    return _round_weight(e1rm_kg * pct)
```

`wave_params["bbb_percentages"]` is a 3-element list: `[0.65, 0.70, 0.75]` by default.

### Rounding

All weights — planned and actual — must be rounded to the nearest 2.5 kg before display or storage. Use `_round_weight()`. Never store or display unrounded floats.

---

## Database schema

Foreign keys are enforced (`PRAGMA foreign_keys = ON` in `get_db()`).

### Design layer (program authoring)

```
programs
  id INTEGER PK
  name TEXT NOT NULL
  total_weeks INTEGER NOT NULL
  notes TEXT
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP

tiers
  id INTEGER PK
  program_id INTEGER FK → programs.id
  name TEXT NOT NULL
  behaviour TEXT NOT NULL  CHECK IN ('percentage','fixed','progression','free')
  display_order INTEGER NOT NULL DEFAULT 0

blocks
  id INTEGER PK
  program_id INTEGER FK → programs.id
  cycle_number INTEGER NOT NULL
  label TEXT

days
  id INTEGER PK
  block_id INTEGER FK → blocks.id
  day_number INTEGER NOT NULL
  label TEXT

exercise_slots
  id INTEGER PK
  day_id INTEGER FK → days.id
  tier_id INTEGER FK → tiers.id
  hevy_exercise_id TEXT NOT NULL
  hevy_exercise_name TEXT NOT NULL
  slot_order INTEGER NOT NULL DEFAULT 0
  wave_params TEXT  -- JSON: {"percentages": [...], "bbb_percentages": [...]}
  target_rpe REAL
```

### Live training layer

```
active_blocks
  id INTEGER PK
  program_id INTEGER FK → programs.id
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP
  current_cycle INTEGER NOT NULL DEFAULT 1
  current_day INTEGER NOT NULL DEFAULT 1
  status TEXT NOT NULL DEFAULT 'active'  CHECK IN ('active','completed','abandoned')

session_log
  id INTEGER PK
  active_block_id INTEGER FK → active_blocks.id
  exercise_slot_id INTEGER FK → exercise_slots.id
  week_number INTEGER NOT NULL
  day_number INTEGER NOT NULL
  set_number INTEGER NOT NULL
  set_type TEXT NOT NULL
  planned_weight_kg REAL   -- rounded to 2.5 kg
  actual_weight_kg REAL    -- rounded to 2.5 kg
  reps INTEGER
  target_rpe REAL
  actual_rpe REAL
  hevy_workout_id TEXT
  logged_at DATETIME DEFAULT CURRENT_TIMESTAMP

e1rm_log
  id INTEGER PK
  active_block_id INTEGER FK → active_blocks.id
  exercise_slot_id INTEGER FK → exercise_slots.id
  e1rm_kg REAL NOT NULL
  source TEXT NOT NULL  CHECK IN ('amrap','joker_avg','manual')
  logged_at DATETIME DEFAULT CURRENT_TIMESTAMP
```

### Support tables

```
hevy_exercise_cache
  id TEXT PK              -- Hevy exerciseTemplateId
  title TEXT NOT NULL
  primary_muscle TEXT
  cached_at DATETIME DEFAULT CURRENT_TIMESTAMP

app_settings
  key TEXT PK
  value TEXT NOT NULL     -- Hevy API key stored here, never hardcoded
```

---

## Hevy integration

### Exercise cache

- Pulled from `GET /v1/exercise_templates` at setup.
- Stored in `hevy_exercise_cache`. Refreshable via `POST /exercises/sync`.
- `hevy_exercise_cache.id` is the `exerciseTemplateId` used in write-back payloads.

### Workout write-back

- Triggered after a session is submitted.
- Endpoint: `POST /v1/workouts` on the Hevy API.
- Payload uses `exerciseTemplateId` from `hevy_exercise_cache`.
- **Failures must be logged and must not raise or block the session save.** The session is always written to `session_log` first; Hevy write-back is best-effort.
- The resulting `hevy_workout_id` is stored back to `session_log.hevy_workout_id` on success.

### API key

Stored in `app_settings` table under a known key. Never hardcoded, never committed.

---

## Hard constraints

| Constraint | Rule |
|---|---|
| DB path | Read from `os.environ["DB_PATH"]`. Never hardcode. |
| DB library | `sqlite3` stdlib only. No SQLAlchemy, no Alembic. |
| SQL safety | Parameterised queries only. No f-string SQL. |
| Weights | Always rounded to nearest 2.5 kg before display or storage. |
| `wave_math.py` | Pure functions only — no DB, no HTTP, no side effects. |
| Frontend libraries | Chart.js only. No bundler, no build step. |
| Frontend structure | All HTML/CSS/JS stays in `index.html`. Do not split. |
| `docker-compose.yml` | Do not alter CasaOS metadata. |
| Hevy write-back | Log failures; never raise or block session save. |
| Schema changes | Always verify columns with `PRAGMA table_info`. Never assume. |
| Deletions | No permanent deletions without explicit written instruction. |
| Commits | Brian commits after review. Implementer does not `git commit` or `git push`. |

---

## Architecture conventions

- FastAPI route handlers stay thin — business logic goes in service modules.
- Pydantic models for all request/response shapes.
- Environment config via `.env` / `python-dotenv`.
- Docker-aware: the app runs in a container; `/data/` is a volume mount.

---

## Development workflow

**Claude** (architect / spec writer) → **Copilot** (implementer, reads `docs/copilot-context.md`) → **Brian** (reviewer / committer)

Implementer agent instructions live in [`docs/copilot-context.md`](copilot-context.md).

---

## Local Docker (Windows)

Tested on Windows with Docker Desktop. Uses a named volume — no bind-mount path issues.

**Build and run:**
```
docker compose up --build -d
```

**Stop:**
```
docker compose stop
```

**Start after stop:**
```
docker compose start
```

**Tear down (removes containers and volume — destroys DB):**
```
docker compose down -v
```

**View logs:**
```
docker logs 531bbb -f
```

**Health check:**
```
curl http://localhost:8126/health
```

The SQLite DB is stored in the named volume `531bbb-ar_531bbb-data` at `/data/531bbb.db` inside the container. The Fernet key is at `/data/app.key`. Both persist across `stop`/`start` cycles. Only `down -v` wipes them.
