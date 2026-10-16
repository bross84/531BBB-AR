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

    def test_the_ts_itself_warmups_and_dropsets_are_left_out(self):
        sets = [S(145, 1, 7.0, is_ts=1), S(60, 5, 7.0, set_type="warmup"), S(100, 5, 7.0, set_type="dropset"), S(128, 5, 7.0)]
        out = rpe_observed.build_observed(sets, [ts(DAY1)], chart)
        self.assertEqual(1, out["sets_used"])
        self.assertEqual(1, len(out["cells"]))

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

    def test_lists_movements_that_have_working_sets_with_an_rpe(self):
        self._log("tpl-squat", "Squat", [
            {"type": "warmup", "weight_kg": 60, "reps": 5, "rpe": None},
            {"type": "normal", "weight_kg": 120, "reps": 5, "rpe": 5},
            {"type": "normal", "weight_kg": 128, "reps": 5, "rpe": 7},
        ])
        self._log("tpl-row", "Row", [{"type": "normal", "weight_kg": 80, "reps": 5, "rpe": None}])   # no RPE: not listed
        got = self.client.get("/rpe-observed").json()
        self.assertEqual([{"exercise_template_id": "tpl-squat", "title": "Squat", "sets": 2, "sessions": 1}], got)

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
