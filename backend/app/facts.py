"""How old the real exam facts are (content/certifications.yaml `official.checked`).

Prices, question counts and rules change. Facts older than MAX_AGE_MONTHS are shown as
"may be out of date" in the app, and scripts/check_facts.py lists them.
"""
from __future__ import annotations

from datetime import date

MAX_AGE_MONTHS = 6


def age_months(checked: str, today: date) -> int:
    """Whole months between the month the facts were checked ("YYYY-MM") and today."""
    year, month = (int(x) for x in checked.split("-"))
    return (today.year - year) * 12 + today.month - month


def report(certs: list, today: date, max_months: int = MAX_AGE_MONTHS) -> list[dict]:
    out = []
    for c in certs:
        if not c.official:
            continue
        age = age_months(c.official.checked, today)
        out.append({"id": c.id, "short": c.short, "checked": c.official.checked, "months": age,
                    "stale": age > max_months, "url": c.official.url})
    return out
