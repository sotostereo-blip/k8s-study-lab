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


def create_app(content_dir: Path | None = None, db_path: Path | None = None) -> FastAPI:
    content_dir = content_dir or Path(os.getenv("CONTENT_DIR", ROOT / "content"))
    db_path = db_path or Path(os.getenv("DB_PATH", ROOT / "data" / "progress.db"))
    lib = load_library(content_dir)
    db = Database(db_path)

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

    return app


app = create_app() if os.getenv("K8S_LAB_NO_AUTOAPP") != "1" else None
