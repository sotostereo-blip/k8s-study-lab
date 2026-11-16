"""Mock exam history: scores over time and per-domain trends. Pure functions (tested in test_history)."""
from __future__ import annotations

import json


def exam_point(row) -> dict:
    """A finished multiple-choice mock exam -> {date, score, domains: {id: percent}}."""
    raw = json.loads(row["domains"] or "{}")
    return {"date": row["finished_at"], "score": row["score"],
            "domains": {d: round(100 * v["correct"] / v["total"], 1) for d, v in raw.items() if v["total"]}}


def lab_point(row) -> dict:
    """A finished lab mock exam -> per-domain percent of the points of its tasks."""
    got: dict[str, list[float]] = {}
    for r in json.loads(row["results"] or "[]"):
        e = got.setdefault(r["domain"], [0.0, 0.0])
        e[0] += r["earned"]
        e[1] += r["points"]
    return {"date": row["finished_at"], "score": row["score"],
            "domains": {d: round(100 * a / b, 1) for d, (a, b) in got.items() if b}}


def domain_trends(points: list[dict], domains) -> list[dict]:
    """Per official domain: first result, average of the last 3, and the change between them."""
    out = []
    for d in domains:
        vals = [p["domains"][d.id] for p in points if d.id in p["domains"]]
        last3 = round(sum(vals[-3:]) / len(vals[-3:]), 1) if vals else None
        out.append({"id": d.id, "name": d.name, "weight": d.weight, "count": len(vals),
                    "first": vals[0] if vals else None, "recent": last3,
                    "change": round(last3 - vals[0], 1) if len(vals) > 1 else None})
    return out


def series(kind: str, label: str, passing: int, points: list[dict], domains) -> dict:
    return {"kind": kind, "label": label, "passing_score": passing, "points": points,
            "domains": domain_trends(points, domains)}
