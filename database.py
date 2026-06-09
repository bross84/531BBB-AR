import sqlite3
import os


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(os.environ["DB_PATH"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS programs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                total_weeks INTEGER NOT NULL,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER NOT NULL REFERENCES programs(id),
                name TEXT NOT NULL,
                behaviour TEXT NOT NULL CHECK(behaviour IN ('percentage','fixed','progression','free')),
                display_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER NOT NULL REFERENCES programs(id),
                cycle_number INTEGER NOT NULL,
                label TEXT
            );

            CREATE TABLE IF NOT EXISTS days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                block_id INTEGER NOT NULL REFERENCES blocks(id),
                day_number INTEGER NOT NULL,
                label TEXT
            );

            CREATE TABLE IF NOT EXISTS exercise_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_id INTEGER NOT NULL REFERENCES days(id),
                tier_id INTEGER NOT NULL REFERENCES tiers(id),
                hevy_exercise_id TEXT NOT NULL,
                hevy_exercise_name TEXT NOT NULL,
                slot_order INTEGER NOT NULL DEFAULT 0,
                wave_params TEXT,
                target_rpe REAL
            );

            CREATE TABLE IF NOT EXISTS active_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER NOT NULL REFERENCES programs(id),
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                current_cycle INTEGER NOT NULL DEFAULT 1,
                current_day INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK(status IN ('active','completed','abandoned'))
            );

            CREATE TABLE IF NOT EXISTS session_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                active_block_id INTEGER NOT NULL REFERENCES active_blocks(id),
                exercise_slot_id INTEGER NOT NULL REFERENCES exercise_slots(id),
                week_number INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                set_number INTEGER NOT NULL,
                set_type TEXT NOT NULL,
                planned_weight_kg REAL,
                actual_weight_kg REAL,
                reps INTEGER,
                target_rpe REAL,
                actual_rpe REAL,
                hevy_workout_id TEXT,
                logged_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS e1rm_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                active_block_id INTEGER NOT NULL REFERENCES active_blocks(id),
                exercise_slot_id INTEGER NOT NULL REFERENCES exercise_slots(id),
                e1rm_kg REAL NOT NULL,
                source TEXT NOT NULL
                    CHECK(source IN ('amrap','joker_avg','manual')),
                logged_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS hevy_exercise_cache (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                primary_muscle TEXT,
                cached_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
