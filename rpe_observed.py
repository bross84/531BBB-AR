"""
rpe_observed.py — What your own logged sets say an RPE table should look like, one lift at a time.

Each set is turned into an observed percentage: its weight as a share of the lift's anchor e1RM, the e1RM of the
newest TS saved on or before that set's workout. (The TS defines the anchor, so it is left out of its own table.)
Sets sharing an RPE and rep count are averaged into one cell, so the table fills in as you log. Pure: no DB access.
Warm-ups and drop sets are left out, as are sets without a weight, reps or an RPE.
"""
from __future__ import annotations

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
    used = no_anchor = 0
    for s in sets:
        if s["set_type"] in SKIPPED_TYPES or s["is_ts"]:
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
        buckets[(float(rpe), int(reps))].append(weight * LB_PER_KG / anchor["e1rm_lb"])
        used += 1

    cells = [
        {"rpe": rpe, "reps": reps, "n": len(values), "observed": sum(values) / len(values), "chart": chart(rpe, reps)}
        for (rpe, reps), values in sorted(buckets.items(), key=lambda kv: (-kv[0][0], kv[0][1]))
    ]
    newest = anchors[-1] if anchors else None
    return {
        "anchor_e1rm_lb": newest["e1rm_lb"] if newest else None,
        "anchor_set_at": newest["set_at"] if newest else None,
        "sets_used": used,
        "sets_without_anchor": no_anchor,
        "cells": cells,
    }
