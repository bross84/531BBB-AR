"""The front door: / sends you to the workout log; the original app is kept, unchanged, at /legacy."""
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


class TestFrontDoor(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["DB_PATH"] = os.path.join(self.tmp, "test.db")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.client = TestClient(main.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_root_redirects_to_the_log_page(self):
        r = self.client.get("/", follow_redirects=False)
        self.assertIn(r.status_code, (302, 307))
        self.assertEqual("/log", r.headers["location"])

    def test_original_app_is_still_served_at_legacy(self):
        r = self.client.get("/legacy")
        self.assertEqual(200, r.status_code)
        self.assertIn("531 BBB-AR", r.text)

    def test_recent_page_links_to_the_log_page_and_back(self):
        self.assertIn('href="/log"', self.client.get("/recent").text)
        self.assertIn('href="/recent"', self.client.get("/log").text)

    def test_pages_tell_browsers_to_recheck_instead_of_reusing_a_stored_copy(self):
        for path in ("/log", "/recent", "/legacy"):
            self.assertEqual("no-cache", self.client.get(path).headers["cache-control"], path)
        self.assertEqual("no-cache", self.client.get("/", follow_redirects=False).headers["cache-control"])


if __name__ == "__main__":
    unittest.main()
