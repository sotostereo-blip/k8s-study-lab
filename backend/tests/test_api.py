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
