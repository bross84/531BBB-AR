"""Per-movement settings, the RPE table endpoint, and the exercise-state endpoint the log page reads."""
import csv
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import warnings
from unittest import mock

import httpx

warnings.filterwarnings("ignore", category=ResourceWarning)

_IMPORT_DIR = tempfile.mkdtemp()
os.environ.setdefault("DB_PATH", os.path.join(_IMPORT_DIR, "import.db"))

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient  # noqa: E402

import database  # noqa: E402
import main  # noqa: E402

USER_CSV = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "rpe_chart_user.csv")


class RefsCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        env = mock.patch.dict(os.environ, {"DB_PATH": os.path.join(self.tmp, "t.db"), "RPE_CHART_PATH": USER_CSV})
        env.start()
        self.addCleanup(env.stop)
        self.client = TestClient(main.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)


class TestMovementSettings(RefsCase):

    def test_starts_empty(self):
        self.assertEqual([], self.client.get("/exercise-refs").json())

    def test_defaults_are_e1rm_last_set_on_and_95_percent(self):
        r = self.client.put("/exercise-refs/tpl-bench", json={})
        self.assertEqual(
            {"exercise_template_id": "tpl-bench", "basis": "e1rm", "ls": True, "tm_pct": 0.95}, r.json()
        )

    def test_save_and_list(self):
        r = self.client.put("/exercise-refs/tpl-squat", json={"basis": "tm", "ls": False, "tm_pct": 0.9})
        self.assertEqual(200, r.status_code, r.text)
        expected = {"exercise_template_id": "tpl-squat", "basis": "tm", "ls": False, "tm_pct": 0.9}
        self.assertEqual(expected, r.json())
        self.assertEqual([expected], self.client.get("/exercise-refs").json())

    def test_saving_again_updates_instead_of_duplicating(self):
        self.client.put("/exercise-refs/tpl-squat", json={"basis": "tm"})
        self.client.put("/exercise-refs/tpl-squat", json={"basis": "e1rm", "ls": False})
        rows = self.client.get("/exercise-refs").json()
        self.assertEqual(1, len(rows))
        self.assertEqual(("e1rm", False), (rows[0]["basis"], rows[0]["ls"]))

    def test_movements_are_kept_apart(self):
        self.client.put("/exercise-refs/a", json={"basis": "tm"})
        self.client.put("/exercise-refs/b", json={"basis": "e1rm"})
        self.assertEqual(
            {"a": "tm", "b": "e1rm"},
            {r["exercise_template_id"]: r["basis"] for r in self.client.get("/exercise-refs").json()},
        )

    def test_rejects_unknown_basis_and_silly_tm_percentages(self):
        for bad in ({"basis": "percent"}, {"tm_pct": 0.2}, {"tm_pct": 1.5}):
            self.assertEqual(422, self.client.put("/exercise-refs/x", json=bad).status_code, bad)

    def test_a_database_from_the_earlier_version_gains_the_new_columns(self):
        path = os.environ["DB_PATH"]
        conn = sqlite3.connect(path)
        conn.execute("DROP TABLE exercise_refs")
        conn.execute(
            "CREATE TABLE exercise_refs (exercise_template_id TEXT PRIMARY KEY, e1rm_lb REAL, tm_lb REAL,"
            " basis TEXT NOT NULL DEFAULT 'e1rm', auto INTEGER NOT NULL DEFAULT 0, updated_at DATETIME)"
        )
        conn.execute("INSERT INTO exercise_refs (exercise_template_id, basis) VALUES ('old', 'tm')")
        conn.commit()
        conn.close()
        database.init_db()
        self.assertEqual(
            [{"exercise_template_id": "old", "basis": "tm", "ls": True, "tm_pct": 0.95}],
            self.client.get("/exercise-refs").json(),
        )


class TestRpeTableEndpoint(RefsCase):

    def test_serves_the_users_table(self):
        rows = self.client.get("/rpe-table").json()["rows"]
        with open(USER_CSV, newline="", encoding="utf-8") as f:
            expected = sum(1 for _ in csv.DictReader(f))
        self.assertEqual(expected, len(rows))
        by_pair = {(r[0], int(r[1])): r[2] for r in rows}
        self.assertAlmostEqual(0.826, by_pair[(8.0, 5)], places=4)
        self.assertEqual(1.0, by_pair[(10.0, 1)])


def _entry(workout, start, set_type, kg, reps, rpe, title):
    return {
        "workout_id": workout, "workout_title": title, "workout_start_time": start,
        "set_type": set_type, "weight_kg": kg, "reps": reps, "rpe": rpe,
    }


class TestExerciseStateEndpoint(RefsCase):

    def setUp(self):
        super().setUp()
        patcher = mock.patch("main.hevy_client.HevyClient")
        self.hevy_cls = patcher.start()
        self.addCleanup(patcher.stop)
        self.hevy = self.hevy_cls.return_value
        self.hevy.exercise_history.return_value = [
            _entry("w1", "2026-09-30T17:00:00+00:00", "warmup", 49.9, 5, None, "BS-Bridge1.3.1"),
            _entry("w1", "2026-09-30T17:00:00+00:00", "normal", 120.2, 5, 6, "BS-Bridge1.3.1"),
            _entry("w1", "2026-09-30T17:00:00+00:00", "normal", 132.45, 5, 8, "BS-Bridge1.3.1"),
        ]

    def test_returns_the_e1rm_and_the_set_it_came_from(self):
        r = self.client.get("/hevy/exercise-state/tpl-squat")
        self.assertEqual(200, r.status_code, r.text)
        body = r.json()
        self.assertTrue(body["found"])
        self.assertEqual(("BS-Bridge1.3.1", 292.0, 5, 8.0), (body["workout_title"], body["set_weight_lb"], body["set_reps"], body["set_rpe"]))
        self.assertEqual(round(292 / 0.826, 1), body["e1rm_lb"])
        self.hevy.exercise_history.assert_called_once_with("tpl-squat")

    def test_no_history_is_found_false_not_an_error(self):
        self.hevy.exercise_history.return_value = []
        r = self.client.get("/hevy/exercise-state/tpl-new")
        self.assertEqual(200, r.status_code)
        self.assertEqual((False, None), (r.json()["found"], r.json()["e1rm_lb"]))

    def test_no_api_key_is_a_400(self):
        self.hevy_cls.side_effect = ValueError("No Hevy API key configured.")
        self.assertEqual(400, self.client.get("/hevy/exercise-state/x").status_code)

    def test_hevy_failure_is_a_502(self):
        self.hevy.exercise_history.side_effect = httpx.ConnectError("down")
        self.assertEqual(502, self.client.get("/hevy/exercise-state/x").status_code)


if __name__ == "__main__":
    unittest.main()
