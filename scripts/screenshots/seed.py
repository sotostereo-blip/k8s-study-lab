"""Fill a THROWAWAY database (through the API on :8000) with realistic KCNA/CKA progress for the
README screenshots. See capture.mjs. Never run it against your real progress."""
import json, random, sys, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.content import load_library
lib = load_library(ROOT / "content")
API = "http://localhost:8000/api"
def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))
random.seed(7)
rate = {"kcna-fund": .82, "kcna-orch": .7, "kcna-arch": .76, "kcna-deliv": .6}
qs = [q for q in lib.questions.values() if q.id.startswith("kcna-")]
for q in random.sample(qs, 110):
    dom = q.id.rsplit("-", 1)[0]
    right = random.random() < rate.get(dom, .7)
    sel = list(q.answer) if right else [next(o.id for o in q.options if o.id not in q.answer)]
    call("POST", "/practice/answer", {"question_id": q.id, "selected": sel})
for target in (.68, .74, .79):
    s = call("POST", "/exam/start", {"exam_id": "kcna"})
    ans = {}
    for qq in s["questions"]:
        q = lib.questions[qq["id"]]
        ans[q.id] = list(q.answer) if random.random() < target else [next(o.id for o in q.options if o.id not in q.answer)]
    r = call("POST", f"/exam/{s['session_id']}/submit", {"answers": ans})
    print("mock", r.get("score"))
call("PUT", "/plan?cert_id=kcna", {"exam_date": "2026-12-18", "minutes_per_day": 60})
call("PUT", "/plan?cert_id=cka", {"exam_date": "2027-02-26", "minutes_per_day": 90})
for cert, passed in (("kcna", "2025-12-02"), ("cka", "2026-03-10")):
    call("PUT", f"/earned?cert_id={cert}", {"passed_on": passed})
print(call("GET", "/progress/summary"))
