import json
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

from database import get_db, get_rpe_percentage, init_db
import hevy_client
import program_parser
from wave_math import bbb_weight, epley, joker_qualifies, joker_weight, round_weight, session_e1rm, working_weight

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="531 BBB-AR", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse("index.html")


# ── Settings ───────────────────────────────────────────────────────────────────

class ApiKeyInput(BaseModel):
    api_key: str


class SlotTrainingMaxInput(BaseModel):
    slot_id: int = Field(ge=1)
    value_kg: float = Field(gt=0)


class SlotWmPctInput(BaseModel):
    slot_id: int = Field(ge=1)
    value: float = Field(ge=50, le=100)


class ProgramInput(BaseModel):
    name: str
    total_weeks: int = Field(ge=1)
    notes: str | None = None


class TierInput(BaseModel):
    name: str
    behaviour: Literal["percentage", "fixed", "progression", "free"]
    display_order: int = 0


class CycleInput(BaseModel):
    cycle_number: int = Field(ge=1)
    label: str | None = None


class DayInput(BaseModel):
    day_number: int = Field(ge=1)
    label: str | None = None


class SlotInput(BaseModel):
    tier_id: int
    hevy_exercise_id: str
    hevy_exercise_name: str
    slot_order: int = 0
    wave_params: dict[str, Any] | None = None
    target_rpe: float | None = None
    source_params: dict[str, Any] | None = None


class ParseProgramInput(BaseModel):
    text: str


class ActiveBlockStartInput(BaseModel):
    program_id: int


class SessionSetInput(BaseModel):
    slot_id: int
    set_number: int = Field(ge=1)
    set_type: str
    actual_weight_kg: float | None = None
    reps: int | None = None
    target_rpe: float | None = None
    actual_rpe: float | None = None


class SessionLogInput(BaseModel):
    sets: list[SessionSetInput]


class ManualE1RMInput(BaseModel):
    slot_id: int
    e1rm_kg: float = Field(gt=0)


def _fetch_one_or_404(conn, query: str, params: tuple[Any, ...], detail: str) -> dict[str, Any]:
    row = conn.execute(query, params).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=detail)
    return dict(row)


def _parse_wave_params(raw_value: str | None) -> dict[str, Any] | None:
    if raw_value is None:
        return None
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return None


def _serialize_wave_params(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value)


def _slot_response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "day_id": row["day_id"],
        "tier_id": row["tier_id"],
        "hevy_exercise_id": row["hevy_exercise_id"],
        "hevy_exercise_name": row["hevy_exercise_name"],
        "slot_order": row["slot_order"],
        "wave_params": _parse_wave_params(row["wave_params"]),
        "target_rpe": row["target_rpe"],
        "source_params": _parse_wave_params(row.get("source_params")),
    }


def _fetch_program_tree(program_id: int) -> dict[str, Any]:
    with get_db() as conn:
        program = _fetch_one_or_404(
            conn,
            """
            SELECT id, name, total_weeks, notes, created_at
            FROM programs
            WHERE id = ?
            """,
            (program_id,),
            "Program not found.",
        )
        tiers = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, program_id, name, behaviour, display_order
                FROM tiers
                WHERE program_id = ?
                ORDER BY display_order ASC, id ASC
                """,
                (program_id,),
            ).fetchall()
        ]

        # Top-level blocks (new schema level)
        block_rows = conn.execute(
            """
            SELECT id, program_id, block_number, label
            FROM blocks
            WHERE program_id = ?
            ORDER BY block_number ASC, id ASC
            """,
            (program_id,),
        ).fetchall()
        blocks: list[dict[str, Any]] = [
            {**dict(row), "microcycles": []}
            for row in block_rows
        ]
        block_map = {blk["id"]: blk for blk in blocks}

        # Microcycles — may be linked to a block (block_id) or unlinked (legacy)
        mc_rows = conn.execute(
            """
            SELECT id, program_id, block_id, cycle_number, label
            FROM microcycles
            WHERE program_id = ?
            ORDER BY cycle_number ASC, id ASC
            """,
            (program_id,),
        ).fetchall()
        orphan_microcycles: list[dict[str, Any]] = []
        mc_map: dict[int, dict[str, Any]] = {}
        for row in mc_rows:
            mc = {**dict(row), "days": []}
            mc_map[mc["id"]] = mc
            parent_block = block_map.get(mc["block_id"]) if mc["block_id"] is not None else None
            if parent_block is not None:
                parent_block["microcycles"].append(mc)
            else:
                orphan_microcycles.append(mc)

        # Days — block_id here references microcycles.id
        day_rows = conn.execute(
            """
            SELECT id, block_id, day_number, label
            FROM days
            WHERE block_id IN (
                SELECT id FROM microcycles WHERE program_id = ?
            )
            ORDER BY day_number ASC, id ASC
            """,
            (program_id,),
        ).fetchall()
        day_map: dict[int, dict[str, Any]] = {}
        for row in day_rows:
            day = {**dict(row), "slots": []}
            day_map[day["id"]] = day
            mc_map[day["block_id"]]["days"].append(day)

        slot_rows = conn.execute(
            """
            SELECT id, day_id, tier_id, hevy_exercise_id, hevy_exercise_name,
                   slot_order, wave_params, target_rpe, source_params
            FROM exercise_slots
            WHERE day_id IN (
                SELECT d.id
                FROM days d
                JOIN microcycles b ON b.id = d.block_id
                WHERE b.program_id = ?
            )
            ORDER BY slot_order ASC, id ASC
            """,
            (program_id,),
        ).fetchall()
        for row in slot_rows:
            slot = _slot_response(dict(row))
            day_map[slot["day_id"]]["slots"].append(slot)

    result: dict[str, Any] = {
        **program,
        "tiers": tiers,
        "blocks": blocks,
    }
    if orphan_microcycles:
        # Legacy microcycles with no parent block — surface them separately
        result["microcycles"] = orphan_microcycles
    return result


def _ensure_program_exists(conn, program_id: int) -> None:
    row = conn.execute("SELECT 1 FROM programs WHERE id = ?", (program_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Program not found.")


def _ensure_block_exists(conn, block_id: int) -> None:
    row = conn.execute("SELECT 1 FROM microcycles WHERE id = ?", (block_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Cycle not found.")


def _ensure_day_exists(conn, day_id: int) -> None:
    row = conn.execute("SELECT 1 FROM days WHERE id = ?", (day_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Day not found.")


def _ensure_tier_exists(conn, tier_id: int) -> dict[str, Any]:
    return _fetch_one_or_404(
        conn,
        "SELECT id, program_id, name, behaviour, display_order FROM tiers WHERE id = ?",
        (tier_id,),
        "Tier not found.",
    )


def _ensure_slot_exists(conn, slot_id: int) -> dict[str, Any]:
    return _fetch_one_or_404(
        conn,
        """
        SELECT id, day_id, tier_id, hevy_exercise_id, hevy_exercise_name,
               slot_order, wave_params, target_rpe, source_params
        FROM exercise_slots
        WHERE id = ?
        """,
        (slot_id,),
        "Slot not found.",
    )


def _day_program_id(conn, day_id: int) -> int:
    row = conn.execute(
        """
        SELECT b.program_id
        FROM days d
        JOIN microcycles b ON b.id = d.block_id
        WHERE d.id = ?
        """,
        (day_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Day not found.")
    return row["program_id"]


def _validate_slot_program_match(conn, day_id: int, tier_id: int) -> None:
    tier = _ensure_tier_exists(conn, tier_id)
    day_program_id = _day_program_id(conn, day_id)
    if tier["program_id"] != day_program_id:
        raise HTTPException(
            status_code=400,
            detail="Slot tier must belong to the same program as the target day.",
        )


def _active_block_state_or_404(conn, active_block_id: int) -> dict[str, Any]:
    return _fetch_one_or_404(
        conn,
        """
        SELECT id, program_id, current_cycle, current_day, status, started_at
        FROM active_blocks
        WHERE id = ?
        """,
        (active_block_id,),
        "Active block not found.",
    )


def _setting_float_or_none(conn, key: str) -> float | None:
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return None
    raw = (row["value"] or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _wave_param_number(wave_params: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = wave_params.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _wave_param_int(wave_params: dict[str, Any], key: str) -> int | None:
    value = wave_params.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _slot_in_program(conn, slot_id: int, program_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT s.id, s.hevy_exercise_id, s.hevy_exercise_name
        FROM exercise_slots s
        JOIN days d ON d.id = s.day_id
        JOIN microcycles b ON b.id = d.block_id
        WHERE s.id = ? AND b.program_id = ?
        """,
        (slot_id, program_id),
    ).fetchone()
    return dict(row) if row is not None else None


def _load_api_key(conn) -> str | None:
    """Read and decrypt the Hevy API key using the existing DB connection."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'hevy_api_key'"
    ).fetchone()
    if row is None:
        return None
    try:
        return hevy_client._decrypt(row["value"])
    except Exception:
        return None


def _resolve_e1rm(conn, hevy_exercise_id: str) -> float | None:
    """
    Return the best known e1RM for the given Hevy exercise ID.

    Lookup order:
    1. Most recent entry in e1rm_log (any active block) joined via exercise_slots.
    2. Hevy workout history via HevyClient — skipped if no API key is stored.

    Does not write to e1rm_log: the schema CHECK constraint only allows
    ('amrap','joker_avg','manual') and the function lacks the active_block_id /
    exercise_slot_id FKs required for a row insert.
    """
    row = conn.execute(
        """
        SELECT el.e1rm_kg
        FROM e1rm_log el
        JOIN exercise_slots es ON es.id = el.exercise_slot_id
        WHERE es.hevy_exercise_id = ?
        ORDER BY el.logged_at DESC, el.id DESC
        LIMIT 1
        """,
        (hevy_exercise_id,),
    ).fetchone()
    if row is not None:
        return float(row["e1rm_kg"])

    api_key = _load_api_key(conn)
    if not api_key:
        return None
    return hevy_client.HevyClient(api_key).best_e1rm_from_hevy(hevy_exercise_id)


def _session_slots_for_active_block(conn, state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT s.id AS slot_id,
                   t.name AS tier_name,
                   t.behaviour AS tier_behaviour,
                   s.hevy_exercise_id,
                   s.hevy_exercise_name AS exercise_name,
                   s.wave_params,
                   s.target_rpe,
                   s.source_params,
                   s.slot_order
            FROM exercise_slots s
            JOIN tiers t ON t.id = s.tier_id
            JOIN days d ON d.id = s.day_id
            JOIN microcycles b ON b.id = d.block_id
            WHERE b.program_id = ?
              AND b.cycle_number = ?
              AND d.day_number = ?
            ORDER BY s.slot_order ASC, s.id ASC
            """,
            (state["program_id"], state["current_cycle"], state["current_day"]),
        ).fetchall()
    ]


@app.get("/settings")
def get_settings():
    """Return whether the Hevy API key is configured. Never returns the key itself."""
    key = hevy_client.get_api_key()
    if key and len(key) >= 4:
        preview = "···" + key[-4:]
    elif key:
        preview = "···"
    else:
        preview = None
    return {"hevy_api_key_set": bool(key), "hevy_api_key_preview": preview}


@app.post("/settings/api-key", status_code=204)
def save_api_key(data: ApiKeyInput):
    """Encrypt and store the Hevy API key. Returns 204 on success."""
    key = data.api_key.strip()
    if not key:
        raise HTTPException(status_code=422, detail="API key cannot be empty.")
    hevy_client.save_api_key(key)


@app.post("/settings/tm")
def save_training_max_setting(data: SlotTrainingMaxInput):
    setting_key = f"tm_{data.slot_id}"
    setting_value = str(data.value_kg)
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO app_settings (key, value)
            VALUES (?, ?)
            """,
            (setting_key, setting_value),
        )
    return {"slot_id": data.slot_id, "value_kg": data.value_kg}


@app.post("/settings/wm-pct")
def save_wm_pct_setting(data: SlotWmPctInput):
    setting_key = f"wm_pct_{data.slot_id}"
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (setting_key, str(data.value)),
        )
    return {"slot_id": data.slot_id, "value": data.value}


@app.get("/settings/wm-pct/{slot_id}")
def get_wm_pct_setting(slot_id: int):
    setting_key = f"wm_pct_{slot_id}"
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (setting_key,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="WM% not set.")
    try:
        value = float(row["value"])
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=500, detail="Stored WM% is invalid.") from error
    return {"slot_id": slot_id, "value": value}


@app.get("/settings/tm/{slot_id}")
def get_training_max_setting(slot_id: int):
    setting_key = f"tm_{slot_id}"
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (setting_key,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Training max not set.")
    raw_value = row["value"]
    try:
        value_kg = float(raw_value)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=500, detail="Stored training max is invalid.") from error
    return {"slot_id": slot_id, "value_kg": value_kg}


@app.post("/programs/parse")
def parse_program_text(data: ParseProgramInput):
    return program_parser.parse_program(data.text)


# ── Programs ───────────────────────────────────────────────────────────────────

@app.post("/programs/{program_id}/import")
def import_program(program_id: int, data: ParseProgramInput):
    parsed = program_parser.parse_program(data.text)
    if parsed["errors"]:
        raise HTTPException(status_code=422, detail=parsed["errors"])

    parsed_blocks = parsed["blocks"]
    import_errors: list[dict[str, Any]] = []
    block_count = 0
    mc_count = 0
    day_count = 0
    slot_count = 0

    with get_db() as conn:
        _ensure_program_exists(conn, program_id)

        # Block reimport if there is an active block for this program.
        active_block = conn.execute(
            "SELECT id FROM active_blocks WHERE program_id = ? AND status = 'active' LIMIT 1",
            (program_id,),
        ).fetchone()
        if active_block:
            raise HTTPException(
                status_code=400,
                detail="Cannot reimport a program with an active block — abandon the active block first.",
            )

        # Wipe existing program data in FK-safe order before reinserting.
        conn.execute(
            """
            DELETE FROM exercise_slots
            WHERE day_id IN (
                SELECT id FROM days
                WHERE block_id IN (
                    SELECT id FROM microcycles
                    WHERE block_id IN (
                        SELECT id FROM blocks WHERE program_id = ?
                    )
                )
            )
            """,
            (program_id,),
        )
        conn.execute(
            """
            DELETE FROM days
            WHERE block_id IN (
                SELECT id FROM microcycles
                WHERE block_id IN (
                    SELECT id FROM blocks WHERE program_id = ?
                )
            )
            """,
            (program_id,),
        )
        conn.execute(
            """
            DELETE FROM microcycles
            WHERE block_id IN (
                SELECT id FROM blocks WHERE program_id = ?
            )
            """,
            (program_id,),
        )
        conn.execute("DELETE FROM blocks WHERE program_id = ?", (program_id,))
        conn.execute("DELETE FROM tiers WHERE program_id = ?", (program_id,))

        cache_rows = conn.execute(
            "SELECT id, title FROM hevy_exercise_cache"
        ).fetchall()
        exercise_lookup: dict[str, str] = {row["title"].lower(): row["id"] for row in cache_rows}

        # Collect all sources so tiers can be found or created before slot inserts.
        all_sources: set[str] = set()
        for blk in parsed_blocks:
            for mc in blk["microcycles"]:
                for day in mc["days"]:
                    for slot in day["slots"]:
                        all_sources.add((slot.get("source_params") or {}).get("source", "free"))

        # Tiers for imported programs use behaviour='free' (compatible with both old and new
        # DB CHECK constraints). source_params on each slot is the real source of truth.
        source_to_tier: dict[str, int] = {}
        for idx, source in enumerate(sorted(all_sources)):
            tier_name = source.upper()
            existing = conn.execute(
                "SELECT id FROM tiers WHERE program_id = ? AND name = ? LIMIT 1",
                (program_id, tier_name),
            ).fetchone()
            if existing:
                source_to_tier[source] = existing["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO tiers (program_id, name, behaviour, display_order) VALUES (?, ?, 'free', ?)",
                    (program_id, tier_name, idx),
                )
                source_to_tier[source] = cur.lastrowid

        for blk in parsed_blocks:
            blk_cur = conn.execute(
                "INSERT INTO blocks (program_id, block_number, label) VALUES (?, ?, ?)",
                (program_id, blk["block_number"], blk.get("label")),
            )
            blk_id = blk_cur.lastrowid
            block_count += 1

            for mc in blk["microcycles"]:
                mc_cur = conn.execute(
                    "INSERT INTO microcycles (program_id, block_id, cycle_number, label) VALUES (?, ?, ?, ?)",
                    (program_id, blk_id, mc["cycle_number"], mc.get("label")),
                )
                mc_id = mc_cur.lastrowid
                mc_count += 1

                for day in mc["days"]:
                    day_cur = conn.execute(
                        "INSERT INTO days (block_id, day_number, label) VALUES (?, ?, ?)",
                        (mc_id, day["day_number"], day.get("label")),
                    )
                    day_id = day_cur.lastrowid
                    day_count += 1

                    for slot in day["slots"]:
                        sp = slot.get("source_params") or {}
                        source = sp.get("source", "free")
                        tier_id = source_to_tier[source]

                        exercise_name = slot["exercise_name"]
                        hevy_exercise_id = exercise_lookup.get(exercise_name.lower(), "")
                        if not hevy_exercise_id:
                            import_errors.append({
                                "exercise": exercise_name,
                                "message": f"Exercise not found in cache: {exercise_name!r}",
                            })

                        conn.execute(
                            """
                            INSERT INTO exercise_slots (
                                day_id, tier_id, hevy_exercise_id, hevy_exercise_name,
                                slot_order, wave_params, target_rpe, source_params
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                day_id,
                                tier_id,
                                hevy_exercise_id,
                                exercise_name,
                                slot["slot_order"],
                                json.dumps({"sets": slot["sets"]}),
                                slot.get("target_rpe"),
                                json.dumps(sp) if sp else None,
                            ),
                        )
                        slot_count += 1

    return {
        "imported": True,
        "blocks": block_count,
        "microcycles": mc_count,
        "days": day_count,
        "slots": slot_count,
        "errors": import_errors,
    }

@app.get("/programs")
def list_programs():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, name, total_weeks, notes, created_at
            FROM programs
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/programs")
def create_program(data: ProgramInput):
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO programs (name, total_weeks, notes)
            VALUES (?, ?, ?)
            """,
            (data.name.strip(), data.total_weeks, data.notes),
        )
        program_id = cursor.lastrowid
        row = conn.execute(
            """
            SELECT id, name, total_weeks, notes, created_at
            FROM programs
            WHERE id = ?
            """,
            (program_id,),
        ).fetchone()
    return dict(row)


@app.get("/programs/{program_id}")
def get_program(program_id: int):
    return _fetch_program_tree(program_id)


@app.put("/programs/{program_id}")
def update_program(program_id: int, data: ProgramInput):
    with get_db() as conn:
        _ensure_program_exists(conn, program_id)
        conn.execute(
            """
            UPDATE programs
            SET name = ?, total_weeks = ?, notes = ?
            WHERE id = ?
            """,
            (data.name.strip(), data.total_weeks, data.notes, program_id),
        )
        row = conn.execute(
            """
            SELECT id, name, total_weeks, notes, created_at
            FROM programs
            WHERE id = ?
            """,
            (program_id,),
        ).fetchone()
    return dict(row)


@app.delete("/programs/{program_id}")
def delete_program(program_id: int):
    with get_db() as conn:
        _ensure_program_exists(conn, program_id)
        active_ref = conn.execute(
            "SELECT 1 FROM active_blocks WHERE program_id = ? AND status = 'active' LIMIT 1",
            (program_id,),
        ).fetchone()
        if active_ref is not None:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete program while an active block references it.",
            )
        conn.execute(
            """
            DELETE FROM session_log
            WHERE active_block_id IN (
                SELECT id FROM active_blocks WHERE program_id = ?
            )
            """,
            (program_id,),
        )
        conn.execute(
            """
            DELETE FROM e1rm_log
            WHERE active_block_id IN (
                SELECT id FROM active_blocks WHERE program_id = ?
            )
            """,
            (program_id,),
        )
        conn.execute("DELETE FROM active_blocks WHERE program_id = ?", (program_id,))
        conn.execute(
            """
            DELETE FROM exercise_slots
            WHERE day_id IN (
                SELECT d.id
                FROM days d
                JOIN microcycles b ON b.id = d.block_id
                WHERE b.program_id = ?
            )
            """,
            (program_id,),
        )
        conn.execute(
            """
            DELETE FROM days
            WHERE block_id IN (
                SELECT id FROM microcycles WHERE program_id = ?
            )
            """,
            (program_id,),
        )
        conn.execute("DELETE FROM microcycles WHERE program_id = ?", (program_id,))
        conn.execute("DELETE FROM blocks WHERE program_id = ?", (program_id,))
        conn.execute("DELETE FROM tiers WHERE program_id = ?", (program_id,))
        conn.execute("DELETE FROM programs WHERE id = ?", (program_id,))
    return {"deleted": True}


@app.post("/programs/{program_id}/tiers")
def create_tier(program_id: int, data: TierInput):
    with get_db() as conn:
        _ensure_program_exists(conn, program_id)
        cursor = conn.execute(
            """
            INSERT INTO tiers (program_id, name, behaviour, display_order)
            VALUES (?, ?, ?, ?)
            """,
            (program_id, data.name.strip(), data.behaviour, data.display_order),
        )
        tier_id = cursor.lastrowid
        row = conn.execute(
            """
            SELECT id, program_id, name, behaviour, display_order
            FROM tiers
            WHERE id = ?
            """,
            (tier_id,),
        ).fetchone()
    return dict(row)


@app.put("/tiers/{tier_id}")
def update_tier(tier_id: int, data: TierInput):
    with get_db() as conn:
        _ensure_tier_exists(conn, tier_id)
        conn.execute(
            """
            UPDATE tiers
            SET name = ?, behaviour = ?, display_order = ?
            WHERE id = ?
            """,
            (data.name.strip(), data.behaviour, data.display_order, tier_id),
        )
        row = conn.execute(
            """
            SELECT id, program_id, name, behaviour, display_order
            FROM tiers
            WHERE id = ?
            """,
            (tier_id,),
        ).fetchone()
    return dict(row)


@app.delete("/tiers/{tier_id}")
def delete_tier(tier_id: int):
    with get_db() as conn:
        _ensure_tier_exists(conn, tier_id)
        slot_ref = conn.execute(
            "SELECT 1 FROM exercise_slots WHERE tier_id = ? LIMIT 1",
            (tier_id,),
        ).fetchone()
        if slot_ref is not None:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete tier while slots reference it.",
            )
        conn.execute("DELETE FROM tiers WHERE id = ?", (tier_id,))
    return {"deleted": True}


@app.post("/programs/{program_id}/cycles")
def create_cycle(program_id: int, data: CycleInput):
    with get_db() as conn:
        _ensure_program_exists(conn, program_id)
        cursor = conn.execute(
            """
            INSERT INTO microcycles (program_id, cycle_number, label)
            VALUES (?, ?, ?)
            """,
            (program_id, data.cycle_number, data.label),
        )
        block_id = cursor.lastrowid
        row = conn.execute(
            """
            SELECT id, program_id, cycle_number, label
            FROM microcycles
            WHERE id = ?
            """,
            (block_id,),
        ).fetchone()
    return dict(row)


@app.delete("/cycles/{cycle_id}")
def delete_cycle(cycle_id: int):
    with get_db() as conn:
        _ensure_block_exists(conn, cycle_id)
        conn.execute(
            """
            DELETE FROM exercise_slots
            WHERE day_id IN (
                SELECT id FROM days WHERE block_id = ?
            )
            """,
            (cycle_id,),
        )
        conn.execute(
            "DELETE FROM days WHERE block_id = ?",
            (cycle_id,),
        )
        conn.execute(
            "DELETE FROM microcycles WHERE id = ?",
            (cycle_id,),
        )
    return {"deleted": True}


@app.post("/cycles/{cycle_id}/days")
def create_day(cycle_id: int, data: DayInput):
    with get_db() as conn:
        _ensure_block_exists(conn, cycle_id)
        cursor = conn.execute(
            """
            INSERT INTO days (block_id, day_number, label)
            VALUES (?, ?, ?)
            """,
            (cycle_id, data.day_number, data.label),
        )
        day_id = cursor.lastrowid
        row = conn.execute(
            """
            SELECT id, block_id, day_number, label
            FROM days
            WHERE id = ?
            """,
            (day_id,),
        ).fetchone()
    return dict(row)


@app.delete("/days/{day_id}")
def delete_day(day_id: int):
    with get_db() as conn:
        _ensure_day_exists(conn, day_id)
        block_row = conn.execute(
            "SELECT block_id FROM days WHERE id = ?",
            (day_id,),
        ).fetchone()
        if block_row is None:
            raise HTTPException(status_code=404, detail="Day not found.")
        day_count_row = conn.execute(
            "SELECT COUNT(*) AS day_count FROM days WHERE block_id = ?",
            (block_row["block_id"],),
        ).fetchone()
        if day_count_row is not None and day_count_row["day_count"] <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last day in a microcycle",
            )

        conn.execute(
            "DELETE FROM exercise_slots WHERE day_id = ?",
            (day_id,),
        )
        conn.execute(
            "DELETE FROM days WHERE id = ?",
            (day_id,),
        )
    return {"deleted": True}


@app.post("/days/{day_id}/slots")
def create_slot(day_id: int, data: SlotInput):
    with get_db() as conn:
        _ensure_day_exists(conn, day_id)
        _validate_slot_program_match(conn, day_id, data.tier_id)
        cursor = conn.execute(
            """
            INSERT INTO exercise_slots (
                day_id, tier_id, hevy_exercise_id, hevy_exercise_name,
                slot_order, wave_params, target_rpe, source_params
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                day_id,
                data.tier_id,
                data.hevy_exercise_id.strip(),
                data.hevy_exercise_name.strip(),
                data.slot_order,
                _serialize_wave_params(data.wave_params),
                data.target_rpe,
                _serialize_wave_params(data.source_params),
            ),
        )
        slot_id = cursor.lastrowid
        row = conn.execute(
            """
            SELECT id, day_id, tier_id, hevy_exercise_id, hevy_exercise_name,
                   slot_order, wave_params, target_rpe, source_params
            FROM exercise_slots
            WHERE id = ?
            """,
            (slot_id,),
        ).fetchone()
    return _slot_response(dict(row))


@app.put("/slots/{slot_id}")
def update_slot(slot_id: int, data: SlotInput):
    with get_db() as conn:
        _ensure_slot_exists(conn, slot_id)
        day_row = conn.execute(
            "SELECT day_id FROM exercise_slots WHERE id = ?",
            (slot_id,),
        ).fetchone()
        if day_row is None:
            raise HTTPException(status_code=404, detail="Slot not found.")
        day_id = day_row["day_id"]
        _validate_slot_program_match(conn, day_id, data.tier_id)
        conn.execute(
            """
            UPDATE exercise_slots
            SET tier_id = ?, hevy_exercise_id = ?, hevy_exercise_name = ?,
                slot_order = ?, wave_params = ?, target_rpe = ?, source_params = ?
            WHERE id = ?
            """,
            (
                data.tier_id,
                data.hevy_exercise_id.strip(),
                data.hevy_exercise_name.strip(),
                data.slot_order,
                _serialize_wave_params(data.wave_params),
                data.target_rpe,
                _serialize_wave_params(data.source_params),
                slot_id,
            ),
        )
        row = conn.execute(
            """
            SELECT id, day_id, tier_id, hevy_exercise_id, hevy_exercise_name,
                   slot_order, wave_params, target_rpe, source_params
            FROM exercise_slots
            WHERE id = ?
            """,
            (slot_id,),
        ).fetchone()
    return _slot_response(dict(row))


@app.delete("/slots/{slot_id}")
def delete_slot(slot_id: int):
    with get_db() as conn:
        _ensure_slot_exists(conn, slot_id)
        conn.execute("DELETE FROM exercise_slots WHERE id = ?", (slot_id,))
    return {"deleted": True}


# ── Active Blocks ──────────────────────────────────────────────────────────────

@app.get("/active-blocks")
def list_active_blocks():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, program_id, current_cycle, current_day, status, started_at
            FROM active_blocks
            ORDER BY started_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/active-blocks")
def start_active_block(data: ActiveBlockStartInput):
    with get_db() as conn:
        _ensure_program_exists(conn, data.program_id)
        cursor = conn.execute(
            """
            INSERT INTO active_blocks (program_id, current_cycle, current_day, status)
            VALUES (?, 1, 1, 'active')
            """,
            (data.program_id,),
        )
    return {"id": cursor.lastrowid}


@app.get("/active-blocks/{active_block_id}")
def get_active_block(active_block_id: int):
    with get_db() as conn:
        return _active_block_state_or_404(conn, active_block_id)


@app.post("/active-blocks/{active_block_id}/advance")
def advance_active_block(active_block_id: int):
    with get_db() as conn:
        state = _active_block_state_or_404(conn, active_block_id)
        if state["status"] != "active":
            raise HTTPException(status_code=400, detail="Only active blocks can be advanced.")

        days_in_current_cycle = conn.execute(
            """
            SELECT COUNT(*) AS day_count
            FROM days d
            JOIN microcycles b ON b.id = d.block_id
            WHERE b.program_id = ? AND b.cycle_number = ?
            """,
            (state["program_id"], state["current_cycle"]),
        ).fetchone()["day_count"]
        if days_in_current_cycle <= 0:
            raise HTTPException(
                status_code=400,
                detail="Current cycle has no days configured for this program.",
            )

        current_day = state["current_day"]
        current_cycle = state["current_cycle"]

        if current_day < days_in_current_cycle:
            conn.execute(
                """
                UPDATE active_blocks
                SET current_day = ?
                WHERE id = ?
                """,
                (current_day + 1, active_block_id),
            )
        else:
            last_cycle_row = conn.execute(
                "SELECT MAX(cycle_number) AS max_cycle FROM microcycles WHERE program_id = ?",
                (state["program_id"],),
            ).fetchone()
            max_cycle = last_cycle_row["max_cycle"]
            if max_cycle is None:
                raise HTTPException(
                    status_code=400,
                    detail="Program has no cycles configured.",
                )

            if current_cycle < max_cycle:
                next_cycle = current_cycle + 1
                next_cycle_days = conn.execute(
                    """
                    SELECT COUNT(*) AS day_count
                    FROM days d
                    JOIN microcycles b ON b.id = d.block_id
                    WHERE b.program_id = ? AND b.cycle_number = ?
                    """,
                    (state["program_id"], next_cycle),
                ).fetchone()["day_count"]
                if next_cycle_days <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail="Next cycle has no days configured for this program.",
                    )
                conn.execute(
                    """
                    UPDATE active_blocks
                    SET current_cycle = ?, current_day = 1
                    WHERE id = ?
                    """,
                    (next_cycle, active_block_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE active_blocks
                    SET status = 'completed'
                    WHERE id = ?
                    """,
                    (active_block_id,),
                )

        return _active_block_state_or_404(conn, active_block_id)


@app.delete("/active-blocks/{active_block_id}")
def abandon_active_block(active_block_id: int):
    with get_db() as conn:
        _active_block_state_or_404(conn, active_block_id)
        conn.execute(
            """
            UPDATE active_blocks
            SET status = 'abandoned'
            WHERE id = ?
            """,
            (active_block_id,),
        )
        return _active_block_state_or_404(conn, active_block_id)


@app.get("/active-blocks/{active_block_id}/session")
def get_active_block_session(active_block_id: int):
    with get_db() as conn:
        state = _active_block_state_or_404(conn, active_block_id)
        # current_cycle is used as week_number: cycle 1 = week 1 in a standard wave
        week_number = state["current_cycle"]
        slot_rows = _session_slots_for_active_block(conn, state)

        slots = []
        for row in slot_rows:
            wave_params = _parse_wave_params(row["wave_params"]) or {}
            first_set_weight_kg: float | None = None
            bbb_weight_kg: float | None = None
            baseline_for_wave: float | None = None

            raw_sets = wave_params.get("sets")
            parsed_sets: list[dict[str, Any]] = []
            if isinstance(raw_sets, list):
                for set_row in raw_sets:
                    if not isinstance(set_row, dict):
                        continue
                    reps_value = set_row.get("reps")
                    try:
                        reps_int = int(reps_value)
                    except (TypeError, ValueError):
                        continue

                    set_target_rpe = set_row.get("target_rpe")
                    target_rpe = set_target_rpe if set_target_rpe is not None else row["target_rpe"]
                    rpe_percentage = None
                    if target_rpe is not None:
                        try:
                            rpe_percentage = get_rpe_percentage(float(target_rpe), reps_int)
                        except (TypeError, ValueError):
                            pass

                    try:
                        raw_jump = set_row.get("joker_jump_pct")
                        joker_jump_pct: float | None = float(raw_jump) if raw_jump is not None else None
                    except (TypeError, ValueError):
                        joker_jump_pct = None

                    parsed_sets.append(
                        {
                            "reps": reps_int,
                            "is_amrap": bool(set_row.get("is_amrap", False)),
                            "is_joker": bool(set_row.get("is_joker", False)),
                            "target_rpe": target_rpe,
                            "rpe_percentage": rpe_percentage,
                            "joker_jump_pct": joker_jump_pct,
                        }
                    )

            is_amrap = any(set_row["is_amrap"] for set_row in parsed_sets)
            jokers_enabled = any(set_row["is_joker"] for set_row in parsed_sets)

            slot_source_params = _parse_wave_params(row.get("source_params")) or {}
            source = slot_source_params.get("source")  # "tm", "e1rm", "ddp", "free", or None

            if source == "tm":
                e1rm_kg = _resolve_e1rm(conn, row["hevy_exercise_id"])
                if e1rm_kg is None:
                    e1rm_kg = _setting_float_or_none(conn, f"tm_{row['slot_id']}")
                sp_wm_pct = slot_source_params.get("wm_pct")
                try:
                    wm_pct = float(sp_wm_pct) if sp_wm_pct is not None else None
                except (TypeError, ValueError):
                    wm_pct = None
                if wm_pct is None:
                    raw_setting = _setting_float_or_none(conn, f"wm_pct_{row['slot_id']}")
                    wm_pct = raw_setting / 100 if raw_setting is not None else 0.90
                baseline_for_wave = e1rm_kg * wm_pct if e1rm_kg is not None else None

            elif source == "e1rm":
                baseline_for_wave = _resolve_e1rm(conn, row["hevy_exercise_id"])

            elif source == "ddp":
                ddp_row = conn.execute(
                    """
                    SELECT actual_weight_kg FROM session_log
                    WHERE exercise_slot_id = ?
                      AND set_type != 'joker'
                      AND actual_weight_kg IS NOT NULL
                    ORDER BY logged_at DESC, id DESC LIMIT 1
                    """,
                    (row["slot_id"],),
                ).fetchone()
                baseline_for_wave = float(ddp_row["actual_weight_kg"]) if ddp_row is not None else None

            elif source == "free":
                baseline_for_wave = None

            else:
                # Legacy tier_behaviour fallback for programs built before source_params
                if row["tier_behaviour"] == "percentage":
                    e1rm_row = conn.execute(
                        """
                        SELECT e1rm_kg FROM e1rm_log
                        WHERE active_block_id = ? AND exercise_slot_id = ?
                        ORDER BY logged_at DESC, id DESC LIMIT 1
                        """,
                        (active_block_id, row["slot_id"]),
                    ).fetchone()
                    e1rm_kg = (
                        float(e1rm_row["e1rm_kg"])
                        if e1rm_row is not None
                        else _setting_float_or_none(conn, f"tm_{row['slot_id']}")
                    )
                    wm_pct_row = conn.execute(
                        "SELECT value FROM app_settings WHERE key = ?",
                        (f"wm_pct_{row['slot_id']}",),
                    ).fetchone()
                    wm_pct = float(wm_pct_row["value"]) / 100 if wm_pct_row else 0.90
                    baseline_for_wave = e1rm_kg * wm_pct if e1rm_kg is not None else None
                    if baseline_for_wave is not None:
                        try:
                            first_set_weight_kg = float(
                                working_weight(baseline_for_wave, week_number, wave_params)
                            )
                        except (KeyError, IndexError, TypeError, ValueError):
                            first_set_weight_kg = None
                elif row["tier_behaviour"] in {"fixed", "progression"}:
                    base_weight = _wave_param_number(
                        wave_params,
                        ["weight_kg", "fixed_weight_kg", "progression_weight_kg", "current_weight_kg"],
                    )
                    if base_weight is not None:
                        baseline_for_wave = float(base_weight)
                        first_set_weight_kg = float(round_weight(base_weight))

            if "bbb_percentages" in wave_params and baseline_for_wave is not None:
                try:
                    bbb_weight_kg = float(bbb_weight(baseline_for_wave, week_number, wave_params))
                except (KeyError, IndexError, TypeError, ValueError):
                    bbb_weight_kg = None

            # Second pass: fill planned_weight_kg per set.
            # New source-params path: each set uses baseline * its own rpe_percentage.
            # Legacy tier_behaviour path: all non-joker sets share first_set_weight_kg.
            prev_kg: float | None = first_set_weight_kg
            for s in parsed_sets:
                if s["is_joker"]:
                    if prev_kg is not None:
                        try:
                            jump = s["joker_jump_pct"] if s["joker_jump_pct"] is not None else 0.10
                            s["planned_weight_kg"] = float(joker_weight(prev_kg, jump))
                        except (TypeError, ValueError):
                            s["planned_weight_kg"] = None
                    else:
                        s["planned_weight_kg"] = None
                elif source in {"tm", "e1rm", "ddp"}:
                    rpe_pct = s.get("rpe_percentage")
                    if baseline_for_wave is not None and rpe_pct is not None:
                        s["planned_weight_kg"] = float(round_weight(baseline_for_wave * rpe_pct))
                    else:
                        s["planned_weight_kg"] = None
                else:
                    s["planned_weight_kg"] = first_set_weight_kg
                prev_kg = s["planned_weight_kg"]

            if source in {"tm", "e1rm", "ddp", "free"}:
                first_set_weight_kg = next(
                    (s["planned_weight_kg"] for s in parsed_sets if not s["is_joker"]),
                    None,
                )

            slots.append(
                {
                    "slot_id": row["slot_id"],
                    "slot_order": row["slot_order"],
                    "tier_name": row["tier_name"],
                    "tier_behaviour": row["tier_behaviour"],
                    "exercise_name": row["exercise_name"],
                    "hevy_exercise_id": row["hevy_exercise_id"],
                    "wave_params": wave_params,
                    "target_rpe": row["target_rpe"],
                    "first_set_weight_kg": first_set_weight_kg,
                    "bbb_weight_kg": bbb_weight_kg,
                    "is_amrap": is_amrap,
                    "jokers_enabled": jokers_enabled,
                    "sets": parsed_sets,
                }
            )

    return {
        "active_block_id": state["id"],
        "cycle_number": state["current_cycle"],
        "day_number": state["current_day"],
        "slots": slots,
    }


@app.post("/active-blocks/{active_block_id}/session")
def log_active_block_session(active_block_id: int, data: SessionLogInput):
    if not data.sets:
        raise HTTPException(status_code=422, detail="sets cannot be empty.")

    inserted_row_ids: list[int] = []
    normalized_sets: list[dict[str, Any]] = []
    slot_meta: dict[int, dict[str, Any]] = {}

    with get_db() as conn:
        state = _active_block_state_or_404(conn, active_block_id)
        if state["status"] != "active":
            raise HTTPException(status_code=400, detail="Session logging requires an active block.")

        for item in data.sets:
            slot_row = slot_meta.get(item.slot_id)
            if slot_row is None:
                slot_row = _slot_in_program(conn, item.slot_id, state["program_id"])
                if slot_row is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"slot_id {item.slot_id} is not part of this active block's program.",
                    )
                slot_meta[item.slot_id] = slot_row

            rounded_actual = (
                float(round_weight(item.actual_weight_kg))
                if item.actual_weight_kg is not None
                else None
            )
            cursor = conn.execute(
                """
                INSERT INTO session_log (
                    active_block_id,
                    exercise_slot_id,
                    week_number,
                    day_number,
                    set_number,
                    set_type,
                    planned_weight_kg,
                    actual_weight_kg,
                    reps,
                    target_rpe,
                    actual_rpe
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    active_block_id,
                    item.slot_id,
                    state["current_cycle"],
                    state["current_day"],
                    item.set_number,
                    item.set_type.strip().lower(),
                    None,
                    rounded_actual,
                    item.reps,
                    item.target_rpe,
                    item.actual_rpe,
                ),
            )
            inserted_row_ids.append(cursor.lastrowid)
            normalized_sets.append(
                {
                    "slot_id": item.slot_id,
                    "set_number": item.set_number,
                    "set_type": item.set_type.strip().lower(),
                    "actual_weight_kg": rounded_actual,
                    "reps": item.reps,
                    "target_rpe": item.target_rpe,
                    "actual_rpe": item.actual_rpe,
                }
            )

        sets_by_slot: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in normalized_sets:
            sets_by_slot[row["slot_id"]].append(row)

        for slot_id, set_rows in sets_by_slot.items():
            main_candidates = [
                row
                for row in set_rows
                if row["set_type"] == "main"
                and row["reps"] is not None
                and row["reps"] > 0
                and row["actual_rpe"] is not None
                and row["actual_weight_kg"] is not None
            ]
            if not main_candidates:
                continue

            amrap_set = max(main_candidates, key=lambda row: row["set_number"])
            amrap_e1rm = epley(float(amrap_set["actual_weight_kg"]), int(amrap_set["reps"]))

            joker_sets: list[tuple[float, float]] = []
            for row in set_rows:
                if (
                    row["set_type"] == "joker"
                    and row["reps"] is not None
                    and row["reps"] > 0
                    and row["actual_rpe"] is not None
                    and row["actual_weight_kg"] is not None
                ):
                    joker_e1rm = epley(float(row["actual_weight_kg"]), int(row["reps"]))
                    if joker_qualifies(joker_e1rm, amrap_e1rm):
                        joker_sets.append((float(row["actual_weight_kg"]), float(row["reps"])))

            final_e1rm = session_e1rm(amrap_e1rm, joker_sets)
            source = "joker_avg" if joker_sets else "amrap"
            conn.execute(
                """
                INSERT INTO e1rm_log (active_block_id, exercise_slot_id, e1rm_kg, source)
                VALUES (?, ?, ?, ?)
                """,
                (active_block_id, slot_id, float(round_weight(final_e1rm)), source),
            )

    hevy_synced = False
    try:
        now = datetime.now(timezone.utc).isoformat()
        grouped_for_payload: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in normalized_sets:
            grouped_for_payload[row["slot_id"]].append(row)

        payload_exercises = []
        for slot_id, set_rows in grouped_for_payload.items():
            meta = slot_meta.get(slot_id)
            if meta is None:
                continue
            payload_sets = []
            for row in sorted(set_rows, key=lambda x: x["set_number"]):
                if row["reps"] is None:
                    continue
                payload_sets.append(
                    {
                        "type": row["set_type"],
                        "weightKg": row["actual_weight_kg"],
                        "reps": row["reps"],
                    }
                )
            if payload_sets:
                payload_exercises.append(
                    {
                        "exerciseTemplateId": meta["hevy_exercise_id"],
                        "title": meta["hevy_exercise_name"],
                        "sets": payload_sets,
                    }
                )

        payload = {
            "title": f"531 BBB-AR Cycle {state['current_cycle']} Day {state['current_day']}",
            "startTime": now,
            "endTime": now,
            "exercises": payload_exercises,
        }
        hevy_workout_id = hevy_client.HevyClient().post_workout(payload)
        if hevy_workout_id:
            with get_db() as conn:
                for row_id in inserted_row_ids:
                    conn.execute(
                        "UPDATE session_log SET hevy_workout_id = ? WHERE id = ?",
                        (hevy_workout_id, row_id),
                    )
            hevy_synced = True
    except Exception:
        logger.exception("Hevy write-back failed during session logging.")
        hevy_synced = False

    return {"session_logged": True, "hevy_synced": hevy_synced}


@app.get("/active-blocks/{active_block_id}/e1rm")
def get_active_block_e1rm_history(active_block_id: int):
    with get_db() as conn:
        _active_block_state_or_404(conn, active_block_id)
        rows = conn.execute(
            """
            SELECT l.exercise_slot_id AS slot_id,
                   s.hevy_exercise_name AS exercise_name,
                   l.e1rm_kg,
                   l.source,
                   l.logged_at
            FROM e1rm_log l
            JOIN exercise_slots s ON s.id = l.exercise_slot_id
            WHERE l.active_block_id = ?
            ORDER BY l.logged_at ASC, l.id ASC
            """,
            (active_block_id,),
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/active-blocks/{active_block_id}/e1rm", status_code=204)
def create_manual_e1rm(active_block_id: int, data: ManualE1RMInput):
    with get_db() as conn:
        state = _active_block_state_or_404(conn, active_block_id)
        slot_row = _slot_in_program(conn, data.slot_id, state["program_id"])
        if slot_row is None:
            raise HTTPException(
                status_code=400,
                detail="slot_id is not part of this active block's program.",
            )
        conn.execute(
            """
            INSERT INTO e1rm_log (active_block_id, exercise_slot_id, e1rm_kg, source)
            VALUES (?, ?, ?, 'manual')
            """,
            (active_block_id, data.slot_id, float(round_weight(data.e1rm_kg))),
        )
    return Response(status_code=204)


# ── Exercises ──────────────────────────────────────────────────────────────────

@app.get("/exercises")
def get_exercises():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, title, primary_muscle, cached_at
            FROM hevy_exercise_cache
            ORDER BY title COLLATE NOCASE ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/exercises/sync")
def sync_exercises():
    count = hevy_client.HevyClient().sync_exercise_cache()
    return {"cached": count}


@app.get("/exercises/{hevy_exercise_id}/e1rm")
def get_exercise_e1rm(hevy_exercise_id: str):
    with get_db() as conn:
        e1rm_kg = _resolve_e1rm(conn, hevy_exercise_id)
    if e1rm_kg is None:
        raise HTTPException(status_code=404, detail="No e1RM data found.")
    return {"e1rm_kg": e1rm_kg}
