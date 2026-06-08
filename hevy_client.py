import logging
import os

import httpx
from cryptography.fernet import Fernet

from database import get_db

logger = logging.getLogger(__name__)

_fernet = Fernet(os.environ["ENCRYPTION_KEY"].encode())

_BASE_URL = "https://api.hevyapp.com/v1"
_SETTINGS_KEY = "hevy_api_key"


def _encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    return _fernet.decrypt(value.encode()).decode()


def save_api_key(raw_key: str) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_SETTINGS_KEY, _encrypt(raw_key)),
        )


def _load_api_key() -> str | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (_SETTINGS_KEY,)
        ).fetchone()
    if row is None:
        return None
    return _decrypt(row["value"])


class HevyClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or _load_api_key()

    def _headers(self) -> dict:
        if not self.api_key:
            raise ValueError("No Hevy API key configured.")
        return {"api-key": self.api_key}

    def sync_exercise_cache(self) -> int:
        """Fetch all exercise templates from Hevy and upsert into hevy_exercise_cache."""
        exercises: list[dict] = []
        page = 1
        with httpx.Client(timeout=30) as client:
            while True:
                resp = client.get(
                    f"{_BASE_URL}/exercise_templates",
                    headers=self._headers(),
                    params={"page": page, "pageSize": 100},
                )
                resp.raise_for_status()
                data = resp.json()
                exercises.extend(data.get("exercise_templates", []))
                if page >= data.get("page_count", 1):
                    break
                page += 1

        with get_db() as conn:
            conn.executemany(
                """
                INSERT INTO hevy_exercise_cache (id, title, primary_muscle)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    primary_muscle = excluded.primary_muscle,
                    cached_at = CURRENT_TIMESTAMP
                """,
                [
                    (e["id"], e["title"], e.get("primary_muscle_group"))
                    for e in exercises
                ],
            )

        return len(exercises)

    def post_workout(self, payload: dict) -> str | None:
        """Post a completed session to Hevy. Returns the Hevy workout ID or None on failure."""
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{_BASE_URL}/workouts",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json().get("workout", {}).get("id")
        except Exception:
            logger.exception("Hevy write-back failed — session already saved to local DB.")
            return None
