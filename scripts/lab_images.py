#!/usr/bin/env python3
"""List the lab images built from labs/ (used by .github/workflows/lab-images.yml).

  python scripts/lab_images.py                         # table: image, build context, bases
  python scripts/lab_images.py --github-output REGISTRY  # base=<json> and rest=<json> build matrices

Base images (other lab images are built FROM them) must be published first; the others get a
`build_contexts` entry so `FROM k8s-study-lab/toolbox:3` resolves to the published base image.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.labs import bases_of, lab_builds, prebuilt_name  # noqa: E402


def matrices(registry: str) -> tuple[list[dict], list[dict]]:
    builds = lab_builds(ROOT / "labs")
    bases = {b for _, _, ctx in builds.values() for b in bases_of(ctx)}
    base, rest = [], []
    for image, (_, _, ctx) in sorted(builds.items()):
        item = {"image": image, "remote": prebuilt_name(registry, image),
                "context": str(ctx.relative_to(ROOT)),
                "build_contexts": "\n".join(f"{b}=docker-image://{prebuilt_name(registry, b)}"
                                            for b in bases_of(ctx))}
        (base if image in bases else rest).append(item)
    return base, rest


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--github-output":
        base, rest = matrices(sys.argv[2])
        print(f"base={json.dumps(base)}")
        print(f"rest={json.dumps(rest)}")
        return 0
    for image, (env, service, ctx) in sorted(lab_builds(ROOT / "labs").items()):
        print(f"{image:40} {str(ctx.relative_to(ROOT)):28} {env}/{service}  FROM {bases_of(ctx) or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
