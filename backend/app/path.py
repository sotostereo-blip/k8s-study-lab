"""Certification path map: suggested order, prerequisites, what you passed and when it expires.

Pure functions: main.py reads the passed certifications, study goals and readiness from the
database and calls `build`.
"""
from __future__ import annotations

from datetime import date

EXPIRING_DAYS = 90   # remind you this many days before a certification expires


def add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:          # 29 February
        return d.replace(year=d.year + years, day=28)


def levels(certs: list) -> dict[str, int]:
    """Column on the map: 0 for certifications with nothing before them, else 1 + the deepest one before."""
    by_id = {c.id: c for c in certs}
    memo: dict[str, int] = {}

    def level(cid: str, stack: tuple = ()) -> int:
        if cid in memo:
            return memo[cid]
        c = by_id[cid]
        before = [b for b in c.after + (c.official.requires if c.official else []) if b in by_id and b not in stack]
        memo[cid] = 1 + max((level(b, stack + (cid,)) for b in before), default=-1)
        return memo[cid]

    return {c.id: level(c.id) for c in certs}


def build(certs: list, programs: list, earned: dict[str, dict], goals: dict[str, date],
          ready: dict[str, dict], today: date) -> dict:
    """earned: {cert_id: {"passed_on": date, "expires_on": date | None (manual date)}}"""
    certs = [c for c in certs if c.official]
    lvl = levels(certs)
    expiry: dict[str, date] = {}
    extended_by: dict[str, str] = {}
    for c in certs:
        e = earned.get(c.id)
        if e:
            expiry[c.id] = e.get("expires_on") or (
                add_years(e["passed_on"], c.official.valid_years) if c.official.valid_years else None)
    for c in certs:   # e.g. a CKS passed on/after 2026-06-18 extends the CKA to the same date
        e = earned.get(c.id)
        for other, since in c.official.extends.items():
            if e and other in expiry and expiry.get(c.id) and e["passed_on"] >= date.fromisoformat(since) \
                    and expiry[c.id] > expiry[other]:
                expiry[other] = expiry[c.id]
                extended_by[other] = c.short

    def status(cid: str) -> str:
        if cid not in earned:
            return "goal" if cid in goals and goals[cid] >= today else "none"
        exp = expiry.get(cid)
        if exp is None:
            return "active"
        days = (exp - today).days
        return "expired" if days < 0 else "expiring" if days <= EXPIRING_DAYS else "active"

    def holds(cid: str) -> bool:
        return status(cid) in ("active", "expiring")

    names = {c.id: c.short for c in certs}
    items, reminders = [], []
    for c in certs:
        st = status(c.id)
        exp = expiry.get(c.id)
        missing = [r for r in c.official.requires if not holds(r)]
        item = {
            "id": c.id, "short": c.short, "name": c.name, "area": c.area, "level": lvl[c.id],
            "after": c.after, "requires": c.official.requires, "missing_requires": missing,
            "valid_years": c.official.valid_years, "renewal": c.official.renewal, "status": st,
            "passed_on": earned[c.id]["passed_on"].isoformat() if c.id in earned else None,
            "expires_on": exp.isoformat() if exp else None,
            "days_left": (exp - today).days if exp else None,
            "extended_by": extended_by.get(c.id),
            "exam_date": goals[c.id].isoformat() if c.id in goals else None,
            "readiness": ready.get(c.id),
        }
        items.append(item)
        if st == "expiring":
            reminders.append({"cert_id": c.id, "level": "warn", "days_left": item["days_left"],
                              "text": f"Your {c.short} expires in {item['days_left']} days ({exp.isoformat()}). {c.official.renewal}"})
        elif st == "expired":
            reminders.append({"cert_id": c.id, "level": "ko", "days_left": item["days_left"],
                              "text": f"Your {c.short} expired on {exp.isoformat()}. {c.official.renewal}"})
        if c.id in goals and goals[c.id] >= today and missing:
            reminders.append({"cert_id": c.id, "level": "warn", "days_left": None,
                              "text": f"Your {c.short} exam is on {goals[c.id].isoformat()}, but you must hold the "
                                      f"{', '.join(names.get(m, m) for m in missing)} first. Record it here when you pass it."})
    progs = []
    for p in programs:
        active = [cid for cid in p.certs if holds(cid)]
        exps = [expiry[cid] for cid in p.certs if cid in expiry]
        progs.append({"id": p.id, "name": p.name, "description": p.description, "url": p.url,
                      "certs": p.certs, "active": active, "missing": [c for c in p.certs if c not in active],
                      "complete": len(active) == len(p.certs),
                      "until": min(exps).isoformat() if len(active) == len(p.certs) and exps else None})
    reminders.sort(key=lambda r: (r["level"] != "ko", r["days_left"] if r["days_left"] is not None else 9999))
    return {"today": today.isoformat(), "certs": items, "programs": progs, "reminders": reminders,
            "expiring_days": EXPIRING_DAYS}
