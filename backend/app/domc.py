"""DOMC (Discrete Option Multiple Choice), as in the Docker DCA exam.

The options of a question appear one at a time, in random order, and you answer YES or NO to
each one. You cannot go back. The question ends as soon as the answer is decided:

- one right answer: a YES ends it (right or wrong), and a NO to the right option ends it (wrong);
- several right answers: a YES to a wrong option ends it (wrong), and so does answering every
  right option.

Like real DOMC exams, sometimes one more option is shown after the question is already decided,
so the number of options you see does not tell you if you were right. That answer is not scored.

Pure functions: the order and the extra option come from a seed (session id + question id), so
the server keeps no state between calls.
"""
from __future__ import annotations

import random

from .content import Question


def order(seed: str, q: Question) -> list[str]:
    ids = [o.id for o in q.options]
    random.Random(f"{seed}:{q.id}").shuffle(ids)
    return ids


def walk(seed: str, q: Question, responses: dict[str, bool]) -> dict:
    """Follow the YES/NO answers given so far. Returns the next option to show (or None when
    the question is over) and the options answered YES before it was decided (the scored answer)."""
    ids = order(seed, q)
    right = set(q.answer)
    shown: list[str] = []
    selected: list[str] = []
    decided = False
    for oid in ids:
        if decided:
            break
        if oid not in responses:
            return {"next": oid, "done": False, "selected": selected, "shown": len(shown)}
        shown.append(oid)
        yes = bool(responses[oid])
        if yes:
            selected.append(oid)
        if q.type == "single":
            decided = yes or oid in right
        else:
            decided = (yes and oid not in right) or right <= set(shown)
    rest = [o for o in ids if o not in shown]
    extra = random.Random(f"{seed}:{q.id}:extra").random() < 0.5
    if extra and rest and rest[0] not in responses:
        return {"next": rest[0], "done": False, "selected": selected, "shown": len(shown)}
    return {"next": None, "done": True, "selected": selected, "shown": len(shown)}
