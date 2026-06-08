# 531 BBB-AR

A personal training planner and workout logger built around Jim Wendler's 5/3/1 BBB programme with autoregulation. Syncs completed sessions to [Hevy](https://hevyapp.com) via the Hevy API.

Deployed via Docker on CasaOS, used as a desktop PWA and mobile PWA.

---

## What it does

- **Program designer** — author multi-week training blocks ahead of time (Main / BBB / Accessory tier model, 3-week wave, 8-week block minimum, 4 days per week)
- **Autoregulated weights** — working weights computed at session time from a live e1RM, anchored by AMRAP sets and averaged Joker sets within a ±5% band
- **BBB volume** — starting weight derived from averaged e1RM × 65/70/75% by wave week; freely overridable per session
- **Hevy write-back** — completed sessions posted to Hevy via `POST /v1/workouts` using `exerciseTemplateId`
- **Exercise cache** — Hevy exercise list pulled and cached at setup, used throughout for slot configuration and write-back

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI |
| Database | SQLite at `/data/531bbb.db` inside Docker |
| DB access | `sqlite3` stdlib — no ORM |
| Frontend | Vanilla JS, single-file `index.html`, no bundler |
| Deployment | Docker + docker-compose, CasaOS |

---

## Programme model

### Three tiers

| Tier | Description |
|---|---|
| **Main** | Primary lift. Percentage-based sets from training max. Top set is AMRAP. Optional Joker sets. |
| **BBB** | Same or complementary lift. 5×10 at 65/70/75% of averaged e1RM by week. Freely adjustable. |
| **Accessory** | Free-log only. No prescribed weight or sets. |

### e1RM rules

- **AMRAP sets** — anchor the e1RM after every top set using the Epley formula
- **Joker sets** — averaged and included only if within ±5% of the current AMRAP-anchored e1RM
- **RPE-less Jokers** — excluded from e1RM calculation entirely

### Wave structure

| Week | Main % | BBB % |
|---|---|---|
| 1 | 75% | 65% |
| 2 | 80% | 70% |
| 3 | 85% (+ AMRAP) | 75% |

3-week wave repeats. Minimum 8-week block (approx. 3 full waves). New e1RM from each AMRAP anchors the following week's working weights automatically.

---

## Database schema (overview)

```
programs → blocks → days → exercise_slots   (template / design layer)
programs → active_blocks                    (live training layer)
active_blocks → session_log                 (set-by-set log)
active_blocks → e1rm_log                    (autoregulation history)
hevy_exercise_cache                         (pulled from Hevy at setup)
```

Full schema in [`docs/schema.md`](docs/schema.md).

---

## Key files

| File | Purpose |
|---|---|
| `main.py` | FastAPI app, all API routes |
| `database.py` | Schema definitions, `init_db()`, migrations |
| `wave_math.py` | e1RM calculation, Joker band filter, BBB weight logic |
| `hevy_client.py` | Hevy API HTTP client — exercise cache pull, workout write-back |
| `index.html` | Entire frontend — HTML, CSS, JS in one file |
| `docker-compose.yml` | Deployment config — contains CasaOS metadata, do not alter |
| `requirements.txt` | Must stay in sync with all imports in `.py` files |

---

## Hevy integration

- **Exercise list** — `GET /v1/exercise_templates` pulled at setup, stored in `hevy_exercise_cache`, refreshable via `POST /exercises/sync`
- **Workout write-back** — `POST /v1/workouts` fired after session log is submitted; uses `exerciseTemplateId` from cache
- **API key** — stored in `app_settings` table, never hardcoded or committed

---

## Hard constraints

| Constraint | Rule |
|---|---|
| DB access | `sqlite3` stdlib only. No SQLAlchemy, no Alembic. |
| Frontend libraries | Chart.js only. No bundler, no build step. |
| Frontend structure | `index.html` holds all HTML, CSS, JS. Do not split. |
| DB path | Read from `os.environ` as `DB_PATH`. Never hardcode. |
| Docker | Do not alter CasaOS metadata in `docker-compose.yml`. |
| Commits | No `git commit` or `git push`. Brian commits after review. |
| Deletions | No permanent deletions without explicit written instruction. |
| Column names | Always verify with `PRAGMA table_info`. Never assume. |

---

## Development model

**Claude** (architect / reviewer) → **Copilot** (implementer) → **Brian** (reviewer / committer)

This context file and [`docs/copilot-context.md`](docs/copilot-context.md) are read by the Copilot agent at the start of every task.

---

## Deployment

```bash
docker compose up -d
```

App runs on port **8126** (8125 is reserved by hevy-fatigue on the same host).

Database persists at `/data/531bbb.db` via Docker volume.

---

## License

MIT
