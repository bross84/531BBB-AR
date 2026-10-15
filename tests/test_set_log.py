"""Tests for set_log: every set of a saved workout is kept locally, with the RPE as typed."""
import os
import shutil
import sys
import tempfile
import unittest
import warnings
from unittest import mock

warnings.filterwarnings("ignore", category=ResourceWarning)

_IMPORT_DIR = tempfile.mkdtemp()
os.environ.setdefault("DB_PATH", os.path.join(_IMPORT_DIR, "import.db"))

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
import set_log  # noqa: E402

START = "2026-10-15T23:00:00.000Z"
ENTRY = {
    "title": "Day 1",
    "start_time": START,
    "end_time": "2026-10-16T00:10:00.000Z",
    "exercises": [
        {
            "exercise_template_id": "tpl-squat",
            "title": "Squat (Barbell)",
            "sets": [
                {"type": "warmup", "weight_kg": 60, "reps": 5, "rpe": None},
                {"type": "normal", "weight_kg": 140, "reps": 1, "rpe": 8, "ts": True},
                {"type": "normal", "weight_kg": 110, "reps": 5, "rpe": 5},   # below what Hevy can store
            ],
        },
        {
            "exercise_template_id": "tpl-bench",
            "title": "Bench Press (Barbell)",
            "sets": [{"type": "normal", "weight_kg": 100, "reps": 3, "rpe": 6.5}],
        },
    ],
}


class TestRowsFromEntry(unittest.TestCase):

    def test_one_row_per_set_numbered_within_each_exercise(self):
        rows = set_log.rows_from_entry(ENTRY, "h1")
        self.assertEqual(4, len(rows))
        self.assertEqual([1, 2, 3, 1], [r["set_number"] for r in rows])
        self.assertEqual(["tpl-squat"] * 3 + ["tpl-bench"], [r["exercise_template_id"] for r in rows])

    def test_keeps_the_rpe_hevy_cannot_store(self):
        rows = set_log.rows_from_entry(ENTRY, "h1")
        self.assertEqual([None, 8, 5, 6.5], [r["rpe"] for r in rows])

    def test_flags_the_ts_and_carries_the_workout_fields(self):
        rows = set_log.rows_from_entry(ENTRY, "h1")
        self.assertEqual([0, 1, 0, 0], [r["is_ts"] for r in rows])
        self.assertEqual(("h1", "Day 1", START, "warmup"), (rows[0]["hevy_workout_id"], rows[0]["workout_title"], rows[0]["workout_start"], rows[0]["set_type"]))


class SetLogRouteCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["DB_PATH"] = os.path.join(self.tmp, "test.db")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.client = TestClient(main.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        patcher = mock.patch("main.hevy_client.HevyClient")
        self.hevy = patcher.start().return_value
        self.addCleanup(patcher.stop)
        self.hevy.create_workout.return_value = {"id": "hevy-123"}


class TestSavingAWorkoutKeepsItsSets(SetLogRouteCase):

    def test_sets_are_recorded_once_hevy_has_the_workout(self):
        r = self.client.post("/hevy/workouts", json=ENTRY)
        self.assertEqual(200, r.status_code, r.text)
        squat = set_log.for_exercise("tpl-squat")
        self.assertEqual(3, len(squat))
        self.assertEqual("hevy-123", squat[0]["hevy_workout_id"])
        self.assertEqual([None, 8.0, 5.0], [s["rpe"] for s in squat])
        self.assertEqual([0, 1, 0], [s["is_ts"] for s in squat])
        self.assertEqual(1, len(set_log.for_exercise("tpl-bench")))

    def test_nothing_is_recorded_when_hevy_rejects_the_workout(self):
        self.hevy.create_workout.side_effect = RuntimeError("down")
        with self.assertRaises(RuntimeError):
            self.client.post("/hevy/workouts", json=ENTRY)
        self.assertEqual([], set_log.for_exercise("tpl-squat"))

    def test_a_failure_to_record_does_not_fail_the_save(self):
        with mock.patch("main.set_log.record", side_effect=RuntimeError("disk full")):
            with self.assertLogs("main", level="ERROR"):
                r = self.client.post("/hevy/workouts", json=ENTRY)
        self.assertEqual(200, r.status_code, r.text)
        self.assertEqual("hevy-123", r.json()["id"])


if __name__ == "__main__":
    unittest.main()
