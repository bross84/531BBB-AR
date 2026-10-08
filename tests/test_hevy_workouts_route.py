"""Tests for GET /hevy/workouts and the /recent page route. The Hevy client is mocked: no network."""
import os
import shutil
import sys
import tempfile
import unittest
import warnings
from unittest import mock

import httpx
from cryptography.fernet import InvalidToken

warnings.filterwarnings("ignore", category=ResourceWarning)

_IMPORT_DIR = tempfile.mkdtemp()
os.environ.setdefault("DB_PATH", os.path.join(_IMPORT_DIR, "import.db"))

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

RAW_PAGE = {
    "page": 1,
    "page_count": 3,
    "workouts": [
        {
            "id": "w1",
            "title": "Day 1",
            "start_time": "2026-09-30T17:00:00+00:00",
            "end_time": "2026-09-30T17:58:00+00:00",
            "exercises": [
                {
                    "index": 0,
                    "title": "Squat (Barbell)",
                    "exercise_template_id": "tpl-squat",
                    "sets": [{"index": 0, "type": "normal", "weight_kg": 120, "reps": 5, "rpe": 6}],
                }
            ],
        }
    ],
}


def _status_error(code):
    request = httpx.Request("GET", "https://api.hevyapp.com/v1/workouts")
    return httpx.HTTPStatusError("boom", request=request, response=httpx.Response(code, request=request))


class WorkoutsRouteCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["DB_PATH"] = os.path.join(self.tmp, "test.db")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.client = TestClient(main.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

        patcher = mock.patch("main.hevy_client.HevyClient")
        self.hevy_cls = patcher.start()
        self.addCleanup(patcher.stop)
        self.hevy = self.hevy_cls.return_value
        self.hevy.list_workouts.return_value = RAW_PAGE


class TestListHevyWorkouts(WorkoutsRouteCase):

    def test_returns_summarised_page(self):
        r = self.client.get("/hevy/workouts")
        self.assertEqual(200, r.status_code, r.text)
        body = r.json()
        self.assertEqual((1, 3), (body["page"], body["page_count"]))
        w = body["workouts"][0]
        self.assertEqual(("w1", "Day 1", 58, 1), (w["id"], w["title"], w["duration_minutes"], w["working_sets"]))
        s = w["exercises"][0]["sets"][0]
        self.assertEqual((120.0, 264.6, 5, 6.0), (s["weight_kg"], s["weight_lb"], s["reps"], s["rpe"]))

    def test_passes_paging_through_to_hevy(self):
        self.client.get("/hevy/workouts?page=2&page_size=5")
        self.hevy.list_workouts.assert_called_once_with(page=2, page_size=5)

    def test_page_size_over_hevy_maximum_is_rejected(self):
        self.assertEqual(422, self.client.get("/hevy/workouts?page_size=11").status_code)

    def test_page_zero_is_rejected(self):
        self.assertEqual(422, self.client.get("/hevy/workouts?page=0").status_code)

    def test_empty_account(self):
        self.hevy.list_workouts.return_value = {"page": 1, "page_count": 1, "workouts": []}
        body = self.client.get("/hevy/workouts").json()
        self.assertEqual([], body["workouts"])

    def test_no_api_key_is_a_400_with_the_reason(self):
        self.hevy_cls.side_effect = ValueError("No Hevy API key configured.")
        r = self.client.get("/hevy/workouts")
        self.assertEqual(400, r.status_code)
        self.assertIn("No Hevy API key", r.json()["detail"])

    def test_undecryptable_stored_key_is_a_400(self):
        self.hevy_cls.side_effect = InvalidToken()
        r = self.client.get("/hevy/workouts")
        self.assertEqual(400, r.status_code)
        self.assertIn("Save it again", r.json()["detail"])

    def test_hevy_rejecting_the_key_is_a_502_that_mentions_the_key(self):
        self.hevy.list_workouts.side_effect = _status_error(401)
        r = self.client.get("/hevy/workouts")
        self.assertEqual(502, r.status_code)
        self.assertIn("rejected the API key", r.json()["detail"])

    def test_other_hevy_errors_are_a_502_with_the_status(self):
        self.hevy.list_workouts.side_effect = _status_error(500)
        r = self.client.get("/hevy/workouts")
        self.assertEqual(502, r.status_code)
        self.assertIn("500", r.json()["detail"])

    def test_network_failure_is_a_502(self):
        self.hevy.list_workouts.side_effect = httpx.ConnectError("down")
        r = self.client.get("/hevy/workouts")
        self.assertEqual(502, r.status_code)
        self.assertIn("reach Hevy", r.json()["detail"])


class TestRecentPage(WorkoutsRouteCase):

    def test_recent_page_is_served(self):
        r = self.client.get("/recent")
        self.assertEqual(200, r.status_code)
        self.assertIn("Recent workouts", r.text)


if __name__ == "__main__":
    unittest.main()
