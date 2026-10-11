"""
progress.py — The numbers behind the /progress page: a lift's e1RM per session next to bodyweight and DOTS.
Pure: no DB access, no HTTP calls.

e1RM per session comes from Hevy's per-set exercise history with the user's RPE table (the same
reference_set the log page uses), so sets logged without an RPE don't count. Bodyweight is the 7-day
trailing average of the daily weigh-ins, taken as of each session's date.
"""
from __future__ import annotations

from typing import Any

from exercise_state import LB_PER_KG, PctLookup, reference_set, sessions_newest_first
from strength_score import Sex, dots_score, smooth_body_weight, weight_on

# The four main lifts and the one Hevy exercise each reads: the movements trained as the main lifts,
# by exact title in the exercise cache. Other variants (paused, other bars) are different movements
# and are not mixed in. Change a title here if a main lift changes.
LIFT_TITLES: dict[str, str] = {
    "squat": "Squat, Low Bar w/ Belt",
    "bench": "Bench Press - Close Grip (Barbell)",
    "deadlift": "Deadlift, Conv. w/ Belt",
    "press": "Overhead Press (Barbell)",
}


def e1rm_by_session(entries: list[dict[str, Any]], pct: PctLookup) -> list[dict[str, Any]]:
    """One point per workout that has a usable set, oldest first: {date, e1rm_lb}."""
    points = []
    for session in sessions_newest_first(entries):
        ref = reference_set(session, pct)
        start = ref and ref["entry"].get("workout_start_time")
        if ref is None or not start:
            continue
        points.append({"date": start[:10], "e1rm_lb": ref["e1rm_lb"]})
    points.reverse()
    return points


def build_series(
    sessions: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    sex: Sex = "male",
) -> list[dict[str, Any]]:
    """
    Each session's {date, e1rm_lb} plus the smoothed bodyweight that day and the DOTS score.
    Sessions before the first weigh-in keep their e1RM but get no bodyweight or score.
    """
    smoothed = smooth_body_weight(measurements)
    series = []
    for point in sessions:
        bw_kg = weight_on(smoothed, point["date"])
        series.append({
            "date": point["date"],
            "e1rm_lb": round(point["e1rm_lb"], 1),
            "bodyweight_lb": round(bw_kg * LB_PER_KG, 1) if bw_kg is not None else None,
            "dots": round(dots_score(point["e1rm_lb"] / LB_PER_KG, bw_kg, sex), 1) if bw_kg is not None else None,
        })
    return series
