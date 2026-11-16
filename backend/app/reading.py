"""Reading speed in exam English: how fast you read a question and how long you take to answer,
compared with the time the real exam gives per question. Pure functions (tested in test_reading)."""
from __future__ import annotations

import re
from statistics import median

from .content import Exam, Question

MIN_SECONDS, MAX_SECONDS = 2, 600      # outside this, the timing is noise (a click by mistake, a break)
RECENT = 50                            # answers used for the current pace
COMFORT_WPM = 150                      # a comfortable pace for exam reading in a second language


def words(q: Question) -> int:
    """Words you read before you can answer: the question and every option."""
    text = " ".join([q.question] + [o.text for o in q.options])
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.\-/]*", text))


def wpm(n_words: int, seconds: float) -> int:
    return round(n_words * 60 / seconds)


def pace(rows: list[dict], exam: Exam) -> dict:
    """rows: recent answers, newest first, with read_seconds, answer_seconds and words."""
    read = [r for r in rows if r["read_seconds"] and MIN_SECONDS <= r["read_seconds"] <= MAX_SECONDS][:RECENT]
    answer = [r for r in rows if r["answer_seconds"] and MIN_SECONDS <= r["answer_seconds"] <= MAX_SECONDS][:RECENT]
    budget = round(exam.exam_minutes * 60 / exam.exam_questions)
    out = {"samples": len(read), "budget_seconds": budget, "comfort_wpm": COMFORT_WPM,
           "wpm": None, "answer_seconds": None, "verdict": "unknown"}
    if read:
        out["wpm"] = round(median(wpm(r["words"], r["read_seconds"]) for r in read))
    if answer:
        out["answer_seconds"] = round(median(r["answer_seconds"] for r in answer))
    if len(read) >= 10 and out["answer_seconds"] is not None:
        slow_read = out["wpm"] < COMFORT_WPM * 0.8
        over = out["answer_seconds"] > budget
        out["verdict"] = "slow" if over else "watch" if slow_read or out["answer_seconds"] > budget * 0.8 else "good"
    return out
