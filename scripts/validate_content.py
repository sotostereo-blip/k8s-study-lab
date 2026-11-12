#!/usr/bin/env python3
"""Validate everything in content/. Run before every commit or pull request."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.content import load_library  # noqa: E402


def main() -> int:
    content = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "content"
    try:
        lib = load_library(content)
    except ValueError as e:
        print("Content errors found:\n" + str(e))
        return 1
    for exam in lib.exams.values():
        print(f"{exam.id}: {len(lib.questions_for(exam.id))} questions")
        for d in exam.domains:
            print(f"  {d.name:<40} {len(lib.questions_for(exam.id, d.id)):>3}  (weight {d.weight}%)")
    print(f"glossary: {len(lib.glossary)} terms")
    print(f"vocabulary (exam English): {len(lib.vocabulary)} words")
    for track in lib.tracks.values():
        tasks = [t for t in lib.tasks.values() if t.id.startswith(f"{track.id}-")]
        print(f"{track.id} labs: {len(tasks)} tasks")
        for d in track.domains:
            print(f"  {d.name:<52} {sum(t.domain == d.id for t in tasks):>3}  (weight {d.weight}%)")
        for t in tasks:
            if not (ROOT / "labs" / "envs" / t.environment / "compose.yaml").exists():
                print(f"error: {t.id}: labs/envs/{t.environment}/compose.yaml not found")
                return 1
    # Warn (not fail) when the right answer stands out by length.
    for q in lib.questions.values():
        if q.type != "single":
            continue
        right = next(o for o in q.options if o.id == q.answer[0])
        longest_wrong = max(len(o.text) for o in q.options if o.id != right.id)
        if len(right.text) > 1.6 * longest_wrong and len(right.text) > 25:
            print(f"warning: {q.id}: correct option is much longer than the others")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
