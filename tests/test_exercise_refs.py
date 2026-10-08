"""Per-exercise e1RM / TM / auto-weight settings, and the RPE table endpoint the log page reads."""
import csv
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


class TestExerciseRefs(RefsCase):

    def test_starts_empty(self):
        self.assertEqual([], self.client.get("/exercise-refs").json())

    def test_save_and_list(self):
        r = self.client.put(
            "/exercise-refs/tpl-squat", json={"e1rm_lb": 344, "tm_lb": 316, "basis": "tm", "auto": True}
        )
        self.assertEqual(200, r.status_code, r.text)
        expected = {"exercise_template_id": "tpl-squat", "e1rm_lb": 344.0, "tm_lb": 316.0, "basis": "tm", "auto": True}
        self.assertEqual(expected, r.json())
        self.assertEqual([expected], self.client.get("/exercise-refs").json())

    def test_defaults_when_nothing_is_sent(self):
        r = self.client.put("/exercise-refs/tpl-bench", json={})
        self.assertEqual(
            {"exercise_template_id": "tpl-bench", "e1rm_lb": None, "tm_lb": None, "basis": "e1rm", "auto": False},
            r.json(),
        )

    def test_saving_again_updates_instead_of_duplicating(self):
        self.client.put("/exercise-refs/tpl-squat", json={"e1rm_lb": 340})
        self.client.put("/exercise-refs/tpl-squat", json={"e1rm_lb": 350, "auto": True})
        rows = self.client.get("/exercise-refs").json()
        self.assertEqual(1, len(rows))
        self.assertEqual((350.0, True), (rows[0]["e1rm_lb"], rows[0]["auto"]))

    def test_e1rm_and_tm_are_separate_numbers_and_the_save_is_a_full_replace(self):
        self.client.put("/exercise-refs/tpl-squat", json={"e1rm_lb": 344, "tm_lb": 316})
        self.client.put("/exercise-refs/tpl-squat", json={"tm_lb": 320})
        row = self.client.get("/exercise-refs").json()[0]
        self.assertEqual((None, 320.0), (row["e1rm_lb"], row["tm_lb"]))

    def test_exercises_are_kept_apart(self):
        self.client.put("/exercise-refs/a", json={"e1rm_lb": 100})
        self.client.put("/exercise-refs/b", json={"e1rm_lb": 200})
        self.assertEqual({"a": 100.0, "b": 200.0}, {r["exercise_template_id"]: r["e1rm_lb"] for r in self.client.get("/exercise-refs").json()})

    def test_rejects_non_positive_numbers_and_unknown_basis(self):
        for bad in ({"e1rm_lb": 0}, {"tm_lb": -5}, {"basis": "percent"}):
            self.assertEqual(422, self.client.put("/exercise-refs/x", json=bad).status_code, bad)


class TestRpeTableEndpoint(RefsCase):

    def test_serves_the_users_table(self):
        rows = self.client.get("/rpe-table").json()["rows"]
        with open(USER_CSV, newline="", encoding="utf-8") as f:
            expected = sum(1 for _ in csv.DictReader(f))
        self.assertEqual(expected, len(rows))
        by_pair = {(r[0], int(r[1])): r[2] for r in rows}
        self.assertAlmostEqual(0.826, by_pair[(8.0, 5)], places=4)
        self.assertEqual(1.0, by_pair[(10.0, 1)])


if __name__ == "__main__":
    unittest.main()
