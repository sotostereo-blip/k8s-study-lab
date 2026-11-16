import os
from pathlib import Path

os.environ["K8S_LAB_NO_AUTOAPP"] = "1"
os.environ["AI_FEEDBACK"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app import reading  # noqa: E402
from app.content import load_library  # noqa: E402
from app.main import create_app  # noqa: E402

CONTENT = Path(__file__).resolve().parents[2] / "content"
LIB = load_library(CONTENT)


def test_words_count_question_and_options():
    q = LIB.questions["kcna-fund-001"]
    n = reading.words(q)
    assert n > len(q.question.split()) and n < 400


def test_pace_needs_ten_answers_and_ignores_noise():
    exam = LIB.exams["kcna"]                      # 90 min / 60 questions = 90 s per question
    row = {"words": 60, "read_seconds": 20, "answer_seconds": 40}    # 180 wpm, 40 s
    noise = {"words": 60, "read_seconds": 0.5, "answer_seconds": 1000}
    few = reading.pace([row] * 5 + [noise], exam)
    assert few["wpm"] == 180 and few["verdict"] == "unknown" and few["budget_seconds"] == 90
    assert reading.pace([row] * 12, exam)["verdict"] == "good"
    slow = {"words": 60, "read_seconds": 50, "answer_seconds": 100}    # 72 wpm, over the budget
    assert reading.pace([slow] * 12, exam)["verdict"] == "slow"
    watch = {"words": 60, "read_seconds": 40, "answer_seconds": 60}    # 90 wpm, in time
    assert reading.pace([watch] * 12, exam)["verdict"] == "watch"


def test_practice_answer_reports_reading_pace(tmp_path):
    c = TestClient(create_app(CONTENT, tmp_path / "p.db"))
    q = LIB.questions["kcna-fund-001"]
    r = c.post("/api/practice/answer", json={"question_id": q.id, "selected": q.answer,
                                             "read_seconds": 15, "answer_seconds": 22}).json()
    assert r["reading"]["wpm"] == reading.wpm(reading.words(q), 15) and r["reading"]["answer_seconds"] == 22
    plain = c.post("/api/practice/answer", json={"question_id": q.id, "selected": q.answer}).json()
    assert "reading" not in plain                 # old clients still work
    p = c.get("/api/reading?exam_id=kcna").json()
    assert p["samples"] == 1 and p["answer_seconds"] == 22
