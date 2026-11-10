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
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
