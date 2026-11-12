"""Readiness score and a daily study plan for one certification.

Pure functions: main.py reads the progress from the database into `Part` objects, and this
module turns them into an estimated exam score and the work for today.

A certification has one to three parts: the multiple-choice question bank ("exam"), the
hands-on labs ("labs") and job interview practice ("interview"). The *main* part is the one
that looks like the real exam (labs for a performance-based exam, else the question bank).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

# Chance of answering a multiple-choice question right, by Leitner box (0 = never seen).
# A never-seen question still has a guessing chance on the real exam.
EXAM_RECALL = {0: 0.25, 1: 0.4, 2: 0.6, 3: 0.75, 4: 0.85, 5: 0.95}
# Interview answers: no guessing, the key points come from practice.
INTERVIEW_RECALL = {0: 0.0, 1: 0.35, 2: 0.55, 3: 0.7, 4: 0.85, 5: 0.95}
LAB_FAST, LAB_SLOW = 1.0, 0.7   # solved within the target time / solved slower
MOCK_WEIGHT = 0.6               # mock exams say more about the real exam than the practice bank
MAIN_WEIGHT = 0.75              # main part vs the other part, for a certification with both
RECENT_MOCKS = 3
MOCK_NAMES = {"exam": "a multiple-choice mock exam", "labs": "a hands-on mock exam", "interview": "a mock interview"}
FINAL_DAYS = 7                  # last week: mock exams and reviews
PRACTICE_DAYS = 21              # three weeks before the exam: more mock exams
MOCK_EVERY = {"learn": 7, "practice": 3, "final": 2}


@dataclass
class Item:
    """One question or lab task."""
    id: str
    title: str
    level: float          # 0..1, see the RECALL tables
    seen: bool
    minutes: float        # time to study it the first time
    difficulty: int = 1


@dataclass
class DomainProgress:
    id: str
    name: str
    weight: float
    items: list[Item]

    @property
    def strength(self) -> float:
        return sum(i.level for i in self.items) / len(self.items) if self.items else 0.0

    @property
    def unseen(self) -> list[Item]:
        return [i for i in self.items if not i.seen]


@dataclass
class Mock:
    score: float
    day: date


@dataclass
class Part:
    kind: str                  # exam | labs | interview
    name: str
    passing: float
    mock_minutes: int
    domains: list[DomainProgress]
    mocks: list[Mock] = field(default_factory=list)   # most recent first
    due: int = 0               # spaced repetition reviews due now
    done_today: int = 0        # questions answered / labs solved / interview answers today
    mock_today: bool = False

    @property
    def items(self) -> list[Item]:
        return [i for d in self.domains for i in d.items]

    @property
    def bank_score(self) -> float:
        """Estimated score from practice alone, following the domain weights (0..100)."""
        total = sum(d.weight for d in self.domains if d.items)
        return 100 * sum(d.weight * d.strength for d in self.domains if d.items) / total if total else 0.0

    @property
    def mock_score(self) -> float | None:
        recent = self.mocks[:RECENT_MOCKS]
        return sum(m.score for m in recent) / len(recent) if recent else None

    @property
    def estimate(self) -> float:
        m = self.mock_score
        return self.bank_score if m is None else MOCK_WEIGHT * m + (1 - MOCK_WEIGHT) * self.bank_score

    @property
    def coverage(self) -> float:
        items = self.items
        return sum(i.seen for i in items) / len(items) if items else 0.0

    def priority(self) -> list[DomainProgress]:
        """Domains to study first: high weight and low strength."""
        return sorted((d for d in self.domains if d.items), key=lambda d: -d.weight * (1 - d.strength))


def _round(x: float) -> int:
    return int(round(x))


def readiness(parts: list[Part], main: str) -> dict:
    """Estimated exam score, confidence and a verdict."""
    by_kind = {p.kind: p for p in parts}
    m = by_kind[main]
    others = [p for p in parts if p.kind != main]
    estimate = m.estimate if not others else (
        MAIN_WEIGHT * m.estimate + (1 - MAIN_WEIGHT) * sum(p.estimate for p in others) / len(others))
    mocks = m.mocks
    recent_ok = len(mocks) >= 2 and all(x.score >= m.passing + 5 for x in mocks[:2])
    if not mocks:
        verdict, message = "unknown", "Take a mock exam: without one, this score is only a guess from practice."
    elif estimate >= m.passing + 10 and recent_ok:
        verdict, message = "ready", "You are ready. Your last mock exams pass with a good margin: book the exam."
    elif estimate >= m.passing:
        verdict, message = "almost", "Almost ready. Pass two mock exams in a row with a margin of 5 points or more."
    else:
        verdict, message = "not-yet", f"Not ready yet. Your estimated score is below the {m.passing:g}% you need."
    confidence = "low" if not mocks or m.coverage < 0.5 else "medium" if len(mocks) < 3 or m.coverage < 0.8 else "high"
    return {
        "estimate": _round(estimate),
        "passing": m.passing,
        "verdict": verdict,
        "message": message,
        "confidence": confidence,
        "main": main,
        "parts": [{
            "kind": p.kind, "name": p.name, "estimate": _round(p.estimate), "practice": _round(p.bank_score),
            "mock": None if p.mock_score is None else _round(p.mock_score), "mocks": len(p.mocks),
            "coverage": _round(100 * p.coverage), "passing": p.passing,
            "domains": [{"id": d.id, "name": d.name, "weight": d.weight, "strength": _round(100 * d.strength),
                         "seen": len(d.items) - len(d.unseen), "total": len(d.items)} for d in p.domains if d.items],
        } for p in parts],
        "next_steps": next_steps(parts, main),
    }


def next_steps(parts: list[Part], main: str) -> list[dict]:
    steps: list[dict] = []
    tabs = {"exam": "practice", "labs": "labs", "interview": "interview"}
    mock_tabs = {"exam": "exam", "labs": "labs", "interview": "mock-interview"}
    m = next(p for p in parts if p.kind == main)
    if not m.mocks:
        steps.append({"text": f"Take {MOCK_NAMES[m.kind]} to measure your level.", "tab": mock_tabs[m.kind]})
    for p in parts:
        if p.due:
            steps.append({"text": f"{p.name}: review the {p.due} questions that are due today.", "tab": tabs[p.kind]})
        weak = p.priority()[:1]
        for d in weak:
            if d.strength < 0.85:
                left = len(d.unseen)
                extra = f", {left} not tried yet" if left else ""
                steps.append({"text": f"{p.name}: work on \"{d.name}\" (weight {d.weight:g}%, strength "
                                      f"{_round(100 * d.strength)}%{extra}).", "tab": tabs[p.kind]})
    return steps[:4]


def phase_of(days_left: int) -> str:
    if days_left <= 1:
        return "rest"
    if days_left <= FINAL_DAYS:
        return "final"
    if days_left <= PRACTICE_DAYS:
        return "practice"
    return "learn"


PHASES = {
    "learn": "Learn: try every question and lab once, weakest and heaviest domains first. One mock exam a week.",
    "practice": "Practice: finish what is left, fix weak domains, and take a mock exam every 3 days.",
    "final": "Final week: a mock exam every 2 days and your reviews. Few new topics.",
    "rest": "Exam is tomorrow or today: a short review only, then rest.",
}


def roadmap(start: date, exam_day: date, today: date) -> list[dict]:
    """The phases between today and the exam, with their dates."""
    out = []
    bounds = [("learn", None, exam_day - timedelta(days=PRACTICE_DAYS + 1)),
              ("practice", exam_day - timedelta(days=PRACTICE_DAYS), exam_day - timedelta(days=FINAL_DAYS + 1)),
              ("final", exam_day - timedelta(days=FINAL_DAYS), exam_day - timedelta(days=2)),
              ("rest", exam_day - timedelta(days=1), exam_day)]
    for name, first, last in bounds:
        first = max(first or start, start, today)
        if first <= last:
            out.append({"phase": name, "start": first.isoformat(), "end": last.isoformat(),
                        "current": first <= today <= last, "goal": PHASES[name]})
    return out


def daily_plan(parts: list[Part], main: str, exam_day: date, start: date, today: date,
               minutes_per_day: int) -> dict:
    days_left = (exam_day - today).days
    if days_left < 0:
        return {"days_left": days_left, "phase": "done", "items": [], "minutes": 0,
                "message": "The exam date has passed. Set a new date if you are taking it again.",
                "roadmap": [], "pace": None}
    phase = phase_of(days_left)
    items: list[dict] = []
    tabs = {"exam": "practice", "labs": "labs", "interview": "interview"}
    mock_tabs = {"exam": "exam", "labs": "labs", "interview": "mock-interview"}

    # 1. at most one mock exam a day, when the last one is old enough: the main part first,
    #    the other parts once a week. The first one waits until you have studied a little.
    for p in sorted(parts, key=lambda p: p.kind != main):
        if phase == "rest" or p.mock_minutes <= 0:
            continue
        every = MOCK_EVERY[phase] if p.kind == main else 7
        last = p.mocks[0].day if p.mocks else None
        started = p.coverage >= 0.3 or (today - start).days >= 7 or phase == "final"
        if p.mock_today or (started and (last is None or (today - last).days >= every)):
            items.append({"kind": "mock", "part": p.kind, "tab": mock_tabs[p.kind],
                          "title": MOCK_NAMES[p.kind][2:].capitalize(),
                          "detail": f"{p.mock_minutes} minutes, like the real exam. Review every mistake after.",
                          "minutes": p.mock_minutes, "target": 1, "done": int(p.mock_today)})
            if not p.mock_today:
                break

    # 2. reviews that are due (spaced repetition)
    for p in parts:
        n = min(p.due, 15) if phase == "rest" else p.due
        if n:
            items.append({"kind": "review", "part": p.kind, "tab": tabs[p.kind],
                          "title": f"Review {n} due questions ({p.name.lower()})",
                          "detail": "Questions you missed or have not seen for a while.",
                          "minutes": n * (2 if p.kind == "interview" else 1), "target": n, "done": 0})

    # 3. new work: spread what is left over the days before the final week
    learn_days = max(1, days_left - (FINAL_DAYS if phase in ("learn", "practice") else 1))
    budget = max(0, minutes_per_day - sum(i["minutes"] for i in items))
    new: list[tuple[Part, int, float, list[Item], DomainProgress | None]] = []
    needed = 0.0
    for p in parts:
        if phase == "rest":
            break
        unseen = [(d, i) for d in p.priority() for i in sorted(d.unseen, key=lambda i: i.difficulty)]
        weak = [(d, i) for d in p.priority() for i in d.items if i.seen and i.level < 0.7]
        todo = unseen if unseen else weak if p.kind == "labs" else []
        if not todo:
            continue
        per_day = math.ceil(len(todo) / learn_days) if unseen else min(2, len(todo))
        avg = sum(i.minutes for _, i in todo) / len(todo)
        needed += len(todo) / learn_days * avg
        new.append((p, per_day, avg, [i for _, i in todo], todo[0][0]))
    # share the budget left between the parts, in proportion to the time they need
    want = sum(n * avg for _, n, avg, _, _ in new)
    for p, n, avg, todo, focus in new:
        share_all = budget * (n * avg) / want if want else 0
        # use the daily time you set (the message warns when it is not enough to finish on time)
        n_fit = min(len(todo), max(1, int(share_all // avg))) if share_all >= avg * 0.5 else (1 if not items else 0)
        if not n_fit:
            continue
        unseen_left = any(not i.seen for i in todo)
        if p.kind == "labs":
            picked = todo[:n_fit]
            items.append({"kind": "labs", "part": p.kind, "tab": "labs",
                          "title": f"Solve {n_fit} lab{'s' if n_fit > 1 else ''}" + ("" if unseen_left else " again"),
                          "detail": f"Focus: {focus.name}. " + ", ".join(f"{i.title} ({i.id})" for i in picked[:3])
                          + (f" and {len(picked) - 3} more" if len(picked) > 3 else ""),
                          "minutes": _round(n_fit * avg), "target": n_fit, "done": 0, "tasks": [i.id for i in picked]})
        else:
            items.append({"kind": "new", "part": p.kind, "tab": tabs[p.kind],
                          "title": f"Try {n_fit} new {'interview ' if p.kind == 'interview' else ''}questions",
                          "detail": f"Focus: {focus.name} (weight {focus.weight:g}%, strength {_round(100 * focus.strength)}%).",
                          "minutes": _round(n_fit * avg), "target": n_fit, "done": 0, "domain": focus.id})

    # what was done today fills the targets: answers count for reviews first, then new questions
    for p in parts:
        left = p.done_today
        for it in items:
            if it["part"] == p.kind and it["kind"] in ("review", "new", "labs"):
                it["done"] = min(it["target"], left)
                left -= it["done"]

    total_needed = _round(needed + sum(i["minutes"] for i in items if i["kind"] in ("review",)))
    pace = None
    if phase in ("learn", "practice"):
        span = max(1, (exam_day - start).days - FINAL_DAYS)
        expected = min(1.0, max(0, (today - start).days) / span)
        actual = sum(p.coverage for p in parts) / len(parts)
        status = "ahead" if actual >= expected + 0.1 else "on-track" if actual >= expected - 0.1 else "behind"
        pace = {"expected": _round(100 * expected), "actual": _round(100 * actual), "status": status,
                "minutes_needed": total_needed}
    planned = sum(i["minutes"] for i in items)
    message = PHASES[phase]
    if pace and needed > minutes_per_day * 1.1:
        message += (f" To try everything before the final week you need about {_round(needed)} minutes a day"
                    f" of new work; you set {minutes_per_day}. Study more each day or move the exam date.")
    return {"days_left": days_left, "phase": phase, "items": items, "minutes": planned, "message": message,
            "roadmap": roadmap(start, exam_day, today), "pace": pace}
