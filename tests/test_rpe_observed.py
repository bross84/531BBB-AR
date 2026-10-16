"""Tests for rpe_observed: your own logged sets turned into an RPE table, measured against the lift's TS."""
import os
import shutil
import sys
import tempfile
import unittest
import warnings

warnings.filterwarnings("ignore", category=ResourceWarning)

_IMPORT_DIR = tempfile.mkdtemp()
os.environ.setdefault("DB_PATH", os.path.join(_IMPORT_DIR, "import.db"))

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
import rpe_observed  # noqa: E402
import set_log  # noqa: E402
import training_max  # noqa: E402
from exercise_state import LB_PER_KG  # noqa: E402

DAY1 = "2026-10-16T00:25:31.873Z"
DAY3 = "2026-10-20T00:10:00.000Z"
ANCHOR_KG = 160.0


def ts(set_at, e1rm_kg=ANCHOR_KG):
    return {"e1rm_lb": e1rm_kg * LB_PER_KG, "set_at": set_at}


def S(weight_kg, reps, rpe, start=DAY1, set_type="normal", is_ts=0):
    return {"weight_kg": weight_kg, "reps": reps, "rpe": rpe, "set_type": set_type, "is_ts": is_ts, "workout_start": start}


def chart(rpe, reps):
    return {(7.0, 5): 0.80}.get((rpe, reps))


class TestBuildObserved(unittest.TestCase):

    def test_a_set_is_its_weight_as_a_share_of_the_anchor(self):
        out = rpe_observed.build_observed([S(128, 5, 7.0)], [ts(DAY1)], chart)
        self.assertEqual(1, len(out["cells"]))
        cell = out["cells"][0]
        self.assertEqual((7.0, 5, 1, 0.80), (cell["rpe"], cell["reps"], cell["n"], round(cell["observed"], 4)))
        self.assertEqual(0.80, cell["chart"])

    def test_sets_with_the_same_rpe_and_reps_are_averaged(self):
        out = rpe_observed.build_observed([S(128, 5, 7.0), S(124.8, 5, 7.0)], [ts(DAY1)], chart)
        cell = out["cells"][0]
        self.assertEqual(2, cell["n"])
        self.assertAlmostEqual(0.79, cell["observed"], places=4)

    def test_warmups_and_dropsets_are_left_out(self):
        sets = [S(60, 5, 7.0, set_type="warmup"), S(100, 5, 7.0, set_type="dropset"), S(128, 5, 7.0)]
        out = rpe_observed.build_observed(sets, [ts(DAY1)], chart)
        self.assertEqual(1, out["sets_used"])
        self.assertEqual(1, len(out["cells"]))

    def test_the_ts_gets_its_own_cell_but_is_not_averaged_or_counted_as_used(self):
        # 160 kg e1RM: the 1 @7 single is the anchor, so it sits at its own share of the anchor
        out = rpe_observed.build_observed([S(145, 1, 7.0, is_ts=1), S(128, 5, 7.0)], [ts(DAY1)], chart)
        self.assertEqual((1, 1), (out["sets_used"], out["ts_sets"]))
        single, five = out["cells"]
        self.assertEqual((7.0, 1, 0, 1), (single["rpe"], single["reps"], single["n"], single["ts"]))
        self.assertAlmostEqual(145 * LB_PER_KG / (ANCHOR_KG * LB_PER_KG), single["observed"], places=4)
        self.assertEqual((7.0, 5, 1, 0), (five["rpe"], five["reps"], five["n"], five["ts"]))

    def test_a_cell_with_the_ts_and_other_sets_averages_only_the_others(self):
        out = rpe_observed.build_observed([S(145, 1, 7.0, is_ts=1), S(140, 1, 7.0, start=DAY1)], [ts(DAY1)], chart)
        cell = out["cells"][0]
        self.assertEqual((1, 1), (cell["n"], cell["ts"]))
        self.assertAlmostEqual(140 / ANCHOR_KG, cell["observed"], places=4)   # the 140, not the mean of 140 and the TS

    def test_sets_missing_a_weight_reps_or_rpe_are_left_out(self):
        sets = [S(None, 5, 7.0), S(100, None, 7.0), S(100, 5, None), S(0, 5, 7.0)]
        out = rpe_observed.build_observed(sets, [ts(DAY1)], chart)
        self.assertEqual((0, 0, []), (out["sets_used"], out["sets_without_anchor"], out["cells"]))

    def test_a_set_is_measured_against_the_newest_ts_on_or_before_its_workout(self):
        history = [ts(DAY1, 160.0), ts(DAY3, 170.0)]
        out = rpe_observed.build_observed([S(128, 5, 7.0, start=DAY1), S(136, 5, 6.5, start=DAY3)], history, chart)
        by_rpe = {c["rpe"]: c["observed"] for c in out["cells"]}
        self.assertAlmostEqual(0.80, by_rpe[7.0], places=4)    # 128 against the day 1 anchor of 160
        self.assertAlmostEqual(0.80, by_rpe[6.5], places=4)    # 136 against the day 3 anchor of 170, not 160
        self.assertEqual(170.0 * LB_PER_KG, out["anchor_e1rm_lb"])

    def test_sets_before_the_first_ts_are_counted_but_not_measured(self):
        out = rpe_observed.build_observed([S(128, 5, 7.0, start=DAY1)], [ts(DAY3)], chart)
        self.assertEqual((0, 1, []), (out["sets_used"], out["sets_without_anchor"], out["cells"]))

    def test_no_ts_at_all_gives_an_empty_table(self):
        out = rpe_observed.build_observed([S(128, 5, 7.0)], [], chart)
        self.assertEqual((None, None, 0, 1, []), (out["anchor_e1rm_lb"], out["anchor_set_at"], out["sets_used"], out["sets_without_anchor"], out["cells"]))

    def test_cells_run_from_the_highest_rpe_down_then_by_reps(self):
        sets = [S(100, 5, 6.5), S(100, 3, 8.0), S(100, 1, 8.0), S(100, 5, 8.0)]
        out = rpe_observed.build_observed(sets, [ts(DAY1)], chart)
        self.assertEqual([(8.0, 1), (8.0, 3), (8.0, 5), (6.5, 5)], [(c["rpe"], c["reps"]) for c in out["cells"]])


def _synthetic(e1rm_kg, slope, shapes, start):
    """Sets that follow f(k) = 1 - slope * (k - 1) exactly, one per (reps, rpe)."""
    return [S(round(e1rm_kg * (1 - slope * (reps + 10 - rpe - 1)), 4), reps, rpe, start=start) for reps, rpe in shapes]


class TestFitCurve(unittest.TestCase):
    SHAPES = [(1, 7.0), (5, 5.0), (5, 6.5), (5, 7.5)]

    def test_it_recovers_the_slope_and_each_workouts_e1rm_without_using_the_table(self):
        sets = _synthetic(150.0, 0.03, self.SHAPES, DAY1) + _synthetic(155.0, 0.03, self.SHAPES, DAY3)
        out = rpe_observed.fit_curve(sets, [ts(DAY1), ts(DAY3)], chart)
        self.assertAlmostEqual(0.03, out["slope"], places=3)
        by = {s["workout_start"]: s for s in out["sessions"]}
        self.assertAlmostEqual(150.0 * LB_PER_KG, by[DAY1]["e1rm_lb"], delta=1.0)
        self.assertAlmostEqual(155.0 * LB_PER_KG, by[DAY3]["e1rm_lb"], delta=1.0)
        self.assertEqual((2, 8), (out["informative_sessions"], out["sets_fitted"]))
        self.assertLess(out["rms_error"], 0.001)

    def test_the_ts_single_counts_like_any_other_set(self):
        sets = _synthetic(150.0, 0.03, self.SHAPES, DAY1)
        sets[0]["is_ts"] = 1   # the 1 @7
        self.assertEqual(4, rpe_observed.fit_curve(sets, [ts(DAY1)], chart)["sets_fitted"])

    def test_a_workout_with_every_set_at_one_k_does_not_pin_the_slope_but_still_gets_an_e1rm(self):
        same_k = _synthetic(150.0, 0.03, [(5, 7.0), (3, 5.0), (7, 9.0)], DAY1)   # k is 8 for all three
        varied = _synthetic(150.0, 0.03, self.SHAPES, DAY3)
        out = rpe_observed.fit_curve(same_k + varied, [], chart)
        self.assertEqual(1, out["informative_sessions"])
        self.assertAlmostEqual(0.03, out["slope"], places=3)
        self.assertEqual(2, len(out["sessions"]))

    def test_no_workout_with_two_different_k_means_no_fit(self):
        self.assertIsNone(rpe_observed.fit_curve([S(128, 5, 7.0)], [], chart))
        self.assertIsNone(rpe_observed.fit_curve([], [], chart))

    def test_warmups_and_dropsets_do_not_enter_the_fit(self):
        sets = _synthetic(150.0, 0.03, self.SHAPES, DAY1) + [S(30, 12, 3.0, set_type="warmup"), S(60, 12, 4.0, set_type="dropset")]
        self.assertEqual(4, rpe_observed.fit_curve(sets, [ts(DAY1)], chart)["sets_fitted"])

    def test_the_table_in_use_is_reported_beside_the_fit(self):
        sets = _synthetic(150.0, 0.03, self.SHAPES, DAY1)
        full = lambda rpe, reps: {(10.0, 2): 0.96, (10.0, 10): 0.746}.get((rpe, reps))
        out = rpe_observed.fit_curve(sets, [ts(DAY1, 148.0)], full)
        self.assertAlmostEqual((0.96 - 0.746) / 8, out["table_slope"])
        self.assertAlmostEqual(148.0 * 2.20462, out["sessions"][0]["table_e1rm_lb"], places=3)


class TestObservedRoutes(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["DB_PATH"] = os.path.join(self.tmp, "test.db")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.client = TestClient(main.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def _log(self, template, title, sets):
        entry = {"title": "Day", "start_time": DAY1, "end_time": DAY1,
                 "exercises": [{"exercise_template_id": template, "title": title, "sets": sets}]}
        set_log.record(set_log.rows_from_entry(entry, "h1"))

    def test_lists_squat_bench_and_deadlift_with_what_is_logged_for_each(self):
        self._log("tpl-squat", "Squat, Low Bar w/ Belt", [
            {"type": "warmup", "weight_kg": 60, "reps": 5, "rpe": None},
            {"type": "normal", "weight_kg": 120, "reps": 5, "rpe": 5},
            {"type": "normal", "weight_kg": 128, "reps": 5, "rpe": 7},
        ])
        self._log("tpl-row", "Pendlay Row (Barbell)", [{"type": "normal", "weight_kg": 80, "reps": 5, "rpe": 7}])   # not a main lift: not listed
        got = self.client.get("/rpe-observed").json()
        self.assertEqual(["squat", "bench", "deadlift"], [l["key"] for l in got])
        self.assertEqual(("tpl-squat", 2, 1), (got[0]["exercise_template_id"], got[0]["sets"], got[0]["sessions"]))
        self.assertEqual((None, 0, 0), (got[1]["exercise_template_id"], got[1]["sets"], got[1]["sessions"]))   # nothing logged yet

    def test_a_squat_logged_without_an_rpe_does_not_count(self):
        self._log("tpl-squat", "Squat, Low Bar w/ Belt", [{"type": "normal", "weight_kg": 120, "reps": 5, "rpe": None}])
        self.assertIsNone(self.client.get("/rpe-observed").json()[0]["exercise_template_id"])

    def test_the_table_for_a_movement_uses_its_saved_ts_as_the_anchor(self):
        self._log("tpl-squat", "Squat", [
            {"type": "normal", "weight_kg": 145, "reps": 1, "rpe": 7, "ts": True},
            {"type": "normal", "weight_kg": 130, "reps": 5, "rpe": 7.5},
        ])
        training_max.record([{"exercise_template_id": "tpl-squat", "weight_lb": 319.7, "reps": 1, "rpe": 7.0, "e1rm_lb": 352.7}], DAY1)
        r = self.client.get("/rpe-observed/tpl-squat")
        self.assertEqual(200, r.status_code, r.text)
        body = r.json()
        self.assertEqual(("Squat", 1, 0, 352.7), (body["title"], body["sets_used"], body["sets_without_anchor"], body["anchor_e1rm_lb"]))
        cell = body["cells"][0]
        self.assertEqual((7.5, 5, 1), (cell["rpe"], cell["reps"], cell["n"]))
        self.assertAlmostEqual(130 * LB_PER_KG / 352.7, cell["observed"], places=4)
        self.assertIsNotNone(cell["chart"])   # the RPE table in use has a value for 5 @7.5

    def test_an_unknown_movement_is_just_empty(self):
        body = self.client.get("/rpe-observed/nope").json()
        self.assertEqual((None, 0, []), (body["title"], body["sets_used"], body["cells"]))


if __name__ == "__main__":
    unittest.main()
