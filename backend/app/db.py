"""SQLite storage for personal progress. One file, no server."""
from __future__ import annotations

import sqlite3
import time
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
CREATE TABLE IF NOT EXISTS explain_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id TEXT NOT NULL,
    words INTEGER NOT NULL,
    verdict TEXT NOT NULL,            -- correct | partly | wrong (technical)
    english_ok INTEGER NOT NULL,      -- 1 if the AI found no English mistakes
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
    ("exam_sessions", "domains", "TEXT NOT NULL DEFAULT '{}'"),  # JSON: {domain: {correct, total}}
    ("attempts", "read_seconds", "REAL"),      # practice: question shown -> first option picked
    ("attempts", "answer_seconds", "REAL"),    # practice: question shown -> "Check answer"
    ("attempts", "words", "INTEGER"),          # words in the question and its options
]


# What the "Your data" panel counts: label -> SQL
SUMMARY = {
    "answers": "SELECT COUNT(*) FROM attempts",
    "mock_exams": "SELECT COUNT(*) FROM exam_sessions WHERE finished_at IS NOT NULL",
    "lab_attempts": "SELECT COUNT(*) FROM lab_attempts",
    "lab_mock_exams": "SELECT COUNT(*) FROM mock_sessions WHERE finished_at IS NOT NULL",
    "interview_answers": "SELECT COUNT(*) FROM interview_attempts",
    "english_words": "SELECT COUNT(*) FROM vocab_cards",
    "explanations_written": "SELECT COUNT(*) FROM explain_attempts",
    "passed_certifications": "SELECT COUNT(*) FROM earned_certs",
}
MAX_IMPORT_BYTES = 200 * 1024 * 1024


class ProgressFileError(ValueError):
    """The uploaded file is not a progress file of this app."""


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            for table, column, definition in MIGRATIONS:
                cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
                if column not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    # ---------- export / import of the whole progress file ----------

    def summary(self) -> dict:
        with self.connect() as conn:
            return {k: conn.execute(q).fetchone()[0] for k, q in SUMMARY.items()}

    def export_bytes(self) -> bytes:
        """A consistent copy of the whole database (safe while the app is writing)."""
        with self.connect() as conn:
            return conn.serialize()

    def import_bytes(self, data: bytes) -> Path:
        """Replace all progress with an exported file. The current progress is saved first in
        backups/ next to the database; returns that backup's path."""
        if len(data) > MAX_IMPORT_BYTES:
            raise ProgressFileError("The file is too large to be a progress file.")
        if not data.startswith(b"SQLite format 3\x00"):
            raise ProgressFileError("This is not a progress file (k8s-study-lab-progress-….db).")
        src = sqlite3.connect(":memory:")
        try:
            try:
                src.deserialize(data)
                ok = src.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            except sqlite3.DatabaseError as e:
                raise ProgressFileError(f"The file is damaged: {e}") from e
            if not ok:
                raise ProgressFileError("The file is damaged (integrity check failed).")
            if not {"attempts", "cards"} <= tables:
                raise ProgressFileError("This SQLite file is not a k8s-study-lab progress file.")
            backups = self.path.parent / "backups"
            backups.mkdir(exist_ok=True)
            backup = backups / f"progress-before-import-{time.strftime('%Y%m%d-%H%M%S')}.db"
            b = sqlite3.connect(backup)
            try:
                with self.connect() as live:
                    live.backup(b)
            finally:
                b.close()
            with self.connect() as live:
                src.backup(live)          # page-by-page copy into the live file
        finally:
            src.close()
        self.migrate()                    # an older export gets the newer tables and columns
        return backup

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
