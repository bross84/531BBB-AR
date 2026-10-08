"""
refs_store.py — Per-exercise reference numbers and auto-weight settings, kept in SQLite.

An exercise keeps two separate numbers (both in lb): its e1RM and its TM. `basis` says which one the
log page plans weights from, and `auto` says whether it plans them at all. Keyed by the Hevy exercise
template id, so the same settings follow the exercise into every workout.
"""
from __future__ import annotations

from typing import Any

from database import get_db


def _row_to_ref(row) -> dict[str, Any]:
    return {
        "exercise_template_id": row["exercise_template_id"],
        "e1rm_lb": row["e1rm_lb"],
        "tm_lb": row["tm_lb"],
        "basis": row["basis"],
        "auto": bool(row["auto"]),
    }


def list_refs() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT exercise_template_id, e1rm_lb, tm_lb, basis, auto FROM exercise_refs"
            " ORDER BY exercise_template_id"
        ).fetchall()
    return [_row_to_ref(r) for r in rows]


def save_ref(
    exercise_template_id: str,
    e1rm_lb: float | None,
    tm_lb: float | None,
    basis: str,
    auto: bool,
) -> dict[str, Any]:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO exercise_refs (exercise_template_id, e1rm_lb, tm_lb, basis, auto)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(exercise_template_id) DO UPDATE SET
                e1rm_lb = excluded.e1rm_lb,
                tm_lb = excluded.tm_lb,
                basis = excluded.basis,
                auto = excluded.auto,
                updated_at = CURRENT_TIMESTAMP
            """,
            (exercise_template_id, e1rm_lb, tm_lb, basis, 1 if auto else 0),
        )
        row = conn.execute(
            "SELECT exercise_template_id, e1rm_lb, tm_lb, basis, auto FROM exercise_refs"
            " WHERE exercise_template_id = ?",
            (exercise_template_id,),
        ).fetchone()
    return _row_to_ref(row)
