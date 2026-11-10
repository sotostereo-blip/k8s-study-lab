"""Spaced repetition with a simple Leitner system.

Correct answer -> move up one box. Wrong answer -> back to box 1.
Each box has a review interval; failed questions come back the same day.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

INTERVAL_DAYS = {1: 0, 2: 1, 3: 3, 4: 7, 5: 14}
MAX_BOX = max(INTERVAL_DAYS)


def next_box(box: int, correct: bool) -> int:
    return min(box + 1, MAX_BOX) if correct else 1


def due_at(box: int, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return (now + timedelta(days=INTERVAL_DAYS[box])).strftime("%Y-%m-%d %H:%M:%S")
