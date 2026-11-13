"""K8s Study Lab API."""
from __future__ import annotations

import json
import os
import random
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import ai, domc, facts, path, plan, srs
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
    real: bool = False             # real exam conditions: no translations or glossary (frontend)
    esl: bool = False              # add the provider's extra time for non-native English speakers
    domc: bool | None = None       # show DOMC questions like the real exam (default: when it has them)


class ExamSubmitIn(BaseModel):
    answers: dict[str, list[str]]
    domc: dict[str, dict[str, bool]] = {}   # DOMC questions: option id -> YES/NO


class DomcIn(BaseModel):
    question_id: str
    responses: dict[str, bool] = {}


class MockStartIn(BaseModel):
    track_id: str = "cka"
    tasks: int = 10
    minutes: int | None = None      # default: sum of the tasks' target minutes


class EnglishEventIn(BaseModel):
    kind: str  # glossary_lookup | translation | listen
    ref: str | None = None  # glossary id, or word:<vocabulary id>


class InterviewGradeIn(BaseModel):
    question_id: str
    covered: list[int]              # indexes of the key points the answer covered
    seconds: int | None = None
    words: int | None = None
    session_id: str | None = None   # set during a mock interview


class InterviewMockIn(BaseModel):
    questions: int = 8
    minutes: int | None = None
    categories: list[str] = []      # empty = all
    level: str | None = None


class GoalIn(BaseModel):
    exam_date: date
    minutes_per_day: int = Field(default=60, ge=15, le=600)


class FeedbackIn(BaseModel):
    question_id: str
    answer: str = Field(min_length=1, max_length=6000)
    seconds: int | None = None


class EarnedIn(BaseModel):
    passed_on: date
    expires_on: date | None = None   # the date on your certificate, when it differs


class VocabAnswerIn(BaseModel):
    item_id: str
    selected: str


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
               labs_dir: Path | None = None, lab_runner: Runner = subprocess_runner,
               coach: ai.Coach | None = None) -> FastAPI:
    content_dir = content_dir or Path(os.getenv("CONTENT_DIR", ROOT / "content"))
    db_path = db_path or Path(os.getenv("DB_PATH", ROOT / "data" / "progress.db"))
    labs_dir = labs_dir or Path(os.getenv("LABS_DIR", ROOT / "labs"))
    lib = load_library(content_dir)
    db = Database(db_path)
    labs = LabManager(labs_dir, lab_runner)
    coach = coach or ai.Coach()

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

    @app.get("/api/vocabulary")
    def vocabulary():
        return [w.model_dump() for w in lib.vocabulary.values()]

    # ---------- English: vocabulary practice (Leitner boxes, like the questions) ----------

    def vocab_items() -> dict[str, dict]:
        items = {f"term:{t.id}": {"id": f"term:{t.id}", "kind": "term", "word": t.term, "definition": t.definition,
                                  "example": None, "es": t.es, "match": t.match or [t.term]} for t in lib.glossary.values()}
        items |= {f"word:{w.id}": {"id": f"word:{w.id}", "kind": "word", "word": w.word, "definition": w.definition,
                                   "example": w.example, "es": w.es, "match": w.match} for w in lib.vocabulary.values()}
        return items

    def lookups() -> dict[str, int]:
        """How often each item was looked up or translated while studying."""
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT ref, COUNT(*) AS n FROM english_events WHERE ref IS NOT NULL GROUP BY ref").fetchall()
        out: dict[str, int] = {}
        for r in rows:
            key = r["ref"] if r["ref"].startswith("word:") else f"term:{r['ref']}"
            out[key] = out.get(key, 0) + r["n"]
        return out

    @app.get("/api/english/next")
    def english_next(n: int = 10, kind: str | None = None):
        items = {k: v for k, v in vocab_items().items() if kind in (None, v["kind"])}
        if len(items) < 4:
            raise HTTPException(400, "Not enough vocabulary yet")
        with db.connect() as conn:
            cards = {r["item_id"]: dict(r) for r in conn.execute("SELECT * FROM vocab_cards").fetchall()}
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        looked = lookups()
        due = sorted((c["box"], c["due_at"], k) for k, c in cards.items() if k in items and c["due_at"] <= now)
        unseen = [k for k in items if k not in cards]
        random.shuffle(unseen)
        unseen.sort(key=lambda k: -looked.get(k, 0))   # words you needed help with come first
        ids = ([k for *_, k in due] + unseen)[:n]
        out = []
        for k in ids:
            it = items[k]
            others = random.sample([o for o in items.values() if o["kind"] == it["kind"] and o["id"] != k], 3)
            options = [o["word"] for o in others] + [it["word"]]
            random.shuffle(options)
            example = it["example"]
            if example:   # hide the word (all its forms) in the example sentence
                forms = sorted(it["match"] + [it["word"]], key=len, reverse=True)
                example = re.sub(r"\b(" + "|".join(map(re.escape, forms)) + r")\b", "_____", example, flags=re.I)
            out.append({"id": k, "kind": it["kind"], "definition": it["definition"], "example": example,
                        "options": options, "looked_up": looked.get(k, 0)})
        return {"due": len(due), "unseen": len(unseen), "items": out}

    @app.post("/api/english/answer")
    def english_answer(body: VocabAnswerIn):
        items = vocab_items()
        if body.item_id not in items:
            raise HTTPException(404, "Unknown vocabulary item")
        it = items[body.item_id]
        ok = body.selected.strip().lower() == it["word"].lower()
        with db.connect() as conn:
            row = conn.execute("SELECT box FROM vocab_cards WHERE item_id=?", (body.item_id,)).fetchone()
            box = srs.next_box(row["box"] if row else 1, ok)
            conn.execute(
                "INSERT INTO vocab_cards (item_id, box, due_at, correct, wrong) VALUES (?,?,?,?,?) "
                "ON CONFLICT(item_id) DO UPDATE SET box=excluded.box, due_at=excluded.due_at, "
                "correct=correct+excluded.correct, wrong=wrong+excluded.wrong",
                (body.item_id, box, srs.due_at(box), int(ok), int(not ok)),
            )
        return {"correct": ok, **it}

    @app.get("/api/english/stats")
    def english_stats():
        items = vocab_items()
        with db.connect() as conn:
            cards = conn.execute("SELECT item_id, box FROM vocab_cards").fetchall()
            ev = conn.execute("SELECT kind, COUNT(*) AS n FROM english_events GROUP BY kind").fetchall()
        looked = lookups()
        top = sorted(((n, k) for k, n in looked.items() if k in items), reverse=True)[:10]
        return {
            "items": len(items),
            "terms": sum(1 for i in items.values() if i["kind"] == "term"),
            "words": sum(1 for i in items.values() if i["kind"] == "word"),
            "practised": sum(1 for c in cards if c["item_id"] in items),
            "mastered": sum(1 for c in cards if c["item_id"] in items and c["box"] >= 4),
            "events": {r["kind"]: r["n"] for r in ev},
            "most_looked_up": [{**items[k], "count": n} for n, k in top],
        }

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
        scale = len(qs) / exam.exam_questions
        minutes = body.minutes or max(1, round(exam.exam_minutes * scale))
        esl = bool(body.esl and exam.esl_minutes)
        if esl:
            minutes += max(1, round(exam.esl_minutes * scale))
        use_domc = exam.domc > 0 if body.domc is None else body.domc
        n_domc = min(len(qs), round(len(qs) * exam.domc / exam.exam_questions)) if use_domc and exam.domc else 0
        domc_ids = {q.id for q in random.sample(qs, n_domc)}
        sid = uuid.uuid4().hex
        conditions = {"real": body.real, "esl": esl}
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO exam_sessions (id, exam_id, question_ids, minutes, domc, conditions) VALUES (?,?,?,?,?,?)",
                (sid, exam.id, json.dumps([q.id for q in qs]), minutes, json.dumps(sorted(domc_ids)),
                 json.dumps(conditions)),
            )
        out = []
        for q in qs:
            pub = q.public()
            if q.id in domc_ids:   # the options come one at a time from /domc
                pub |= {"style": "domc", "options": [], "select": None}
            out.append(pub)
        return {"session_id": sid, "minutes": minutes, "questions": out, "conditions": conditions}

    def open_session(conn, session_id: str):
        s = conn.execute("SELECT * FROM exam_sessions WHERE id=?", (session_id,)).fetchone()
        if not s:
            raise HTTPException(404, "Unknown exam session")
        if s["finished_at"]:
            raise HTTPException(409, "Exam already submitted")
        return s

    @app.post("/api/exam/{session_id}/domc")
    def exam_domc(session_id: str, body: DomcIn):
        """Next option of a DOMC question, given the YES/NO answers so far."""
        with db.connect() as conn:
            s = open_session(conn, session_id)
        if body.question_id not in json.loads(s["domc"]):
            raise HTTPException(400, "This question is not a DOMC question in this exam")
        q = lib.questions[body.question_id]
        step = domc.walk(session_id, q, body.responses)
        text = {o.id: o.text for o in q.options}
        return {"done": step["done"], "next": None if step["next"] is None else
                {"id": step["next"], "text": text[step["next"]]}}

    @app.post("/api/exam/{session_id}/submit")
    def exam_submit(session_id: str, body: ExamSubmitIn):
        with db.connect() as conn:
            s = open_session(conn, session_id)
            exam = lib.exams[s["exam_id"]]
            qids = json.loads(s["question_ids"])
            domc_ids = set(json.loads(s["domc"]))
            started = datetime.strptime(s["started_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds() / 60
            per_domain: dict[str, dict] = {}
            reviews = []
            for qid in qids:
                q = lib.questions[qid]
                extra = {}
                if qid in domc_ids:
                    responses = body.domc.get(qid, {})
                    sel = domc.walk(session_id, q, responses)["selected"]
                    extra = {"style": "domc", "domc": [{"id": o, "yes": responses[o]}
                                                       for o in domc.order(session_id, q) if o in responses]}
                else:
                    sel = body.answers.get(qid, [])
                ok = record(conn, q, sel, "exam")
                d = per_domain.setdefault(q.domain, {"correct": 0, "total": 0})
                d["total"] += 1
                d["correct"] += int(ok)
                reviews.append(review(q, sel) | extra | {"question": q.question, "options": [o.model_dump() for o in q.options]})
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
            "conditions": json.loads(s["conditions"]),
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

    @app.get("/api/certifications")
    def certifications(today: date | None = None):
        ages = {r["id"]: r for r in facts.report(lib.certifications, today or date.today())}
        return [c.model_dump() | ({"facts_age_months": ages[c.id]["months"], "facts_stale": ages[c.id]["stale"]}
                                  if c.id in ages else {}) for c in lib.certifications]

    def get_track(track_id: str):
        if track_id not in lib.tracks:
            raise HTTPException(404, f"Unknown lab track '{track_id}'")
        return lib.tracks[track_id]

    @app.get("/api/labs")
    def labs_list(track_id: str = "cka"):
        get_track(track_id)
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT task_id, MAX(passed) AS solved, COUNT(*) AS tries, "
                "MIN(CASE WHEN passed THEN seconds END) AS best_seconds FROM lab_attempts GROUP BY task_id"
            ).fetchall()
        progress = {r["task_id"]: dict(r) for r in rows}
        return {
            "tracks": [lib.tracks[track_id].model_dump()],
            "tasks": [
                t.public() | {"progress": progress.get(t.id)}
                for t in sorted(lib.tasks_for(track_id), key=lambda t: t.id)
            ],
            "lab": labs.status(),
            "mock_exams": [dict(r) for r in mock_history(track_id)],
        }

    @app.get("/api/labs/status")
    def labs_status():
        return labs.status()

    @app.post("/api/labs/{task_id}/start")
    def labs_start(task_id: str):
        task = get_task(task_id)
        env = lib.tracks[task.id.split("-")[0]].environments[task.environment]
        return labs.start(task.id, task.environment, env.nodes, task.setup,
                          ready=env.ready_command, ready_timeout=env.ready_timeout)

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

    def mock_history(track_id: str):
        with db.connect() as conn:
            return conn.execute(
                "SELECT id, created_at, minutes, score, json_array_length(task_ids) AS tasks FROM mock_sessions "
                "WHERE track_id=? AND finished_at IS NOT NULL AND score IS NOT NULL ORDER BY created_at DESC LIMIT 5",
                (track_id,),
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
        track = get_track(body.track_id)
        if not track.mock:
            raise HTTPException(400, f"{track.name} has no mock exam")
        all_tasks = lib.tasks_for(track.id)
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
        env = track.environments[track.mock_environment]
        labs.start(f"mock-{sid}", track.mock_environment, env.nodes, mock_setup_script(chosen),
                   setup_timeout=120 + 120 * len(chosen), ready=env.ready_command, ready_timeout=env.ready_timeout)
        return mock_public(get_mock(sid))

    @app.get("/api/mock/current")
    def mock_current(track_id: str = "cka"):
        with db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM mock_sessions WHERE track_id=? AND finished_at IS NULL ORDER BY created_at DESC LIMIT 1",
                (track_id,),
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

    # ---------- job interviews in English: answer aloud, check the key points ----------

    def get_iv(qid: str):
        if qid not in lib.interview_questions:
            raise HTTPException(404, f"Unknown interview question '{qid}'")
        return lib.interview_questions[qid]

    def iv_pool(categories: list[str] | None, level: str | None):
        return [q for q in lib.interview_questions.values()
                if (not categories or q.category in categories) and level in (None, "", q.level)]

    @app.get("/api/interview/categories")
    def interview_categories():
        with db.connect() as conn:
            att = conn.execute("SELECT question_id, covered, total FROM interview_attempts").fetchall()
            cards = {r["question_id"]: r["box"] for r in conn.execute("SELECT * FROM interview_cards").fetchall()}
        out = []
        for c in lib.interview_categories.values():
            ids = {q.id for q in lib.interview_questions.values() if q.category == c.id}
            a = [r for r in att if r["question_id"] in ids]
            out.append(c.model_dump() | {
                "questions": len(ids),
                "practised": len({r["question_id"] for r in a}),
                "mastered": sum(1 for i in ids if cards.get(i, 0) >= 4),
                "coverage": round(100 * sum(r["covered"] for r in a) / sum(r["total"] for r in a), 1) if a else None,
            })
        return out

    @app.get("/api/interview/next")
    def interview_next(category: str | None = None, level: str | None = None, n: int = 10):
        pool = {q.id: q for q in iv_pool([category] if category else None, level)}
        with db.connect() as conn:
            rows = conn.execute("SELECT question_id, due_at FROM interview_cards").fetchall()
        seen = {r["question_id"]: r["due_at"] for r in rows if r["question_id"] in pool}
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        due = sorted((d, qid) for qid, d in seen.items() if d <= now)
        unseen = [qid for qid in pool if qid not in seen]
        random.shuffle(unseen)
        ids = ([qid for _, qid in due] + unseen)[:n]
        return {"due": len(due), "unseen": len(unseen), "questions": [pool[i].public() for i in ids]}

    @app.get("/api/interview/{qid}/review")
    def interview_review(qid: str):
        q = get_iv(qid)
        return {"id": q.id, "key_points": q.key_points, "model_answer": q.model_answer,
                "follow_ups": q.follow_ups, "docs": q.docs}

    @app.post("/api/interview/grade")
    def interview_grade(body: InterviewGradeIn):
        q = get_iv(body.question_id)
        covered = sorted({i for i in body.covered if 0 <= i < len(q.key_points)})
        ratio = len(covered) / len(q.key_points)
        ok = ratio >= 0.7   # a good answer covers most key points
        with db.connect() as conn:
            if body.session_id:
                s = conn.execute("SELECT * FROM interview_sessions WHERE id=?", (body.session_id,)).fetchone()
                if not s or q.id not in json.loads(s["question_ids"]):
                    raise HTTPException(400, "This question is not part of that mock interview")
                if s["finished_at"]:
                    raise HTTPException(409, "This mock interview is already finished")
                conn.execute("DELETE FROM interview_attempts WHERE session_id=? AND question_id=?", (s["id"], q.id))
            conn.execute(
                "INSERT INTO interview_attempts (question_id, covered, total, seconds, words, mode, session_id) "
                "VALUES (?,?,?,?,?,?,?)",
                (q.id, len(covered), len(q.key_points), body.seconds, body.words,
                 "mock" if body.session_id else "practice", body.session_id),
            )
            row = conn.execute("SELECT box FROM interview_cards WHERE question_id=?", (q.id,)).fetchone()
            box = srs.next_box(row["box"] if row else 1, ok)
            conn.execute(
                "INSERT INTO interview_cards (question_id, box, due_at) VALUES (?,?,?) "
                "ON CONFLICT(question_id) DO UPDATE SET box=excluded.box, due_at=excluded.due_at",
                (q.id, box, srs.due_at(box)),
            )
        return {"covered": len(covered), "total": len(q.key_points), "good": ok, "box": box}

    @app.post("/api/interview/mock/start")
    def interview_mock_start(body: InterviewMockIn):
        pool = iv_pool(body.categories, body.level)
        n = max(1, min(body.questions, len(pool)))
        if not pool:
            raise HTTPException(400, "No interview questions match these filters")
        # like a real interview: one behavioral question first, then a mix of topics
        behavioral = [q for q in pool if q.type == "behavioral"]
        first = random.sample(behavioral, 1) if behavioral else []
        rest = [q for q in pool if q not in first]
        by_cat: dict[str, list] = {}
        for q in random.sample(rest, len(rest)):
            by_cat.setdefault(q.category, []).append(q)
        mixed = []
        while len(mixed) < n - len(first) and any(by_cat.values()):
            for cat in list(by_cat):   # round robin over categories
                if by_cat[cat] and len(mixed) < n - len(first):
                    mixed.append(by_cat[cat].pop())
        chosen = first + mixed
        minutes = body.minutes or max(5, round(sum(q.minutes for q in chosen) * 1.5))
        sid = uuid.uuid4().hex
        with db.connect() as conn:
            conn.execute("INSERT INTO interview_sessions (id, question_ids, minutes) VALUES (?,?,?)",
                         (sid, json.dumps([q.id for q in chosen]), minutes))
        return {"session_id": sid, "minutes": minutes,
                "questions": [q.public() | {"follow_ups": q.follow_ups[:1]} for q in chosen]}

    @app.post("/api/interview/mock/{session_id}/finish")
    def interview_mock_finish(session_id: str):
        with db.connect() as conn:
            s = conn.execute("SELECT * FROM interview_sessions WHERE id=?", (session_id,)).fetchone()
            if not s:
                raise HTTPException(404, "Unknown mock interview")
            if s["finished_at"]:
                raise HTTPException(409, "This mock interview is already finished")
            ids = json.loads(s["question_ids"])
            att = {r["question_id"]: dict(r) for r in conn.execute(
                "SELECT * FROM interview_attempts WHERE session_id=?", (session_id,)).fetchall()}
            results = []
            for qid in ids:
                q = lib.interview_questions[qid]
                a = att.get(qid)
                results.append({"question_id": qid, "question": q.question, "category": q.category,
                                "type": q.type, "answered": a is not None,
                                "covered": a["covered"] if a else 0, "total": len(q.key_points),
                                "seconds": a["seconds"] if a else None, "words": a["words"] if a else None})
            score = round(100 * sum(r["covered"] for r in results) / sum(r["total"] for r in results), 1)
            conn.execute("UPDATE interview_sessions SET finished_at=datetime('now'), score=? WHERE id=?",
                         (score, session_id))
        spoken = [r for r in results if r["seconds"] and r["words"]]
        wpm = round(60 * sum(r["words"] for r in spoken) / sum(r["seconds"] for r in spoken)) if spoken else None
        return {"score": score, "minutes": s["minutes"], "words_per_minute": wpm, "questions": results}

    @app.get("/api/ai/status")
    def ai_status():
        return {"enabled": coach.enabled, "model": coach.model if coach.enabled else None}

    @app.post("/api/interview/feedback")
    def interview_feedback(body: FeedbackIn):
        """Optional AI feedback on one answer. Nothing is stored."""
        if not coach.enabled:
            raise HTTPException(503, "AI feedback is off. Set ANTHROPIC_API_KEY for the backend to turn it on.")
        q = get_iv(body.question_id)
        if len(body.answer.split()) < 5:
            raise HTTPException(400, "Say or type a longer answer first (at least a few sentences).")
        try:
            import anthropic
        except ImportError:
            raise HTTPException(503, "Install the anthropic package to use AI feedback.")
        try:
            return coach.feedback(q, body.answer, body.seconds)
        except anthropic.AuthenticationError:
            raise HTTPException(502, "The Anthropic API key was not accepted. Check ANTHROPIC_API_KEY.")
        except anthropic.RateLimitError:
            raise HTTPException(429, "Too many AI requests right now. Wait a minute and try again.")
        except anthropic.APIStatusError as e:
            raise HTTPException(502, f"The AI service returned an error ({e.status_code}). Try again later.")
        except anthropic.APIConnectionError:
            raise HTTPException(502, "Cannot reach the AI service. Check your internet connection.")
        except RuntimeError as e:
            raise HTTPException(502, str(e))

    @app.get("/api/interview/stats")
    def interview_stats():
        with db.connect() as conn:
            mocks = conn.execute(
                "SELECT id, created_at, score, json_array_length(question_ids) AS questions FROM interview_sessions "
                "WHERE finished_at IS NOT NULL AND score IS NOT NULL ORDER BY created_at DESC LIMIT 5").fetchall()
            a = conn.execute("SELECT COUNT(*) AS n, SUM(words) AS w, SUM(seconds) AS s FROM interview_attempts "
                             "WHERE words > 0 AND seconds > 0").fetchone()
            total = conn.execute("SELECT COUNT(*) AS n FROM interview_attempts").fetchone()["n"]
        return {"questions": len(lib.interview_questions), "answers": total,
                "words_per_minute": round(60 * a["w"] / a["s"]) if a["n"] else None,
                "mocks": [dict(r) for r in mocks]}

    # ---------- study plan and readiness ----------

    def get_cert(cert_id: str):
        for c in lib.certifications:
            if c.id == cert_id:
                return c
        raise HTTPException(404, f"Unknown certification '{cert_id}'")

    def parts_for(cert) -> tuple[list[plan.Part], str]:
        """Read the progress of one certification from the database."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        today = "date('now', 'localtime')"
        parts: list[plan.Part] = []

        def day(ts: str) -> date:
            return datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).astimezone().date()

        with db.connect() as conn:
            if cert.exam:
                exam = lib.exams[cert.exam]
                boxes = {r["question_id"]: r for r in conn.execute("SELECT question_id, box, due_at FROM cards")}
                domains = []
                for d in exam.domains:
                    qs = lib.questions_for(exam.id, d.id)
                    domains.append(plan.DomainProgress(d.id, d.name, d.weight, [
                        plan.Item(q.id, q.id, plan.EXAM_RECALL[boxes[q.id]["box"] if q.id in boxes else 0],
                                  q.id in boxes, 1.5) for q in qs]))
                ids = {q.id for q in lib.questions_for(exam.id)}
                mocks = conn.execute("SELECT started_at, score FROM exam_sessions WHERE exam_id=? AND score IS NOT NULL "
                                     "ORDER BY started_at DESC LIMIT 10", (exam.id,)).fetchall()
                done = conn.execute(f"SELECT question_id FROM attempts WHERE mode='practice' AND "
                                    f"date(created_at, 'localtime') = {today}").fetchall()
                parts.append(plan.Part(
                    "exam", "Question bank", exam.passing_score, exam.exam_minutes, domains,
                    [plan.Mock(r["score"], day(r["started_at"])) for r in mocks],
                    due=sum(1 for q, r in boxes.items() if q in ids and r["due_at"] <= now),
                    done_today=sum(1 for r in done if r["question_id"] in ids),
                    mock_today=any(day(r["started_at"]) == date.today() for r in mocks)))
            if cert.track:
                track = lib.tracks[cert.track]
                best = {r["task_id"]: r for r in conn.execute(
                    "SELECT task_id, MAX(passed) AS solved, MIN(CASE WHEN passed THEN seconds END) AS best "
                    "FROM lab_attempts GROUP BY task_id")}
                domains = []
                for d in track.domains:
                    items = []
                    for t in sorted(lib.tasks_for(track.id), key=lambda t: t.id):
                        if t.domain != d.id:
                            continue
                        r = best.get(t.id)
                        solved = bool(r and r["solved"])
                        fast = solved and r["best"] is not None and r["best"] <= t.minutes * 60
                        items.append(plan.Item(t.id, t.title, plan.LAB_FAST if fast else plan.LAB_SLOW if solved else 0.0,
                                               solved, t.minutes * 1.5, t.difficulty))
                    domains.append(plan.DomainProgress(d.id, d.name, d.weight, items))
                mocks = conn.execute("SELECT created_at, score FROM mock_sessions WHERE track_id=? AND score IS NOT NULL "
                                     "ORDER BY created_at DESC LIMIT 10", (track.id,)).fetchall()
                solved_today = conn.execute(f"SELECT DISTINCT task_id FROM lab_attempts WHERE passed=1 AND "
                                            f"date(created_at, 'localtime') = {today}").fetchall()
                parts.append(plan.Part(
                    "labs", "Labs", track.passing_score, track.exam_minutes if track.mock else 0, domains,
                    [plan.Mock(r["score"], day(r["created_at"])) for r in mocks],
                    done_today=sum(1 for r in solved_today if r["task_id"].startswith(track.id + "-")),
                    mock_today=any(day(r["created_at"]) == date.today() for r in mocks)))
            if cert.interview:
                boxes = {r["question_id"]: r for r in conn.execute("SELECT question_id, box, due_at FROM interview_cards")}
                domains = []
                cats = list(lib.interview_categories.values())
                for c in cats:
                    qs = [q for q in lib.interview_questions.values() if q.category == c.id]
                    domains.append(plan.DomainProgress(c.id, c.name, round(100 / len(cats), 1), [
                        plan.Item(q.id, q.question, plan.INTERVIEW_RECALL[boxes[q.id]["box"] if q.id in boxes else 0],
                                  q.id in boxes, q.minutes + 2) for q in qs]))
                mocks = conn.execute("SELECT created_at, score FROM interview_sessions WHERE score IS NOT NULL "
                                     "ORDER BY created_at DESC LIMIT 10").fetchall()
                done = conn.execute(f"SELECT COUNT(*) AS n FROM interview_attempts WHERE mode='practice' AND "
                                    f"date(created_at, 'localtime') = {today}").fetchone()["n"]
                parts.append(plan.Part(
                    "interview", "Interview", 70, 20, domains,
                    [plan.Mock(r["score"], day(r["created_at"])) for r in mocks],
                    due=sum(1 for r in boxes.values() if r["due_at"] <= now), done_today=done,
                    mock_today=any(day(r["created_at"]) == date.today() for r in mocks)))
        performance = cert.official and cert.official.format.lower().startswith("performance")
        main = "labs" if cert.track and (performance or not cert.exam) else "exam" if cert.exam else "interview"
        return parts, main

    def get_goal(cert_id: str):
        with db.connect() as conn:
            return conn.execute("SELECT * FROM study_goals WHERE cert_id=?", (cert_id,)).fetchone()

    @app.get("/api/readiness")
    def readiness(cert_id: str):
        parts, main = parts_for(get_cert(cert_id))
        return plan.readiness(parts, main)

    @app.get("/api/plan")
    def study_plan(cert_id: str, today: date | None = None):
        cert = get_cert(cert_id)
        parts, main = parts_for(cert)
        goal = get_goal(cert_id)
        out = {"cert_id": cert_id, "goal": dict(goal) if goal else None, "readiness": plan.readiness(parts, main)}
        if goal:
            today = today or date.today()
            start = min(date.fromisoformat(goal["created_at"]), today)
            out["today"] = plan.daily_plan(parts, main, date.fromisoformat(goal["exam_date"]), start, today,
                                           goal["minutes_per_day"])
        return out

    @app.put("/api/plan")
    def set_goal(cert_id: str, body: GoalIn):
        get_cert(cert_id)
        if body.exam_date < date.today():
            raise HTTPException(400, "The exam date is in the past")
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO study_goals (cert_id, exam_date, minutes_per_day) VALUES (?,?,?) "
                "ON CONFLICT(cert_id) DO UPDATE SET exam_date=excluded.exam_date, minutes_per_day=excluded.minutes_per_day",
                (cert_id, body.exam_date.isoformat(), body.minutes_per_day))
        return study_plan(cert_id)

    # ---------- certification path map ----------

    @app.get("/api/path")
    def path_map(today: date | None = None):
        today = today or date.today()
        with db.connect() as conn:
            earned = {r["cert_id"]: {"passed_on": date.fromisoformat(r["passed_on"]),
                                     "expires_on": date.fromisoformat(r["expires_on"]) if r["expires_on"] else None}
                      for r in conn.execute("SELECT * FROM earned_certs")}
            goals = {r["cert_id"]: date.fromisoformat(r["exam_date"])
                     for r in conn.execute("SELECT cert_id, exam_date FROM study_goals")}
        ready = {}
        for c in lib.certifications:
            if c.official and (c.exam or c.track) and c.id not in earned:
                r = plan.readiness(*parts_for(c))
                ready[c.id] = {"estimate": r["estimate"], "passing": r["passing"], "verdict": r["verdict"]}
        return path.build(lib.certifications, lib.programs, earned, goals, ready, today)

    @app.put("/api/earned")
    def set_earned(cert_id: str, body: EarnedIn):
        get_cert(cert_id)
        if body.passed_on > date.today():
            raise HTTPException(400, "The pass date is in the future")
        if body.expires_on and body.expires_on <= body.passed_on:
            raise HTTPException(400, "The expiry date must be after the pass date")
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO earned_certs (cert_id, passed_on, expires_on) VALUES (?,?,?) ON CONFLICT(cert_id) "
                "DO UPDATE SET passed_on=excluded.passed_on, expires_on=excluded.expires_on",
                (cert_id, body.passed_on.isoformat(), body.expires_on.isoformat() if body.expires_on else None))
        return path_map()

    @app.delete("/api/earned")
    def delete_earned(cert_id: str):
        with db.connect() as conn:
            conn.execute("DELETE FROM earned_certs WHERE cert_id=?", (cert_id,))
        return path_map()

    @app.delete("/api/plan")
    def delete_goal(cert_id: str):
        get_cert(cert_id)
        with db.connect() as conn:
            conn.execute("DELETE FROM study_goals WHERE cert_id=?", (cert_id,))
        return {"ok": True}

    @app.get("/api/interview/phrases")
    def interview_phrases():
        return [g.model_dump() for g in lib.phrase_groups]

    @app.get("/api/labs/{task_id}/solution")
    def labs_solution(task_id: str):
        task = get_task(task_id)
        return {"solution": task.solution, "docs": task.docs}

    return app


app = create_app() if os.getenv("K8S_LAB_NO_AUTOAPP") != "1" else None
