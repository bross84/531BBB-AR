"""
set_log.py — Rackbook's own record of every set you log.

Hevy cannot store an RPE below 6 (or 6.5), so the workout posted to Hevy loses it. This keeps each set exactly as
it was entered on the log page, with the RPE as typed, so history (and later a per-lift RPE chart) can use it.
Rows are written once Hevy has accepted the workout. Weights are in kg, as typed.
"""
from __future__ import annotations

from typing import Any

from database import get_db


def rows_from_entry(entry: dict[str, Any], hevy_workout_id: str | None) -> list[dict[str, Any]]:
    """One row per set of a logged workout. set_number counts from 1 within the exercise, warm-ups included."""
    rows = []
    for exercise in entry.get("exercises") or []:
        for number, s in enumerate(exercise.get("sets") or [], start=1):
            rows.append({
                "hevy_workout_id": hevy_workout_id,
                "workout_title": entry.get("title"),
                "workout_start": entry["start_time"],
                "workout_end": entry.get("end_time"),
                "exercise_template_id": exercise["exercise_template_id"],
                "exercise_title": exercise.get("title"),
                "set_number": number,
                "set_type": s.get("type") or "normal",
                "weight_kg": s.get("weight_kg"),
                "reps": s.get("reps"),
                "rpe": s.get("rpe"),
                "is_ts": 1 if s.get("ts") else 0,
            })
    return rows


def record(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with get_db() as conn:
        conn.executemany(
            """
            INSERT INTO logged_sets (
                hevy_workout_id, workout_title, workout_start, workout_end, exercise_template_id, exercise_title,
                set_number, set_type, weight_kg, reps, rpe, is_ts
            ) VALUES (
                :hevy_workout_id, :workout_title, :workout_start, :workout_end, :exercise_template_id, :exercise_title,
                :set_number, :set_type, :weight_kg, :reps, :rpe, :is_ts
            )
            """,
            rows,
        )


def lifts_with_rpe() -> list[dict[str, Any]]:
    """The movements that have working sets logged with an RPE, most sets first."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT exercise_template_id, MAX(exercise_title) AS title, COUNT(*) AS sets,
                   COUNT(DISTINCT workout_start) AS sessions
            FROM logged_sets
            WHERE set_type NOT IN ('warmup', 'dropset') AND rpe IS NOT NULL
            GROUP BY exercise_template_id
            ORDER BY sets DESC, title
            """
        ).fetchall()
    return [dict(r) for r in rows]


def for_exercise(exercise_template_id: str) -> list[dict[str, Any]]:
    """Every recorded set of one movement, oldest first."""
    with get_db() as conn:
        found = conn.execute(
            "SELECT * FROM logged_sets WHERE exercise_template_id = ? ORDER BY workout_start, id",
            (exercise_template_id,),
        ).fetchall()
    return [dict(r) for r in found]
