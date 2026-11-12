import os
from pathlib import Path

import pytest

os.environ["K8S_LAB_NO_AUTOAPP"] = "1"

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
        t for f in CONTENT.rglob("*.yaml") if f.name not in ("vocabulary.yaml", "glossary.yaml")
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
        assert c["exam"] or c["track"]
        if c["exam"]:
            assert c["exam"] in exams
            assert client.get(f"/api/practice/next?exam_id={c['exam']}&n=3").json()["questions"]
        if c["track"]:
            data = client.get(f"/api/labs?track_id={c['track']}").json()
            assert data["tasks"] and all(t["id"].startswith(c["track"] + "-") for t in data["tasks"])
