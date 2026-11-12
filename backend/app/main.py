"""K8s Study Lab API."""
from __future__ import annotations

import json
import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import srs
from .content import Library, Question, load_library
from .db import Database
from .labs import LabManager, Runner, subprocess_runner

ROOT = Path(__file__).resolve().parents[2]


class AnswerIn(BaseModel):
    question_id: str
    selected: list[str]
    used_translation: bool = False


class ExamStartIn(BaseModel):
    exam_id: str = "kcna"
    questions: int | None = None   # default: official count (capped by bank size)
    minutes: int | None = None     # default: official duration, scaled to count


class ExamSubmitIn(BaseModel):
    answers: dict[str, list[str]]


class MockStartIn(BaseModel):
    track_id: str = "cka"
    tasks: int = 10
    minutes: int | None = None      # default: sum of the tasks' target minutes


class EnglishEventIn(BaseModel):
    kind: str  # glossary_lookup | translation
    ref: str | None = None


def is_correct(q: Question, selected: list[str]) -> bool:
    return set(selected) == set(q.answer)


def review(q: Question, selected: list[str]) -> dict:
    return {
        "question_id": q.id,
        "correct": is_correct(q, selected),
        "selected": selected,
        "answer": q.answer,
        "explanation": q.explanation,
        "docs": q.docs,
        "why": {o.id: o.why for o in q.options if o.why},
    }


def pick_exam_questions(lib: Library, exam_id: str, n: int) -> list[Question]:
    """Sample questions following the official domain weights."""
    exam = lib.exams[exam_id]
    pool = lib.questions_for(exam_id)
    n = min(n, len(pool))
    chosen: list[Question] = []
    for d in exam.domains:
        in_domain = [q for q in pool if q.domain == d.id]
        quota = round(n * d.weight / 100)
        chosen += random.sample(in_domain, min(quota, len(in_domain)))
    rest = [q for q in pool if q not in chosen]
    chosen += random.sample(rest, max(0, n - len(chosen)))
    chosen = chosen[:n]
    random.shuffle(chosen)
    return chosen


MOCK_ENV, MOCK_NODES = "two-node", 2  # one cluster for all exam tasks


def pick_mock_tasks(tasks: list, domains: list, n: int) -> list:
    """Sample tasks following the domain weights, skipping tasks that cannot share a cluster."""
    pool = [t for t in tasks if t.mock_exam]
    chosen: list = []

    def compatible(t) -> bool:
        return all(t.id not in c.conflicts_with and c.id not in t.conflicts_with for c in chosen)

    def take(candidates, k):
        random.shuffle(candidates)
        for t in candidates:
            if k <= 0 or len(chosen) >= n:
                break
            if t not in chosen and compatible(t):
                chosen.append(t)
                k -= 1

    for d in domains:
        take([t for t in pool if t.domain == d.id], max(1, round(n * d.weight / 100)))
    take(list(pool), n - len(chosen))
    random.shuffle(chosen)  # mixed order, like the real exam
    return chosen[:n]


def mock_setup_script(tasks: list) -> str:
    """One script that prepares every task scenario, each in its own subshell."""
    parts = []
    for t in tasks:
        if t.setup.strip():
            parts.append(f'echo "== {t.id}"\n(\n{t.setup.rstrip()}\n) || {{ echo "setup failed: {t.id}"; exit 1; }}')
    return "\n".join(parts)


def create_app(content_dir: Path | None = None, db_path: Path | None = None,
               labs_dir: Path | None = None, lab_runner: Runner = subprocess_runner) -> FastAPI:
    content_dir = content_dir or Path(os.getenv("CONTENT_DIR", ROOT / "content"))
    db_path = db_path or Path(os.getenv("DB_PATH", ROOT / "data" / "progress.db"))
    labs_dir = labs_dir or Path(os.getenv("LABS_DIR", ROOT / "labs"))
    lib = load_library(content_dir)
    db = Database(db_path)
    labs = LabManager(labs_dir, lab_runner)

    app = FastAPI(title="K8s Study Lab", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_exam(exam_id: str):
        if exam_id not in lib.exams:
            raise HTTPException(404, f"Unknown exam '{exam_id}'")
        return lib.exams[exam_id]

    def get_question(qid: str) -> Question:
        if qid not in lib.questions:
            raise HTTPException(404, f"Unknown question '{qid}'")
        return lib.questions[qid]

    def record(conn, q: Question, selected: list[str], mode: str, used_translation: bool = False) -> bool:
        ok = is_correct(q, selected)
        conn.execute(
            "INSERT INTO attempts (question_id, selected, correct, mode, used_translation) VALUES (?,?,?,?,?)",
            (q.id, json.dumps(selected), int(ok), mode, int(used_translation)),
        )
        row = conn.execute("SELECT box FROM cards WHERE question_id=?", (q.id,)).fetchone()
        box = srs.next_box(row["box"] if row else 1, ok)
        conn.execute(
            "INSERT INTO cards (question_id, box, due_at) VALUES (?,?,?) "
            "ON CONFLICT(question_id) DO UPDATE SET box=excluded.box, due_at=excluded.due_at",
            (q.id, box, srs.due_at(box)),
        )
        return ok

    @app.get("/api/health")
    def health():
        return {"status": "ok", "questions": len(lib.questions), "terms": len(lib.glossary)}

    @app.get("/api/exams")
    def exams():
        out = []
        for e in lib.exams.values():
            counts = {d.id: len(lib.questions_for(e.id, d.id)) for d in e.domains}
            out.append(e.model_dump() | {"question_counts": counts})
        return out

    @app.get("/api/glossary")
    def glossary():
        return [t.model_dump() for t in lib.glossary.values()]

    @app.get("/api/practice/next")
    def practice_next(exam_id: str = "kcna", domain: str | None = None, n: int = 10):
        get_exam(exam_id)
        pool = {q.id: q for q in lib.questions_for(exam_id, domain)}
        with db.connect() as conn:
            rows = conn.execute("SELECT question_id, due_at FROM cards").fetchall()
        seen = {r["question_id"]: r["due_at"] for r in rows if r["question_id"] in pool}
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        due = sorted((d, qid) for qid, d in seen.items() if d <= now)
        unseen = [qid for qid in pool if qid not in seen]
        random.shuffle(unseen)
        ids = ([qid for _, qid in due] + unseen)[:n]
        return {
            "due": len(due),
            "unseen": len(unseen),
            "questions": [pool[qid].public() for qid in ids],
        }

    @app.post("/api/practice/answer")
    def practice_answer(body: AnswerIn):
        q = get_question(body.question_id)
        with db.connect() as conn:
            record(conn, q, body.selected, "practice", body.used_translation)
        return review(q, body.selected)

    @app.post("/api/exam/start")
    def exam_start(body: ExamStartIn):
        exam = get_exam(body.exam_id)
        qs = pick_exam_questions(lib, exam.id, body.questions or exam.exam_questions)
        if not qs:
            raise HTTPException(400, "No questions available for this exam yet")
        minutes = body.minutes or max(1, round(exam.exam_minutes * len(qs) / exam.exam_questions))
        sid = uuid.uuid4().hex
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO exam_sessions (id, exam_id, question_ids, minutes) VALUES (?,?,?,?)",
                (sid, exam.id, json.dumps([q.id for q in qs]), minutes),
            )
        return {"session_id": sid, "minutes": minutes, "questions": [q.public() for q in qs]}

    @app.post("/api/exam/{session_id}/submit")
    def exam_submit(session_id: str, body: ExamSubmitIn):
        with db.connect() as conn:
            s = conn.execute("SELECT * FROM exam_sessions WHERE id=?", (session_id,)).fetchone()
            if not s:
                raise HTTPException(404, "Unknown exam session")
            if s["finished_at"]:
                raise HTTPException(409, "Exam already submitted")
            exam = lib.exams[s["exam_id"]]
            qids = json.loads(s["question_ids"])
            started = datetime.strptime(s["started_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds() / 60
            per_domain: dict[str, dict] = {}
            reviews = []
            for qid in qids:
                q = lib.questions[qid]
                sel = body.answers.get(qid, [])
                ok = record(conn, q, sel, "exam")
                d = per_domain.setdefault(q.domain, {"correct": 0, "total": 0})
                d["total"] += 1
                d["correct"] += int(ok)
                reviews.append(review(q, sel) | {"question": q.question, "options": [o.model_dump() for o in q.options]})
            correct = sum(d["correct"] for d in per_domain.values())
            score = round(100 * correct / len(qids), 1)
            conn.execute(
                "UPDATE exam_sessions SET finished_at=datetime('now'), score=? WHERE id=?",
                (score, session_id),
            )
        return {
            "score": score,
            "passed": score >= exam.passing_score,
            "passing_score": exam.passing_score,
            "correct": correct,
            "total": len(qids),
            "elapsed_minutes": round(elapsed, 1),
            "overtime": elapsed > s["minutes"],
            "domains": per_domain,
            "review": reviews,
        }

    @app.post("/api/english/event")
    def english_event(body: EnglishEventIn):
        with db.connect() as conn:
            conn.execute("INSERT INTO english_events (kind, ref) VALUES (?,?)", (body.kind, body.ref))
        return {"ok": True}

    @app.get("/api/stats")
    def stats(exam_id: str = "kcna"):
        exam = get_exam(exam_id)
        with db.connect() as conn:
            attempts = conn.execute("SELECT question_id, correct, used_translation FROM attempts").fetchall()
            cards = conn.execute("SELECT question_id, box, due_at FROM cards").fetchall()
            exams_done = conn.execute(
                "SELECT started_at, score FROM exam_sessions WHERE exam_id=? AND finished_at IS NOT NULL "
                "ORDER BY started_at DESC LIMIT 10",
                (exam_id,),
            ).fetchall()
            eng = conn.execute(
                "SELECT kind, COUNT(*) AS n FROM english_events GROUP BY kind"
            ).fetchall()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        domains = []
        for d in exam.domains:
            ids = {q.id for q in lib.questions_for(exam_id, d.id)}
            a = [r for r in attempts if r["question_id"] in ids]
            c = [r for r in cards if r["question_id"] in ids]
            domains.append({
                "id": d.id,
                "name": d.name,
                "weight": d.weight,
                "questions": len(ids),
                "attempts": len(a),
                "accuracy": round(100 * sum(r["correct"] for r in a) / len(a), 1) if a else None,
                "mastered": sum(1 for r in c if r["box"] >= 4),
                "due": sum(1 for r in c if r["due_at"] <= now),
            })
        translated = sum(r["used_translation"] for r in attempts)
        return {
            "exam_id": exam_id,
            "domains": domains,
            "exams": [dict(r) for r in exams_done],
            "english": {
                "answers_total": len(attempts),
                "answers_with_translation": translated,
                **{r["kind"]: r["n"] for r in eng},
            },
        }

    # ---------- hands-on labs ----------

    def get_task(task_id: str):
        if task_id not in lib.tasks:
            raise HTTPException(404, f"Unknown lab '{task_id}'")
        return lib.tasks[task_id]

    @app.get("/api/labs")
    def labs_list():
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT task_id, MAX(passed) AS solved, COUNT(*) AS tries, "
                "MIN(CASE WHEN passed THEN seconds END) AS best_seconds FROM lab_attempts GROUP BY task_id"
            ).fetchall()
        progress = {r["task_id"]: dict(r) for r in rows}
        return {
            "tracks": [t.model_dump() for t in lib.tracks.values()],
            "tasks": [
                t.public() | {"progress": progress.get(t.id)}
                for t in sorted(lib.tasks.values(), key=lambda t: t.id)
            ],
            "lab": labs.status(),
            "mock_exams": [dict(r) for r in mock_history()],
        }

    @app.get("/api/labs/status")
    def labs_status():
        return labs.status()

    @app.post("/api/labs/{task_id}/start")
    def labs_start(task_id: str):
        task = get_task(task_id)
        track = lib.tracks[task.id.split("-")[0]]
        return labs.start(task.id, task.environment, track.environments[task.environment].nodes, task.setup)

    @app.post("/api/labs/stop")
    def labs_stop():
        return labs.stop()

    @app.post("/api/labs/{task_id}/check")
    def labs_check(task_id: str):
        task = get_task(task_id)
        try:
            results = labs.check(task.id, task.checks)
        except RuntimeError as e:
            raise HTTPException(409, str(e))
        passed = sum(r["passed"] for r in results)
        solved = passed == len(results)
        seconds = labs.status()["elapsed_seconds"]
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO lab_attempts (task_id, passed, checks_passed, checks_total, seconds) VALUES (?,?,?,?,?)",
                (task.id, int(solved), passed, len(results), seconds),
            )
        return {"solved": solved, "passed": passed, "total": len(results), "seconds": seconds, "checks": results}

    # ---------- mock exam: several tasks, one cluster, one timer ----------

    def mock_history():
        with db.connect() as conn:
            return conn.execute(
                "SELECT id, created_at, minutes, score, json_array_length(task_ids) AS tasks FROM mock_sessions "
                "WHERE finished_at IS NOT NULL AND score IS NOT NULL ORDER BY created_at DESC LIMIT 5"
            ).fetchall()

    def mock_public(row) -> dict:
        track = lib.tracks[row["track_id"]]
        ids = json.loads(row["task_ids"])
        lab = labs.status()
        mine = lab["task_id"] == f"mock-{row['id']}"
        return {
            "session_id": row["id"],
            "minutes": row["minutes"],
            "passing_score": track.passing_score,
            "tasks": [lib.tasks[i].public() | {"points": lib.tasks[i].minutes} for i in ids],
            "lab": lab if mine else {**lab, "status": "idle", "terminal_url": None},
            "finished": row["finished_at"] is not None,
        }

    def get_mock(session_id: str):
        with db.connect() as conn:
            row = conn.execute("SELECT * FROM mock_sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Unknown mock exam")
        return row

    @app.post("/api/mock/start")
    def mock_start(body: MockStartIn):
        if body.track_id not in lib.tracks:
            raise HTTPException(404, f"Unknown track '{body.track_id}'")
        track = lib.tracks[body.track_id]
        all_tasks = [t for t in lib.tasks.values() if t.id.startswith(f"{track.id}-")]
        chosen = pick_mock_tasks(all_tasks, track.domains, max(1, body.tasks))
        if not chosen:
            raise HTTPException(400, "No tasks available for a mock exam")
        minutes = body.minutes or sum(t.minutes for t in chosen)
        sid = uuid.uuid4().hex
        with db.connect() as conn:
            # an unfinished exam is abandoned when a new one starts
            conn.execute("UPDATE mock_sessions SET finished_at=datetime('now') WHERE finished_at IS NULL")
            conn.execute(
                "INSERT INTO mock_sessions (id, track_id, task_ids, minutes) VALUES (?,?,?,?)",
                (sid, track.id, json.dumps([t.id for t in chosen]), minutes),
            )
        labs.start(f"mock-{sid}", MOCK_ENV, MOCK_NODES, mock_setup_script(chosen),
                   setup_timeout=120 + 120 * len(chosen))
        return mock_public(get_mock(sid))

    @app.get("/api/mock/current")
    def mock_current():
        with db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM mock_sessions WHERE finished_at IS NULL ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return mock_public(row) if row else None

    @app.post("/api/mock/{session_id}/submit")
    def mock_submit(session_id: str):
        row = get_mock(session_id)
        if row["finished_at"]:
            raise HTTPException(409, "This mock exam is already finished")
        ids = json.loads(row["task_ids"])
        seconds = labs.status()["elapsed_seconds"]
        results, earned, total = [], 0.0, 0
        for tid in ids:
            t = lib.tasks[tid]
            try:
                checks = labs.check(f"mock-{session_id}", t.checks)
            except RuntimeError as e:
                raise HTTPException(409, "The exam cluster is not running: " + str(e))
            passed = sum(c["passed"] for c in checks)
            points = t.minutes
            work = [r for c, r in zip(t.checks, checks) if not c.guard]
            guards_ok = all(r["passed"] for c, r in zip(t.checks, checks) if c.guard)
            # partial credit from the real work only; breaking a guard makes the task worth 0
            got = round(points * sum(r["passed"] for r in work) / len(work), 1) if guards_ok else 0.0
            earned += got
            total += points
            results.append({
                "task_id": t.id, "title": t.title, "domain": t.domain, "points": points, "earned": got,
                "solved": passed == len(checks), "guards_ok": guards_ok, "solution": t.solution, "docs": t.docs,
                "checks": [r | {"guard": c.guard} for c, r in zip(t.checks, checks)],
            })
        score = round(100 * earned / total, 1)
        with db.connect() as conn:
            conn.execute(
                "UPDATE mock_sessions SET finished_at=datetime('now'), score=?, results=? WHERE id=?",
                (score, json.dumps(results), session_id),
            )
            for r in results:
                conn.execute(
                    "INSERT INTO lab_attempts (task_id, passed, checks_passed, checks_total, seconds) VALUES (?,?,?,?,?)",
                    (r["task_id"], int(r["solved"]), sum(c["passed"] for c in r["checks"]), len(r["checks"]), None),
                )
        track = lib.tracks[row["track_id"]]
        return {
            "score": score,
            "passed": score >= track.passing_score,
            "passing_score": track.passing_score,
            "minutes": row["minutes"],
            "elapsed_seconds": seconds,
            "overtime": bool(seconds and seconds > row["minutes"] * 60),
            "tasks": results,
        }

    @app.post("/api/mock/{session_id}/abandon")
    def mock_abandon(session_id: str):
        get_mock(session_id)
        with db.connect() as conn:
            conn.execute("UPDATE mock_sessions SET finished_at=datetime('now') WHERE id=? AND finished_at IS NULL",
                         (session_id,))
        if labs.status()["task_id"] == f"mock-{session_id}":
            labs.stop()
        return {"ok": True}

    @app.get("/api/labs/{task_id}/solution")
    def labs_solution(task_id: str):
        task = get_task(task_id)
        return {"solution": task.solution, "docs": task.docs}

    return app


app = create_app() if os.getenv("K8S_LAB_NO_AUTOAPP") != "1" else None
