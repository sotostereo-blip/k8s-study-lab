#!/usr/bin/env python3
"""Verify lab tasks on REAL lab environments (Docker required).

  tasks mode: for each task -> setup, checks must NOT all pass, solve, checks must all pass.
  mock mode:  all mock-exam tasks of a track in ONE environment -> combined setup;
              every work check fails and every guard passes (doing nothing scores 0);
              solve everything; every check passes (all solutions score 100%).

Examples
  python scripts/verify_labs.py tasks cka-ts-001 cka-net-003
  python scripts/verify_labs.py tasks --track ckad --project verify-ckad --port 7701
  python scripts/verify_labs.py mock cka --exclude cka-net-004 cka-wl-006

The solution used is the task's `auto_solution` if set, otherwise its `solution`.
Use a different --project/--port to run several verifications at the same time.
At most VERIFY_SLOTS (default 2) verifications run at once on this machine; the others wait,
so parallel runs do not exhaust Docker's memory.
"""
from __future__ import annotations

import argparse
import fcntl
import os
import tempfile
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("K8S_LAB_NO_AUTOAPP", "1")

from app.content import load_library  # noqa: E402
from app.main import mock_setup_script  # noqa: E402
from app.labs import TEARDOWN  # noqa: E402


class Env:
    def __init__(self, project: str, port: int):
        self.project, self.port, self.name = project, port, None

    def dc(self, *args, stdin=None, timeout=900):
        cmd = ["docker", "compose", "-p", self.project]
        if self.name:
            cmd += ["-f", str(ROOT / "labs" / "envs" / self.name / "compose.yaml")]
        p = subprocess.run(cmd + list(args), input=stdin, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "TERMINAL_PORT": str(self.port)})
        return p.returncode, (p.stdout + p.stderr).strip()

    def sh(self, script, timeout=300):
        try:
            return self.dc("exec", "-T", "toolbox", "bash", "-s", stdin="set -o pipefail\n" + script, timeout=timeout)
        except subprocess.TimeoutExpired:
            return 124, "timeout"

    def up(self, name: str, spec):
        """spec: the track's LabEnvironment (nodes, ready command)."""
        self.down()
        self.name = name
        rc, out = self.dc("up", "-d", "--build", "--quiet-pull")
        if rc:
            sys.exit(f"docker compose up failed:\n{out[-1500:]}")
        steps = []
        if spec.nodes:
            steps.append(f"[ \"$(kubectl get nodes --no-headers 2>/dev/null | grep -cw Ready)\" -ge {spec.nodes} ] && "
                         "kubectl get sa default >/dev/null 2>&1 && "
                         "kubectl -n kube-system rollout status deploy coredns --timeout=5s >/dev/null 2>&1")
        if spec.ready_command:
            steps.append(spec.ready_command)
        for step in steps:
            deadline = time.time() + max(360, spec.ready_timeout)
            while self.sh(step, 60)[0] != 0:
                if time.time() > deadline:
                    sys.exit(f"environment {name} did not become ready: {step[:80]}")
                time.sleep(3)

    def down(self):
        # release loop devices, LVM volumes and swap first (see labs/toolbox-linux/lab-teardown)
        subprocess.run(["sh", "-c", TEARDOWN.format(project=self.project)], capture_output=True, timeout=180)
        name, self.name = self.name, None
        self.dc("down", "-v", "--remove-orphans", timeout=300)
        self.name = name


def take_slot():
    """Block until one of VERIFY_SLOTS machine-wide slots is free; keep the file open to hold it."""
    slots = int(os.getenv("VERIFY_SLOTS", "2"))
    waited = False
    while True:
        for i in range(slots):
            f = open(Path(tempfile.gettempdir()) / f"k8s-study-lab-verify-{i}.lock", "w")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return f
            except OSError:
                f.close()
        if not waited:
            print(f"waiting for a free verification slot ({slots} in use)…", flush=True)
            waited = True
        time.sleep(10)


def checks(env: Env, task) -> list[bool]:
    return [env.sh(c.run, 120)[0] == 0 for c in task.checks]


def solve(env: Env, task):
    rc, out = env.sh(task.auto_solution or task.solution, 600)
    if rc:
        print(f"   note: solution exited {rc}: {out[-200:]}", flush=True)


def wait_all(env: Env, task, tries=30) -> list[bool]:
    for _ in range(tries):
        res = checks(env, task)
        if all(res):
            break
        time.sleep(4)
    return res


def mode_tasks(lib, env: Env, ids: list[str], fresh: bool) -> bool:
    tasks = [lib.tasks[i] for i in ids]
    ok_all, current = True, None
    for t in sorted(tasks, key=lambda t: t.environment):
        spec = lib.tracks[t.id.split("-")[0]].environments[t.environment]
        if fresh or current != t.environment:
            env.up(t.environment, spec)
            current = t.environment
        if t.setup.strip():
            rc, out = env.sh(t.setup, 600)
            if rc:
                print(f"{t.id:16} BAD setup failed: {out[-400:]}", flush=True)
                ok_all = False
                continue
        time.sleep(3)
        before = checks(env, t)
        solve(env, t)
        after = wait_all(env, t)
        good = not all(before) and all(after)
        ok_all &= good
        print(f"{t.id:16} {'OK ' if good else 'BAD'} before={before} after={after}", flush=True)
    env.down()
    return ok_all


def mode_mock(lib, env: Env, track_id: str, exclude: set[str]) -> bool:
    track = lib.tracks[track_id]
    tasks = [t for t in lib.tasks_for(track_id) if t.mock_exam and t.id not in exclude]
    ids = {t.id for t in tasks}
    clash = [(t.id, c) for t in tasks for c in t.conflicts_with if c in ids]
    if clash:
        sys.exit(f"these tasks conflict, exclude one of each pair: {clash}")
    env.up(track.mock_environment, track.environments[track.mock_environment])
    rc, out = env.sh(mock_setup_script(tasks), 120 + 120 * len(tasks))
    if rc:
        sys.exit(f"combined setup failed:\n{out[-800:]}")
    time.sleep(30)
    ok_all = True
    for t in tasks:   # doing nothing must score 0
        res = [(c.guard, env.sh(c.run, 120)[0] == 0) for c in t.checks]
        wrong = [i for i, (g, ok) in enumerate(res) if ok != g]
        if wrong:
            ok_all = False
            print(f"{t.id:16} BAD baseline: checks {wrong} (work checks must fail, guards must pass)", flush=True)
    for t in tasks:
        solve(env, t)
    time.sleep(20)
    for t in tasks:   # every solution together must score 100%
        res = wait_all(env, t, 20)
        ok_all &= all(res)
        print(f"{t.id:16} {'OK ' if all(res) else 'BAD'} {res}", flush=True)
    env.down()
    return ok_all


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["tasks", "mock"])
    ap.add_argument("ids", nargs="*", help="task ids (tasks mode) or one track id (mock mode)")
    ap.add_argument("--track", help="tasks mode: verify every task of this track")
    ap.add_argument("--exclude", nargs="*", default=[], help="mock mode: task ids to leave out")
    ap.add_argument("--fresh", action="store_true", help="tasks mode: new environment for every task")
    ap.add_argument("--project", default="verify-labs", help="docker compose project name")
    ap.add_argument("--port", type=int, default=7699, help="host port for the web terminal")
    a = ap.parse_args()
    lib = load_library(ROOT / "content", strict=False)   # other content may be mid-edit
    env = Env(a.project, a.port)
    slot = take_slot()  # noqa: F841  (held until the process exits)
    try:
        if a.mode == "tasks":
            ids = a.ids or [t.id for t in lib.tasks_for(a.track)] if a.track else a.ids
            ok = mode_tasks(lib, env, ids, a.fresh)
        else:
            ok = mode_mock(lib, env, a.ids[0], set(a.exclude))
    finally:
        env.down()
    print("ALL OK" if ok else "SOME TASKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
