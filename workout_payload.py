"""
workout_payload.py — Pure builder for the body of Hevy's POST /v1/workouts.
No DB access, no HTTP calls, no side effects.

Hevy's rules (docs/hevy-api.md): snake_case keys wrapped in {"workout": {...}}; set type is one of
warmup / normal / failure / dropset; rpe is one of 6, 7, 7.5, 8, 8.5, 9, 9.5, 10 or null.
An RPE Hevy cannot store (below 6, or 6.5) is left blank, and the caller is warned.
Weights are typed in lb but loaded in kg, so they are posted as the nearest half kilo (198 lb -> 90 kg).
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

LB_TO_KG = 0.45359237  # exact definition; matches how Hevy converts the lb the user types
SET_TYPES = ("warmup", "normal", "failure", "dropset")
HEVY_RPE_VALUES = (6.0, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0)


def lb_to_kg(lb: float) -> float:
    return round(lb * LB_TO_KG, 2)


def lb_to_plate_kg(lb: float) -> float:
    """The kg actually on the bar for a weight typed in lb: the nearest half kilo."""
    return math.floor(lb * LB_TO_KG * 2 + 0.5) / 2


def _parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid timestamp: {value!r}") from exc


def _set_label(set_type: str, working: int) -> str:
    """Name a set the way the log page numbers it: warm-ups are unnumbered, every other set counts."""
    if set_type == "warmup":
        return "warm-up"
    prefix = {"failure": "failure ", "dropset": "drop "}.get(set_type, "")
    return f"{prefix}set {working}"


def build_hevy_workout(entry: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """
    Convert a logged workout (weights in lb) into Hevy's request body.
    Returns (body, warnings). Raises ValueError if the workout can't be sent.
    Warnings list anything dropped, e.g. an RPE Hevy can't store.
    """
    title = (entry.get("title") or "").strip()
    if not title:
        raise ValueError("Workout needs a title.")

    start = _parse_time(entry.get("start_time"))
    end = _parse_time(entry.get("end_time"))
    if end < start:
        raise ValueError("Workout end time is before its start time.")

    warnings: list[str] = []
    exercises = []
    for raw_exercise in entry.get("exercises") or []:
        template_id = (raw_exercise.get("exercise_template_id") or "").strip()
        name = raw_exercise.get("title") or template_id or "exercise"
        if not template_id:
            raise ValueError(f"{name} has no Hevy exercise id.")

        sets = []
        working = 0
        for number, raw_set in enumerate(raw_exercise.get("sets") or [], start=1):
            set_type = raw_set.get("type") or "normal"
            if set_type not in SET_TYPES:
                raise ValueError(f"{name} set {number}: unknown set type {set_type!r}.")

            if set_type != "warmup":
                working += 1
            weight_lb = raw_set.get("weight_lb")
            if weight_lb is not None and weight_lb < 0:
                raise ValueError(f"{name} set {number}: weight can't be negative.")
            reps = raw_set.get("reps")
            if reps is not None and reps < 0:
                raise ValueError(f"{name} set {number}: reps can't be negative.")

            rpe = raw_set.get("rpe")
            if rpe is not None and not 0 <= float(rpe) <= 10:
                raise ValueError(f"{name} set {number}: RPE must be between 0 and 10.")
            if rpe is not None and float(rpe) not in HEVY_RPE_VALUES:
                warnings.append(
                    f"{name} {_set_label(set_type, working)}: RPE {float(rpe):g} can't be stored in Hevy, "
                    "so it was left blank."
                )
                rpe = None

            sets.append(
                {
                    "type": set_type,
                    "weight_kg": lb_to_plate_kg(weight_lb) if weight_lb is not None else None,
                    "reps": reps,
                    "rpe": float(rpe) if rpe is not None else None,
                }
            )
        if not sets:
            continue

        exercise: dict[str, Any] = {"exercise_template_id": template_id, "sets": sets}
        notes = (raw_exercise.get("notes") or "").strip()
        if notes:
            exercise["notes"] = notes
        exercises.append(exercise)

    if not exercises:
        raise ValueError("Add at least one completed set before saving.")

    workout: dict[str, Any] = {
        "title": title,
        "start_time": entry["start_time"],
        "end_time": entry["end_time"],
        "exercises": exercises,
    }
    description = (entry.get("description") or "").strip()
    if description:
        workout["description"] = description
    return {"workout": workout}, warnings
