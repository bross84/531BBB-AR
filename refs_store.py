"""
refs_store.py — Per-movement settings for the log page, kept in SQLite.

Keyed by the Hevy exercise template id so the same choices follow the movement into every workout:
  basis   'e1rm' or 'tm': which number weights are planned from
  ls      whether the last set's e1RM (LSe1RM) feeds the next set's weight
  tm_pct  the TM as a fraction of the e1RM (default 0.95)
  step_kg the plate step planned weights are rounded to (default 2.5 kg; a light lift like a pull-up wants 0.5)
The e1RM and TM themselves are not stored: they are worked out from the movement's last session in Hevy.
(The table also holds older e1rm_lb / tm_lb / auto columns from an earlier version; they are unused.)
"""
from __future__ import annotations

from typing import Any

from database import get_db

DEFAULT_TM_PCT = 0.95
DEFAULT_STEP_KG = 2.5
DEFAULT_STEP_LB = 5.0
DEFAULT_BAR_KG = 20.0
DEFAULT_CHAIN_KG = 0.0

_COLUMNS = "exercise_template_id, basis, ls, tm_pct, step_kg, step_lb, bar_kg, chain_kg"


def _row_to_ref(row) -> dict[str, Any]:
    return {
        "exercise_template_id": row["exercise_template_id"],
        "basis": row["basis"],
        "ls": bool(row["ls"]),
        "tm_pct": row["tm_pct"],
        "step_kg": row["step_kg"],
        "step_lb": row["step_lb"],
        "bar_kg": row["bar_kg"],
        "chain_kg": row["chain_kg"],
    }


def list_refs() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(f"SELECT {_COLUMNS} FROM exercise_refs ORDER BY exercise_template_id").fetchall()
    return [_row_to_ref(r) for r in rows]


def save_ref(
    exercise_template_id: str, basis: str, ls: bool, tm_pct: float,
    step_kg: float = DEFAULT_STEP_KG, step_lb: float = DEFAULT_STEP_LB,
    bar_kg: float = DEFAULT_BAR_KG, chain_kg: float = DEFAULT_CHAIN_KG,
) -> dict[str, Any]:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO exercise_refs (exercise_template_id, basis, ls, tm_pct, step_kg, step_lb, bar_kg, chain_kg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(exercise_template_id) DO UPDATE SET
                basis = excluded.basis,
                ls = excluded.ls,
                tm_pct = excluded.tm_pct,
                step_kg = excluded.step_kg,
                step_lb = excluded.step_lb,
                bar_kg = excluded.bar_kg,
                chain_kg = excluded.chain_kg,
                updated_at = CURRENT_TIMESTAMP
            """,
            (exercise_template_id, basis, 1 if ls else 0, tm_pct, step_kg, step_lb, bar_kg, chain_kg),
        )
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM exercise_refs WHERE exercise_template_id = ?", (exercise_template_id,)
        ).fetchone()
    return _row_to_ref(row)
