"""
refs_store.py — Per-movement settings for the log page, kept in SQLite.

Keyed by the Hevy exercise template id so the same choices follow the movement into every workout:
  basis   'e1rm' or 'tm': which number weights are planned from
  ls      whether the last set's e1RM (LSe1RM) feeds the next set's weight
  tm_pct  the TM as a fraction of the e1RM (default 0.95)
The e1RM and TM themselves are not stored: they are worked out from the movement's last session in Hevy.
(The table also holds older e1rm_lb / tm_lb / auto columns from an earlier version; they are unused.)
"""
from __future__ import annotations

from typing import Any

from database import get_db

DEFAULT_TM_PCT = 0.95

_COLUMNS = "exercise_template_id, basis, ls, tm_pct"


def _row_to_ref(row) -> dict[str, Any]:
    return {
        "exercise_template_id": row["exercise_template_id"],
        "basis": row["basis"],
        "ls": bool(row["ls"]),
        "tm_pct": row["tm_pct"],
    }


def list_refs() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(f"SELECT {_COLUMNS} FROM exercise_refs ORDER BY exercise_template_id").fetchall()
    return [_row_to_ref(r) for r in rows]


def save_ref(exercise_template_id: str, basis: str, ls: bool, tm_pct: float) -> dict[str, Any]:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO exercise_refs (exercise_template_id, basis, ls, tm_pct)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(exercise_template_id) DO UPDATE SET
                basis = excluded.basis,
                ls = excluded.ls,
                tm_pct = excluded.tm_pct,
                updated_at = CURRENT_TIMESTAMP
            """,
            (exercise_template_id, basis, 1 if ls else 0, tm_pct),
        )
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM exercise_refs WHERE exercise_template_id = ?", (exercise_template_id,)
        ).fetchone()
    return _row_to_ref(row)
