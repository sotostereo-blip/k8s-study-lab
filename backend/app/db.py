"""SQLite storage for personal progress. One file, no server."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id TEXT NOT NULL,
    selected TEXT NOT NULL,
    correct INTEGER NOT NULL,
    mode TEXT NOT NULL,              -- practice | exam
    used_translation INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS cards (
    question_id TEXT PRIMARY KEY,
    box INTEGER NOT NULL DEFAULT 1,   -- Leitner box 1..5
    due_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS exam_sessions (
    id TEXT PRIMARY KEY,
    exam_id TEXT NOT NULL,
    question_ids TEXT NOT NULL,       -- JSON list
    minutes INTEGER NOT NULL,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    score REAL
);
CREATE TABLE IF NOT EXISTS english_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,               -- glossary_lookup | translation
    ref TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS lab_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    passed INTEGER NOT NULL,          -- 1 if every check passed
    checks_passed INTEGER NOT NULL,
    checks_total INTEGER NOT NULL,
    seconds INTEGER,                  -- time since the lab was ready
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS vocab_cards (
    item_id TEXT PRIMARY KEY,         -- term:<glossary id> | word:<vocabulary id>
    box INTEGER NOT NULL DEFAULT 1,   -- Leitner box 1..5
    due_at TEXT NOT NULL DEFAULT (datetime('now')),
    correct INTEGER NOT NULL DEFAULT 0,
    wrong INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mock_sessions (
    id TEXT PRIMARY KEY,
    track_id TEXT NOT NULL,
    task_ids TEXT NOT NULL,           -- JSON list
    minutes INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    score REAL,                       -- NULL when abandoned
    results TEXT                      -- JSON, per task
);
CREATE TABLE IF NOT EXISTS interview_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id TEXT NOT NULL,
    covered INTEGER NOT NULL,         -- key points covered (self check)
    total INTEGER NOT NULL,           -- key points of the question
    seconds INTEGER,                  -- speaking time
    words INTEGER,                    -- words in the answer (transcript or typed)
    mode TEXT NOT NULL,               -- practice | mock
    session_id TEXT,                  -- interview_sessions.id for a mock interview
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS interview_cards (
    question_id TEXT PRIMARY KEY,
    box INTEGER NOT NULL DEFAULT 1,   -- Leitner box 1..5
    due_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS study_goals (
    cert_id TEXT PRIMARY KEY,
    exam_date TEXT NOT NULL,          -- YYYY-MM-DD
    minutes_per_day INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (date('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS earned_certs (
    cert_id TEXT PRIMARY KEY,
    passed_on TEXT NOT NULL,          -- YYYY-MM-DD
    expires_on TEXT                   -- YYYY-MM-DD from the certificate; NULL = passed_on + valid_years
);
CREATE TABLE IF NOT EXISTS interview_sessions (
    id TEXT PRIMARY KEY,
    question_ids TEXT NOT NULL,       -- JSON list
    minutes INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    score REAL
);
"""

# Columns added after the first release: (table, column, definition). Added when missing.
MIGRATIONS = [
    ("exam_sessions", "domc", "TEXT NOT NULL DEFAULT '[]'"),   # JSON list of question ids shown as DOMC
    ("exam_sessions", "conditions", "TEXT NOT NULL DEFAULT '{}'"),  # JSON: {"real": bool, "esl": bool}
]


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            for table, column, definition in MIGRATIONS:
                cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
                if column not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
