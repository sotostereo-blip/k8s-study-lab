import json
import os
from pathlib import Path

os.environ["K8S_LAB_NO_AUTOAPP"] = "1"
os.environ["AI_FEEDBACK"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app import history  # noqa: E402
from app.content import Domain, load_library  # noqa: E402
from app.main import create_app  # noqa: E402

CONTENT = Path(__file__).resolve().parents[2] / "content"


def test_domain_trend_compares_first_with_last_three():
    doms = [Domain(id="a", name="A", weight=60), Domain(id="b", name="B", weight=40)]
    pts = [{"domains": {"a": 50}}, {"domains": {"a": 60, "b": 70}}, {"domains": {"a": 70}}, {"domains": {"a": 80}}]
    a, b = history.domain_trends(pts, doms)
    assert (a["first"], a["recent"], a["change"], a["count"]) == (50, 70.0, 20.0, 4)
    assert (b["first"], b["change"]) == (70, None)     # one result: no trend yet


def test_lab_mock_points_per_domain():
    row = {"finished_at": "2026-11-01 10:00:00", "score": 50.0, "results": json.dumps([
        {"domain": "x", "earned": 4, "points": 8}, {"domain": "x", "earned": 6, "points": 6},
        {"domain": "y", "earned": 0, "points": 5}])}
    assert history.lab_point(row)["domains"] == {"x": 71.4, "y": 0.0}


def test_history_endpoint_after_mock_exams(tmp_path):
    lib = load_library(CONTENT)
    c = TestClient(create_app(CONTENT, tmp_path / "p.db"))
    for good in (True, False):
        s = c.post("/api/exam/start", json={"exam_id": "kcna", "questions": 10}).json()
        ans = {q["id"]: list(lib.questions[q["id"]].answer) if good else [] for q in s["questions"]}
        c.post(f"/api/exam/{s['session_id']}/submit", json={"answers": ans})
    h = c.get("/api/history?cert_id=kcna").json()
    (exam,) = h["series"]
    assert [p["score"] for p in exam["points"]] == [100.0, 0.0]
    assert exam["passing_score"] == 75
    assert any(d["change"] is not None and d["change"] < 0 for d in exam["domains"])
    cka = c.get("/api/history?cert_id=cka").json()["series"]
    assert cka[0]["kind"] == "labs" and cka[0]["points"] == []
