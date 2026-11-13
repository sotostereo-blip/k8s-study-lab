import os
from pathlib import Path

import pytest

os.environ["K8S_LAB_NO_AUTOAPP"] = "1"
os.environ["AI_FEEDBACK"] = "0"   # tests never call the real AI service

from fastapi.testclient import TestClient  # noqa: E402

from app.content import load_library  # noqa: E402
from app.main import create_app  # noqa: E402
from app import srs  # noqa: E402

CONTENT = Path(__file__).resolve().parents[2] / "content"


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(CONTENT, tmp_path / "test.db"))


def test_content_is_valid():
    lib = load_library(CONTENT)
    assert lib.questions and lib.glossary


def test_practice_hides_answers(client):
    data = client.get("/api/practice/next?n=5").json()
    assert len(data["questions"]) == 5
    for q in data["questions"]:
        assert "answer" not in q and "explanation" not in q


def test_answer_and_spaced_repetition(client):
    lib = load_library(CONTENT)
    q = lib.questions["kcna-fund-001"]
    r = client.post("/api/practice/answer", json={"question_id": q.id, "selected": ["a"]}).json()
    assert r["correct"] is False and r["answer"] == ["b"]
    # wrong answer -> due again now, so it comes first
    nxt = client.get("/api/practice/next?n=1").json()
    assert nxt["questions"][0]["id"] == q.id
    r = client.post("/api/practice/answer", json={"question_id": q.id, "selected": ["b"]}).json()
    assert r["correct"] is True


def test_multiple_choice_needs_exact_set(client):
    ok = client.post("/api/practice/answer", json={"question_id": "kcna-fund-006", "selected": ["c", "a"]}).json()
    partial = client.post("/api/practice/answer", json={"question_id": "kcna-fund-006", "selected": ["a"]}).json()
    assert ok["correct"] and not partial["correct"]


def test_exam_flow(client):
    s = client.post("/api/exam/start", json={"exam_id": "kcna", "questions": 8}).json()
    assert len(s["questions"]) == 8
    answers = {q["id"]: ["a"] for q in s["questions"]}
    r = client.post(f"/api/exam/{s['session_id']}/submit", json={"answers": answers}).json()
    assert r["total"] == 8 and 0 <= r["score"] <= 100
    assert client.post(f"/api/exam/{s['session_id']}/submit", json={"answers": answers}).status_code == 409
    stats = client.get("/api/stats").json()
    assert stats["exams"][0]["score"] == r["score"]


def test_leitner():
    assert srs.next_box(1, True) == 2
    assert srs.next_box(5, True) == 5
    assert srs.next_box(4, False) == 1


# ---------- hands-on labs (docker is replaced by a fake runner) ----------

LABS = Path(__file__).resolve().parents[2] / "labs"


class FakeDocker:
    """Pretends to be `docker compose`: nodes are Ready and checks pass unless told otherwise."""

    def __init__(self, failing_check: str | None = None):
        self.calls: list[list[str]] = []
        self.failing_check = failing_check

    def __call__(self, cmd, stdin, timeout):
        self.calls.append(cmd)
        if stdin and "grep -cw Ready" in stdin:
            return 0, "2"
        if stdin and self.failing_check and self.failing_check in stdin:
            return 1, "not yet"
        return 0, ""


def wait_ready(client, timeout=5):
    import time
    end = time.time() + timeout
    while time.time() < end:
        s = client.get("/api/labs/status").json()
        if s["status"] in ("ready", "error"):
            return s
        time.sleep(0.05)
    raise AssertionError("lab never became ready")


def lab_client(tmp_path, docker):
    app = create_app(CONTENT, tmp_path / "test.db", LABS, docker)
    return TestClient(app)


def test_labs_are_valid():
    lib = load_library(CONTENT)
    assert len(lib.tasks) >= 10
    for t in lib.tasks.values():
        assert (LABS / "envs" / t.environment / "compose.yaml").exists()


def test_labs_list_hides_checks_and_solution(tmp_path):
    client = lab_client(tmp_path, FakeDocker())
    data = client.get("/api/labs").json()
    assert data["tracks"][0]["id"] == "cka"
    t = data["tasks"][0]
    assert "solution" not in t and "setup" not in t
    assert all(isinstance(c, str) for c in t["checks"])
    assert data["lab"]["status"] == "idle"


def test_lab_start_check_and_stop(tmp_path):
    docker = FakeDocker(failing_check="api-history.txt")
    client = lab_client(tmp_path, docker)
    assert client.post("/api/labs/cka-wl-002/check").status_code == 409  # not running yet
    client.post("/api/labs/cka-wl-002/start")
    s = wait_ready(client)
    assert s["status"] == "ready" and s["terminal_url"]
    assert any("up" in c for c in docker.calls)

    r = client.post("/api/labs/cka-wl-002/check").json()
    assert not r["solved"] and r["passed"] == r["total"] - 1

    docker.failing_check = None
    r = client.post("/api/labs/cka-wl-002/check").json()
    assert r["solved"]
    progress = {t["id"]: t["progress"] for t in client.get("/api/labs").json()["tasks"]}
    assert progress["cka-wl-002"]["solved"] == 1 and progress["cka-wl-002"]["tries"] == 2

    assert client.post("/api/labs/stop").json()["status"] == "idle"
    assert "kubectl" in client.get("/api/labs/cka-wl-002/solution").json()["solution"]


def test_wrong_answer_explains_why(client):
    # questions sent before answering must not leak the 'why' of each option
    for q in client.get("/api/practice/next?n=20").json()["questions"]:
        assert all(set(o) == {"id", "text"} for o in q["options"])
    r = client.post("/api/practice/answer", json={"question_id": "kcna-fund-001", "selected": ["a"]}).json()
    assert not r["correct"]
    assert "a" in r["why"] and r["why"]["a"]          # why the chosen option is wrong
    assert "b" not in r["why"]                         # the right answer uses 'explanation'


def test_mock_exam_picks_compatible_tasks():
    from app.main import pick_mock_tasks
    lib = load_library(CONTENT)
    track = lib.tracks["cka"]
    for _ in range(30):
        chosen = pick_mock_tasks(list(lib.tasks.values()), track.domains, 15)
        ids = {t.id for t in chosen}
        assert len(chosen) == 15 and len(ids) == 15
        assert all(t.mock_exam for t in chosen)
        assert all(not (set(t.conflicts_with) & ids) for t in chosen)
        assert {t.domain for t in chosen} == {d.id for d in track.domains}  # every domain appears


def test_mock_exam_flow(tmp_path):
    docker = FakeDocker(failing_check="api-history.txt")
    client = lab_client(tmp_path, docker)
    assert client.get("/api/mock/current").json() is None
    s = client.post("/api/mock/start", json={"tasks": 6}).json()
    assert len(s["tasks"]) == 6 and s["minutes"] == sum(t["points"] for t in s["tasks"])
    assert all("solution" not in t and "setup" not in t for t in s["tasks"])
    assert wait_ready(client)["task_id"] == f"mock-{s['session_id']}"
    assert client.get("/api/mock/current").json()["session_id"] == s["session_id"]

    r = client.post(f"/api/mock/{s['session_id']}/submit").json()
    assert len(r["tasks"]) == 6 and all("solution" in t for t in r["tasks"])
    ids = [t["task_id"] for t in r["tasks"]]
    expected = 100.0 if "cka-wl-002" not in ids else r["score"]
    assert r["score"] == expected and r["passed"] == (r["score"] >= 66)
    assert client.post(f"/api/mock/{s['session_id']}/submit").status_code == 409
    assert client.get("/api/mock/current").json() is None
    assert client.get("/api/labs").json()["mock_exams"][0]["score"] == r["score"]


def test_mock_exam_partial_credit(tmp_path):
    lib = load_library(CONTENT)
    docker = FakeDocker()
    client = lab_client(tmp_path, docker)
    s = client.post("/api/mock/start", json={"tasks": 3}).json()
    wait_ready(client)
    first = lib.tasks[s["tasks"][0]["id"]]
    docker.failing_check = next(c for c in first.checks if not c.guard).run  # fail one work check
    r = client.post(f"/api/mock/{s['session_id']}/submit").json()
    t0 = r["tasks"][0]
    assert not t0["solved"] and 0 <= t0["earned"] < t0["points"]
    assert r["score"] < 100


def test_mock_exam_abandon(tmp_path):
    client = lab_client(tmp_path, FakeDocker())
    s = client.post("/api/mock/start", json={"tasks": 2}).json()
    wait_ready(client)
    assert client.post(f"/api/mock/{s['session_id']}/abandon").json()["ok"]
    assert client.get("/api/mock/current").json() is None
    assert client.get("/api/labs/status").json()["status"] == "idle"
    assert client.get("/api/labs").json()["mock_exams"] == []   # abandoned exams have no score


def test_mock_exam_guards(tmp_path):
    """Guards give no points; breaking one makes the task worth 0."""
    lib = load_library(CONTENT)
    docker = FakeDocker()
    client = lab_client(tmp_path, docker)
    s = client.post("/api/mock/start", json={"tasks": 35}).json()   # every compatible task
    ids = [t["id"] for t in s["tasks"]]
    assert "cka-ts-002" in ids
    wait_ready(client)
    guard = next(c for c in lib.tasks["cka-ts-002"].checks if c.guard)
    docker.failing_check = guard.run
    r = client.post(f"/api/mock/{s['session_id']}/submit").json()
    ts2 = next(t for t in r["tasks"] if t["task_id"] == "cka-ts-002")
    assert ts2["earned"] == 0 and sum(c["passed"] for c in ts2["checks"]) == len(ts2["checks"]) - 1
    assert all(t["earned"] == t["points"] for t in r["tasks"] if t["task_id"] != "cka-ts-002")


def test_every_task_has_work_checks():
    for t in load_library(CONTENT).tasks.values():
        assert any(not c.guard for c in t.checks), t.id


# ---------- English practice ----------

def test_vocabulary_practice_prioritises_lookups(client):
    lib = load_library(CONTENT)
    for _ in range(3):
        client.post("/api/english/event", json={"kind": "glossary_lookup", "ref": "taint"})
    batch = client.get("/api/english/next?n=5&kind=term").json()
    first = batch["items"][0]
    assert first["id"] == "term:taint" and first["looked_up"] == 3   # the word you looked up comes first
    assert len(first["options"]) == 4 and lib.glossary["taint"].term in first["options"]
    assert "es" not in first and "word" not in first                 # no answer leak

    ok = client.post("/api/english/answer", json={"item_id": "term:taint", "selected": "Taint"}).json()
    assert ok["correct"] and ok["es"]
    bad = client.post("/api/english/answer", json={"item_id": "term:pod", "selected": "Node"}).json()
    assert not bad["correct"] and bad["word"] == "Pod"

    stats = client.get("/api/english/stats").json()
    assert stats["practised"] == 2 and stats["most_looked_up"][0]["id"] == "term:taint"
    assert stats["events"]["glossary_lookup"] == 3


def test_vocabulary_words_are_valid_and_found_in_content():
    import re
    import yaml
    lib = load_library(CONTENT)
    if not lib.vocabulary:
        return
    def strings(node):
        if isinstance(node, str):
            yield node
        elif isinstance(node, dict):
            for v in node.values():
                yield from strings(v)
        elif isinstance(node, list):
            for v in node:
                yield from strings(v)

    text = " ".join(
        t for f in CONTENT.rglob("*.yaml")
        if f.name not in ("vocabulary.yaml", "glossary.yaml") and f.parent.name not in ("vocabulary.d", "glossary.d")
        for t in strings(yaml.safe_load(f.read_text()))
    ).lower()
    missing = [w.id for w in lib.vocabulary.values()
               if not any(re.search(rf"\b{re.escape(m.lower())}\b", text) for m in w.match)]
    assert not missing, f"words not used anywhere in the content: {missing}"


def test_stop_does_not_override_a_newer_start(tmp_path):
    """A stop that finishes after a newer start must not mark the new lab as idle."""
    import threading
    import time as _t
    from app.labs import LabManager

    gate = threading.Event()

    def slow_docker(cmd, stdin, timeout):
        if "down" in cmd:
            gate.wait(2)          # the stop's "down" is slow
        if stdin and "grep -cw Ready" in stdin:
            return 0, "1"
        return 0, ""

    m = LabManager(LABS, slow_docker, poll_seconds=0.01)
    stopper = threading.Thread(target=m.stop)
    stopper.start()
    _t.sleep(0.05)
    m.start("cka-wl-001", "single-node", 1)   # newer start while the stop is still running
    gate.set()
    stopper.join()
    end = _t.time() + 3
    while m.status()["status"] != "ready" and _t.time() < end:
        _t.sleep(0.02)
    assert m.status()["status"] == "ready" and m.status()["task_id"] == "cka-wl-001"


# ---------- several certifications ----------

def test_certifications_resolve(client):
    certs = {c["id"]: c for c in client.get("/api/certifications").json()}
    assert {"kcna", "cka"} <= set(certs)
    exams = {e["id"] for e in client.get("/api/exams").json()}
    for c in certs.values():
        assert c["exam"] or c["track"] or c["interview"]
        if c["interview"]:
            assert client.get("/api/interview/next?n=2").json()["questions"]
        if c["exam"]:
            assert c["exam"] in exams
            assert client.get(f"/api/practice/next?exam_id={c['exam']}&n=3").json()["questions"]
        if c["track"]:
            data = client.get(f"/api/labs?track_id={c['track']}").json()
            assert data["tasks"] and all(t["id"].startswith(c["track"] + "-") for t in data["tasks"])


def test_certifications_have_real_exam_facts(client):
    certs = client.get("/api/certifications").json()
    for c in certs:
        if c["interview"]:
            assert c["official"] is None
            continue
        o = c["official"]
        assert o and o["minutes"] > 0 and o["cost"] and o["valid"] and o["url"].startswith("https://")
    cks = next(c for c in certs if c["id"] == "cks")
    assert "CKA" in cks["official"]["prerequisites"]


def test_terraform_track_has_no_mock_and_starts_without_kubernetes(tmp_path):
    class TerraformDocker(FakeDocker):
        scripts: list = []

        def __call__(self, cmd, stdin, timeout):
            self.calls.append(cmd)
            self.scripts.append(stdin or "")
            if stdin and "kubectl" in stdin and "grep -cw Ready" in stdin:
                raise AssertionError("a Terraform lab must not wait for Kubernetes nodes")
            return 0, ""

    docker = TerraformDocker()
    client = lab_client(tmp_path, docker)
    assert client.post("/api/mock/start", json={"track_id": "terraform", "tasks": 3}).status_code == 400
    client.post("/api/labs/terraform-flow-001/start")
    s = wait_ready(client)
    assert s["status"] == "ready" and s["environment"] == "terraform"
    assert any("lab-ready" in sc for sc in docker.scripts)        # waited for LocalStack, not for nodes
    assert any("terraform/compose.yaml" in " ".join(c) for c in docker.calls)


def test_mock_exam_uses_the_track_environment(tmp_path):
    for track, env in [("ckad", "single-node"), ("cks", "secure-node"), ("cka", "two-node")]:
        docker = FakeDocker()
        client = lab_client(tmp_path / track, docker)
        s = client.post("/api/mock/start", json={"track_id": track, "tasks": 4}).json()
        assert len(s["tasks"]) == 4 and all(t["id"].startswith(track) for t in s["tasks"])
        assert wait_ready(client)["environment"] == env
        assert client.get(f"/api/mock/current?track_id={track}").json()["session_id"] == s["session_id"]
        assert client.get("/api/mock/current?track_id=kcna-none").json() is None


# ---------- job interviews in English ----------

def test_interview_practice_hides_answers_and_grades(client):
    lib = load_library(CONTENT)
    batch = client.get("/api/interview/next?n=50").json()
    assert batch["questions"] and batch["unseen"] == len(lib.interview_questions)
    for q in batch["questions"]:
        assert "key_points" not in q and "model_answer" not in q
    q = lib.interview_questions[batch["questions"][0]["id"]]
    rev = client.get(f"/api/interview/{q.id}/review").json()
    assert rev["key_points"] == q.key_points and rev["model_answer"]
    weak = client.post("/api/interview/grade", json={"question_id": q.id, "covered": [0], "seconds": 60, "words": 120}).json()
    assert weak["good"] is False and weak["covered"] == 1
    # weak answer -> due again now, so it comes first
    assert client.get("/api/interview/next?n=1").json()["questions"][0]["id"] == q.id
    good = client.post("/api/interview/grade", json={"question_id": q.id,
                       "covered": list(range(len(q.key_points))) + [99]}).json()
    assert good["good"] and good["covered"] == len(q.key_points)   # out-of-range indexes are ignored
    cats = {c["id"]: c for c in client.get("/api/interview/categories").json()}
    assert cats[q.category]["practised"] == 1
    assert client.get("/api/interview/stats").json()["words_per_minute"] == 120


def test_mock_interview_flow(client):
    lib = load_library(CONTENT)
    s = client.post("/api/interview/mock/start", json={"questions": 3}).json()
    qs = s["questions"]
    assert 1 <= len(qs) <= 3 and s["minutes"] >= 5
    if any(q.type == "behavioral" for q in lib.interview_questions.values()):
        assert qs[0]["type"] == "behavioral"            # interviews usually open with a behavioral question
    first = lib.interview_questions[qs[0]["id"]]
    client.post("/api/interview/grade", json={"question_id": first.id, "covered": [0, 1], "session_id": s["session_id"],
                                               "seconds": 30, "words": 60})
    other = next((q for q in lib.interview_questions if q not in [x["id"] for x in qs]), None)
    if other:
        bad = client.post("/api/interview/grade", json={"question_id": other, "covered": [], "session_id": s["session_id"]})
        assert bad.status_code == 400
    r = client.post(f"/api/interview/mock/{s['session_id']}/finish").json()
    total = sum(len(lib.interview_questions[q["id"]].key_points) for q in qs)
    assert r["score"] == round(100 * 2 / total, 1) and r["words_per_minute"] == 120
    assert r["questions"][0]["answered"] and not any(x["answered"] for x in r["questions"][1:])
    assert client.post(f"/api/interview/mock/{s['session_id']}/finish").status_code == 409
    assert client.get("/api/interview/stats").json()["mocks"][0]["score"] == r["score"]


def test_interview_phrases(client):
    groups = client.get("/api/interview/phrases").json()
    assert groups and all(g["phrases"] for g in groups)


# ---------- study plan and readiness ----------

def test_readiness_starts_unknown_and_grows_with_practice(client):
    r = client.get("/api/readiness?cert_id=kcna").json()
    assert r["verdict"] == "unknown" and r["main"] == "exam" and r["confidence"] == "low"
    before = r["estimate"]
    assert 20 <= before <= 30          # never-seen questions count as a guess
    q = client.get("/api/practice/next?exam_id=kcna&n=5").json()["questions"]
    for x in q:
        rev = client.post("/api/practice/answer", json={"question_id": x["id"], "selected": ["a"]}).json()
        client.post("/api/practice/answer", json={"question_id": x["id"], "selected": rev["answer"]})
    assert client.get("/api/readiness?cert_id=kcna").json()["parts"][0]["coverage"] > 0
    # a performance-based exam is judged by its labs
    assert client.get("/api/readiness?cert_id=cka").json()["main"] == "labs"
    assert client.get("/api/readiness?cert_id=lfcs").json()["main"] == "labs"
    assert client.get("/api/readiness?cert_id=saa").json()["main"] == "exam"
    assert client.get("/api/readiness?cert_id=nope").status_code == 404


def test_study_plan_for_an_exam_date(client):
    from datetime import date, timedelta
    assert client.get("/api/plan?cert_id=kcna").json()["goal"] is None
    past = (date.today() - timedelta(days=1)).isoformat()
    assert client.put("/api/plan?cert_id=kcna", json={"exam_date": past}).status_code == 400
    day = (date.today() + timedelta(days=40)).isoformat()
    p = client.put("/api/plan?cert_id=kcna", json={"exam_date": day, "minutes_per_day": 45}).json()
    t = p["today"]
    assert t["days_left"] == 40 and t["phase"] == "learn"
    assert [x["phase"] for x in t["roadmap"]] == ["learn", "practice", "final", "rest"]
    kinds = {x["kind"] for x in t["items"]}
    assert "new" in kinds and t["minutes"] <= 60
    # the final week brings mock exams; the day before, a short review only
    soon = client.get(f"/api/plan?cert_id=kcna&today={(date.today() + timedelta(days=35)).isoformat()}").json()["today"]
    assert soon["phase"] == "final" and any(x["kind"] == "mock" for x in soon["items"])
    eve = client.get(f"/api/plan?cert_id=kcna&today={(date.today() + timedelta(days=39)).isoformat()}").json()["today"]
    assert eve["phase"] == "rest" and not any(x["kind"] in ("new", "mock") for x in eve["items"])
    # labs plan names the tasks to solve
    client.put("/api/plan?cert_id=cka", json={"exam_date": day})
    labs = [x for x in client.get("/api/plan?cert_id=cka").json()["today"]["items"] if x["kind"] == "labs"]
    assert labs and labs[0]["tasks"][0].startswith("cka-")
    assert client.delete("/api/plan?cert_id=kcna").json()["ok"]
    assert client.get("/api/plan?cert_id=kcna").json()["goal"] is None


def test_domc_walk_rules():
    from app import domc
    lib = load_library(CONTENT)
    single = next(q for q in lib.questions_for("dca") if q.type == "single")
    right = single.answer[0]
    seed = "s1"
    first = domc.walk(seed, single, {})
    assert first["next"] and not first["done"]
    # YES to the right option decides it (maybe one extra unscored option follows)
    order = domc.order(seed, single)
    responses = {o: False for o in order[:order.index(right)]} | {right: True}
    step = domc.walk(seed, single, responses)
    assert step["selected"] == [right]
    if not step["done"]:
        step = domc.walk(seed, single, responses | {step["next"]: True})
        assert step["done"] and step["selected"] == [right]   # the extra answer is not scored
    # NO to the right option ends it, wrong
    responses = {o: False for o in order[:order.index(right) + 1]}
    step = domc.walk(seed, single, responses)
    assert step["selected"] == []
    multi = next((q for q in lib.questions_for("dca") if q.type == "multiple"), None)
    if multi:
        order = domc.order(seed, multi)
        wrong = next(o for o in order if o not in multi.answer)
        before = order[:order.index(wrong)]
        responses = {o: (o in multi.answer) for o in before} | {wrong: True}
        selected = domc.walk(seed, multi, responses)["selected"]
        if set(multi.answer) <= set(before):   # decided right before the wrong option appears
            assert set(selected) == set(multi.answer)
        else:                                  # a YES to a wrong option ends it, wrong
            assert wrong in selected


def test_dca_mock_exam_uses_domc(client):
    s = client.post("/api/exam/start", json={"exam_id": "dca", "questions": 20}).json()
    domc_qs = [q for q in s["questions"] if q.get("style") == "domc"]
    assert len(domc_qs) == round(20 * 42 / 55)
    assert all(q["options"] == [] for q in domc_qs)    # options come one at a time
    lib = load_library(CONTENT)
    answers, responses = {}, {}
    for q in domc_qs:   # answer YES only to right options
        r, seen = {}, 0
        while True:
            step = client.post(f"/api/exam/{s['session_id']}/domc", json={"question_id": q["id"], "responses": r}).json()
            if step["done"]:
                break
            r[step["next"]["id"]] = step["next"]["id"] in lib.questions[q["id"]].answer
            seen += 1
            assert seen <= 6
        responses[q["id"]] = r
    for q in s["questions"]:
        if q.get("style") != "domc":
            answers[q["id"]] = lib.questions[q["id"]].answer
    res = client.post(f"/api/exam/{s['session_id']}/submit", json={"answers": answers, "domc": responses}).json()
    assert res["score"] == 100
    assert all(r["domc"] for r in res["review"] if r.get("style") == "domc")
    plain = client.post("/api/exam/start", json={"exam_id": "dca", "questions": 10, "domc": False}).json()
    assert not any(q.get("style") for q in plain["questions"])
    kcna = client.post("/api/exam/start", json={"exam_id": "kcna", "questions": 10}).json()
    bad = client.post(f"/api/exam/{kcna['session_id']}/domc", json={"question_id": kcna["questions"][0]["id"]})
    assert bad.status_code == 400


def test_esl_extra_time(client):
    full = client.post("/api/exam/start", json={"exam_id": "saa", "questions": 65, "esl": True}).json()
    assert full["minutes"] == 130 + 30 and full["conditions"]["esl"]
    no = client.post("/api/exam/start", json={"exam_id": "kcna", "questions": 60, "esl": True}).json()
    assert no["minutes"] == 90 and not no["conditions"]["esl"]   # KCNA gives no ESL extra time here


def test_hands_on_tracks_list_real_exam_rules(client):
    for track in ("cka", "ckad", "cks", "lfcs"):
        t = client.get(f"/api/labs?track_id={track}").json()["tracks"][0]
        assert t["exam_rules"]["source"].startswith("https://docs.linuxfoundation.org")
    assert client.get("/api/labs?track_id=lfcs").json()["tracks"][0]["exam_rules"]["docs"] == []


def test_path_map_levels_prerequisites_and_expiry(client):
    m = client.get("/api/path?today=2026-11-12").json()
    by = {c["id"]: c for c in m["certs"]}
    assert "interview" not in by
    assert by["kcna"]["level"] == 0 and by["cka"]["level"] == 1 and by["cks"]["level"] == 2
    assert by["cks"]["missing_requires"] == ["cka"]
    assert m["programs"][0]["id"] == "kubestronaut" and not m["programs"][0]["complete"]
    # pass the CKA: expires 2 years later
    client.put("/api/earned?cert_id=cka", json={"passed_on": "2025-01-20"})
    m = client.get("/api/path?today=2026-11-12").json()
    cka = next(c for c in m["certs"] if c["id"] == "cka")
    assert cka["expires_on"] == "2027-01-20" and cka["status"] == "expiring"
    assert m["reminders"][0]["cert_id"] == "cka"
    assert next(c for c in m["certs"] if c["id"] == "cks")["missing_requires"] == []
    # a CKS passed after 2026-06-18 extends the CKA to the same date
    client.put("/api/earned?cert_id=cks", json={"passed_on": "2026-07-01"})
    m = client.get("/api/path?today=2026-11-12").json()
    cka = next(c for c in m["certs"] if c["id"] == "cka")
    assert cka["expires_on"] == "2028-07-01" and cka["extended_by"] == "CKS" and cka["status"] == "active"
    # expired, manual expiry date, delete, and bad dates
    client.put("/api/earned?cert_id=saa", json={"passed_on": "2023-01-10"})
    assert next(c for c in client.get("/api/path?today=2026-11-12").json()["certs"] if c["id"] == "saa")["status"] == "expired"
    client.put("/api/earned?cert_id=saa", json={"passed_on": "2023-01-10", "expires_on": "2027-06-10"})
    assert next(c for c in client.get("/api/path?today=2026-11-12").json()["certs"] if c["id"] == "saa")["status"] == "active"
    client.delete("/api/earned?cert_id=saa")
    assert next(c for c in client.get("/api/path").json()["certs"] if c["id"] == "saa")["status"] == "none"
    assert client.put("/api/earned?cert_id=kcna", json={"passed_on": "2999-01-01"}).status_code == 400


def test_path_warns_when_exam_needs_a_missing_prerequisite(client):
    from datetime import date, timedelta
    day = (date.today() + timedelta(days=30)).isoformat()
    client.put("/api/plan?cert_id=cks", json={"exam_date": day})
    m = client.get("/api/path").json()
    assert next(c for c in m["certs"] if c["id"] == "cks")["status"] == "goal"
    assert any(r["cert_id"] == "cks" and "CKA" in r["text"] for r in m["reminders"])


class FakeClaude:
    """Stands in for anthropic.Anthropic(): records the request, returns fixed feedback."""

    def __init__(self, stop_reason="end_turn"):
        from types import SimpleNamespace
        self.calls = []
        self.stop_reason = stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse))

    def parse(self, **kw):
        from types import SimpleNamespace
        from app.ai import Feedback
        self.calls.append(kw)
        fb = Feedback(summary="Clear and short.", key_points=[
            {"index": 0, "covered": True, "note": "You explained it."},
            {"index": 1, "covered": False, "note": "Missing."},
            {"index": 99, "covered": True, "note": "bad index"}],
            strengths=["Clear"], improve=["Give an example"],
            english=[{"said": "more better", "better": "better", "why": "Use one comparative."}],
            better_answer="A better answer.")
        return SimpleNamespace(stop_reason=self.stop_reason, model="claude-opus-5-5",
                               parsed_output=None if self.stop_reason != "end_turn" else fb)


def test_ai_feedback_is_off_without_a_key(client):
    assert client.get("/api/ai/status").json()["enabled"] is False
    qid = next(iter(load_library(CONTENT).interview_questions))
    r = client.post("/api/interview/feedback", json={"question_id": qid, "answer": "one two three four five six"})
    assert r.status_code == 503


def test_ai_feedback_with_a_client(tmp_path):
    from app.ai import Coach
    fake = FakeClaude()
    c = TestClient(create_app(CONTENT, tmp_path / "t.db", coach=Coach(client=fake)))
    assert c.get("/api/ai/status").json() == {"enabled": True, "model": "claude-opus-5-5"}
    qid = next(iter(load_library(CONTENT).interview_questions))
    assert c.post("/api/interview/feedback", json={"question_id": qid, "answer": "too short"}).status_code == 400
    r = c.post("/api/interview/feedback", json={"question_id": qid, "answer": "I think it is more better to use a pod here", "seconds": 40}).json()
    assert r["covered"] == [0] and all(k["index"] < 99 for k in r["key_points"])
    kw = fake.calls[0]
    assert kw["fallbacks"] == "default" and "more better" in kw["messages"][0]["content"]
    refused = TestClient(create_app(CONTENT, tmp_path / "u.db", coach=Coach(client=FakeClaude("refusal"))))
    assert refused.post("/api/interview/feedback", json={"question_id": qid, "answer": "one two three four five six"}).status_code == 502


def test_lab_teardown_runs_before_down(tmp_path):
    docker = FakeDocker()
    client = lab_client(tmp_path, docker)
    client.post("/api/labs/lfcs-stor-004/start")
    wait_ready(client)
    client.post("/api/labs/stop")
    kinds = ["teardown" if c[:2] == ["sh", "-c"] and "lab-teardown" in c[2] else "down" if "down" in c else None
             for c in docker.calls]
    kinds = [k for k in kinds if k]
    # every "docker compose down" comes right after the teardown of the lab containers
    assert kinds and all(kinds[i - 1] == "teardown" for i, k in enumerate(kinds) if k == "down")


def test_new_labs_exist():
    lib = load_library(CONTENT)
    for t in ("lfcs-stor-004", "lfcs-stor-005", "lfcs-stor-006", "capa-ev-001", "capa-ev-002", "gha-sec-004"):
        assert t in lib.tasks
    assert "argo-events" in {d.id for d in lib.tracks["capa"].domains}


def test_exam_facts_age(client):
    from datetime import date
    from app.facts import age_months
    assert age_months("2026-11", date(2027, 5, 1)) == 6 and age_months("2026-11", date(2027, 6, 1)) == 7
    now = {c["id"]: c for c in client.get("/api/certifications?today=2026-12-01").json()}
    later = {c["id"]: c for c in client.get("/api/certifications?today=2027-08-01").json()}
    assert now["cka"]["facts_stale"] is False and later["cka"]["facts_stale"] is True
    assert "facts_stale" not in now["interview"]
