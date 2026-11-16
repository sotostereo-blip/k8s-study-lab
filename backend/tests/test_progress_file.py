import os
import sqlite3
from pathlib import Path

os.environ["K8S_LAB_NO_AUTOAPP"] = "1"
os.environ["AI_FEEDBACK"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402

CONTENT = Path(__file__).resolve().parents[2] / "content"


def answer(c, qid="kcna-fund-001"):
    c.post("/api/practice/answer", json={"question_id": qid, "selected": ["a"]})


def test_export_then_import_on_another_machine(tmp_path):
    a = TestClient(create_app(CONTENT, tmp_path / "a" / "progress.db"))
    answer(a)
    answer(a)
    r = a.get("/api/progress/export")
    assert r.status_code == 200 and r.content.startswith(b"SQLite format 3")
    assert "attachment" in r.headers["content-disposition"]

    b = TestClient(create_app(CONTENT, tmp_path / "b" / "progress.db"))
    answer(b)   # progress on the second machine is replaced, but kept in a backup
    out = b.post("/api/progress/import", content=r.content,
                 headers={"Content-Type": "application/octet-stream"}).json()
    assert out["summary"]["answers"] == 2
    assert b.get("/api/progress/summary").json()["answers"] == 2
    backup = tmp_path / "b" / "backups" / out["backup"]
    assert sqlite3.connect(backup).execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 1
    answer(b)   # the app keeps working on the imported file
    assert b.get("/api/progress/summary").json()["answers"] == 3


def test_import_of_an_old_export_gets_new_columns(tmp_path):
    old = tmp_path / "old.db"
    with sqlite3.connect(old) as conn:   # first-release schema: no DOMC columns, few tables
        conn.executescript("CREATE TABLE attempts (id INTEGER PRIMARY KEY, question_id TEXT, selected TEXT,"
                           " correct INTEGER, mode TEXT, used_translation INTEGER DEFAULT 0, created_at TEXT);"
                           "CREATE TABLE cards (question_id TEXT PRIMARY KEY, box INTEGER, due_at TEXT);"
                           "CREATE TABLE exam_sessions (id TEXT PRIMARY KEY, exam_id TEXT, question_ids TEXT,"
                           " minutes INTEGER, started_at TEXT, finished_at TEXT, score REAL);")
    c = TestClient(create_app(CONTENT, tmp_path / "progress.db"))
    assert c.post("/api/progress/import", content=old.read_bytes()).status_code == 200
    assert c.get("/api/progress/summary").json()["passed_certifications"] == 0
    assert c.post("/api/exam/start", json={"exam_id": "kcna", "n": 5}).status_code == 200


def test_import_rejects_other_files(tmp_path):
    c = TestClient(create_app(CONTENT, tmp_path / "progress.db"))
    answer(c)
    assert c.post("/api/progress/import", content=b"hello").status_code == 400
    other = tmp_path / "other.db"
    sqlite3.connect(other).execute("CREATE TABLE notes (x)").connection.commit()
    r = c.post("/api/progress/import", content=other.read_bytes())
    assert r.status_code == 400 and "not a k8s-study-lab" in r.json()["detail"]
    assert c.get("/api/progress/summary").json()["answers"] == 1   # nothing changed
