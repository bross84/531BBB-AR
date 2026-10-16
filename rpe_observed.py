"""
rpe_observed.py — What your own logged sets say an RPE table should look like, one lift at a time.

Each set is turned into an observed percentage: its weight as a share of the lift's anchor e1RM, the e1RM of the
newest TS saved on or before that set's workout. Sets sharing an RPE and rep count are averaged into one cell, so the
table fills in as you log.

The TS has a cell too, but it is the reference the other sets are measured with, so it can only ever agree with the
table: it is shown in its cell and counted separately (ts), and is kept out of the average so it cannot make a cell
look better supported than it is. Warm-ups and drop sets are left out, as are sets without a weight, reps or an RPE.
Pure: no DB access.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Callable

from exercise_state import LB_PER_KG

PctLookup = Callable[[float, int], "float | None"]
SKIPPED_TYPES = ("warmup", "dropset")


def build_observed(sets: list[dict[str, Any]], ts_history: list[dict[str, Any]], chart: PctLookup) -> dict[str, Any]:
    """
    sets: logged_sets rows for one lift (weight_kg, reps, rpe, set_type, is_ts, workout_start).
    ts_history: that lift's TS rows (e1rm_lb, set_at), any order.
    chart: the RPE table in use, rpe/reps -> fraction of e1RM (or None), to sit beside each observed value.
    """
    anchors = sorted(ts_history, key=lambda t: t["set_at"])
    buckets: dict[tuple[float, int], list[float]] = defaultdict(list)
    ts_cells: dict[tuple[float, int], list[float]] = defaultdict(list)
    used = no_anchor = 0
    for s in sets:
        if s["set_type"] in SKIPPED_TYPES:
            continue
        weight, reps, rpe = s["weight_kg"], s["reps"], s["rpe"]
        if not weight or not reps or rpe is None:
            continue
        anchor = None
        for t in anchors:
            if t["set_at"] > s["workout_start"]:
                break
            anchor = t
        if anchor is None:
            no_anchor += 1
            continue
        share = weight * LB_PER_KG / anchor["e1rm_lb"]
        key = (float(rpe), int(reps))
        if s["is_ts"]:
            ts_cells[key].append(share)
        else:
            buckets[key].append(share)
            used += 1

    cells = []
    for key in sorted(set(buckets) | set(ts_cells), key=lambda k: (-k[0], k[1])):
        rpe, reps = key
        values = buckets.get(key)
        shown = values or ts_cells[key]   # a cell with only the TS shows the TS's own share (the table's value)
        cells.append({
            "rpe": rpe, "reps": reps, "n": len(values or []), "ts": len(ts_cells.get(key, [])),
            "observed": sum(shown) / len(shown), "chart": chart(rpe, reps),
        })
    newest = anchors[-1] if anchors else None
    return {
        "anchor_e1rm_lb": newest["e1rm_lb"] if newest else None,
        "anchor_set_at": newest["set_at"] if newest else None,
        "sets_used": used,
        "ts_sets": sum(len(v) for v in ts_cells.values()),
        "sets_without_anchor": no_anchor,
        "cells": cells,
    }


# ── A fit that does not use the table's values ────────────────────────────────
# Measuring sets against the TS's e1RM is circular: that e1RM comes from the table's own value at the TS's cell. The
# fit below uses only the table's structure, never its numbers. A set of `reps` at `rpe` is as hard as a set to failure of
# k = reps + (10 - rpe) reps, and the share of the max you can lift for k reps is taken as a straight line in k:
# f(k) = 1 - slope * (k - 1), so a true RPE 10 single is 100% by definition. Each workout has its own e1RM; the slope is
# shared. Every set counts, the TS included. Workouts whose sets all sit at one k say nothing about the slope.
MIN_SLOPE, MAX_SLOPE, SLOPE_STEP = 0.005, 0.08, 0.0001


def _k(reps: int, rpe: float) -> float:
    return reps + 10 - rpe


def fit_curve(sets: list[dict[str, Any]], ts_history: list[dict[str, Any]], chart: PctLookup) -> dict[str, Any] | None:
    """
    The slope (fraction of the max lost per extra rep to failure) and each workout's e1RM that best fit the sets, or
    None when no workout has sets at two different k. Alongside, the table in use's slope and the e1RM the TS gave.
    """
    sessions: dict[str, list[tuple[float, float]]] = defaultdict(list)   # workout start -> [(weight_kg, k)]
    for s in sets:
        if s["set_type"] in SKIPPED_TYPES or not s["weight_kg"] or not s["reps"] or s["rpe"] is None:
            continue
        sessions[s["workout_start"]].append((float(s["weight_kg"]), _k(int(s["reps"]), float(s["rpe"]))))
    informative = {start: pts for start, pts in sessions.items() if len({k for _, k in pts}) > 1}
    if not informative:
        return None

    def solve(slope: float, pts: list[tuple[float, float]]):
        """(log of the workout's e1RM, squared misses) at this slope, or None if the curve goes non-positive."""
        logs = []
        for weight, k in pts:
            f = 1 - slope * (k - 1)
            if f <= 0.05:
                return None
            logs.append(math.log(weight / f))
        mean = sum(logs) / len(logs)
        return mean, sum((x - mean) ** 2 for x in logs)

    best = None
    steps = int(round((MAX_SLOPE - MIN_SLOPE) / SLOPE_STEP))
    for i in range(steps + 1):
        slope = MIN_SLOPE + i * SLOPE_STEP
        total = 0.0
        for pts in informative.values():
            solved = solve(slope, pts)
            if solved is None:
                total = math.inf
                break
            total += solved[1]
        if best is None or total < best[0]:
            best = (total, slope)
    if best is None or math.isinf(best[0]):
        return None
    sse, slope = best

    anchors = sorted(ts_history, key=lambda t: t["set_at"])
    out_sessions = []
    for start in sorted(sessions):
        solved = solve(slope, sessions[start])
        if solved is None:
            continue
        table = None
        for t in anchors:
            if t["set_at"] > start:
                break
            table = t
        out_sessions.append({
            "workout_start": start,
            "e1rm_lb": math.exp(solved[0]) * LB_PER_KG,
            "table_e1rm_lb": table["e1rm_lb"] if table else None,
            "sets": len(sessions[start]),
        })
    fitted = sum(len(p) for p in informative.values())
    low, high = chart(10.0, 2), chart(10.0, 10)
    return {
        "slope": slope,
        "table_slope": (low - high) / 8 if low is not None and high is not None else None,
        "rms_error": math.sqrt(sse / fitted),
        "informative_sessions": len(informative),
        "sets_fitted": fitted,
        "sessions": out_sessions,
    }
