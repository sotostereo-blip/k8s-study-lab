"""Run hands-on labs: a small k3s cluster + a browser terminal, started with docker compose.

Only one lab runs at a time (like the real exam, you work in one environment).
Starting a lab tears down the previous one, so every lab starts from a clean cluster.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .content import LabTask

# runner(cmd, stdin, timeout) -> (exit_code, combined output)
Runner = Callable[[list[str], str | None, float], tuple[int, str]]


def subprocess_runner(cmd: list[str], stdin: str | None, timeout: float) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout:.0f}s"
    except FileNotFoundError:
        return 127, "docker not found: install Docker Desktop and make sure it is running"
    return p.returncode, (p.stdout + p.stderr).strip()


@dataclass
class LabState:
    status: str = "idle"  # idle | starting | ready | error | stopping
    task_id: str | None = None
    environment: str | None = None
    started_at: float | None = None  # when the lab became ready (timer starts here)
    log: list[str] = field(default_factory=list)
    error: str | None = None

    def public(self, terminal_url: str) -> dict:
        return {
            "status": self.status,
            "task_id": self.task_id,
            "environment": self.environment,
            "elapsed_seconds": round(time.time() - self.started_at) if self.started_at else None,
            "log": self.log[-30:],
            "error": self.error,
            "terminal_url": terminal_url if self.status == "ready" else None,
        }


class LabManager:
    PROJECT = "k8slab"

    def __init__(self, labs_dir: Path, runner: Runner = subprocess_runner,
                 terminal_port: int | None = None, poll_seconds: float = 3.0):
        self.labs_dir = labs_dir
        self.run = runner
        self.port = terminal_port or int(os.getenv("LAB_TERMINAL_PORT", "7681"))
        self.terminal_url = os.getenv("LAB_TERMINAL_URL", f"http://localhost:{self.port}")
        self.poll = poll_seconds
        self.state = LabState()
        self.lock = threading.Lock()
        self.docker_lock = threading.Lock()  # one docker compose up/down sequence at a time
        self.generation = 0  # bumps on every start/stop so stale threads stop quietly

    # ---------- docker compose helpers ----------

    def compose_file(self, env: str) -> Path:
        return self.labs_dir / "envs" / env / "compose.yaml"

    def compose(self, env: str | None, *args: str) -> list[str]:
        cmd = ["docker", "compose", "-p", self.PROJECT]
        if env:
            cmd += ["-f", str(self.compose_file(env))]
        return cmd + list(args)

    def bash(self, script: str, timeout: float = 60) -> tuple[int, str]:
        """Run a bash script inside the lab terminal container (kubectl is configured there)."""
        env = self.state.environment
        return self.run(self.compose(env, "exec", "-T", "toolbox", "bash", "-s"),
                        "set -o pipefail\n" + script, timeout)

    def _log(self, msg: str) -> None:
        self.state.log.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

    # ---------- lifecycle ----------

    def start(self, task: LabTask, nodes: int) -> dict:
        if not self.compose_file(task.environment).exists():
            raise ValueError(f"No compose file for environment '{task.environment}'")
        with self.lock:
            self.generation += 1
            gen = self.generation
            self.state = LabState(status="starting", task_id=task.id, environment=task.environment)
        threading.Thread(target=self._start, args=(gen, task, nodes), daemon=True).start()
        return self.status()

    def _start(self, gen: int, task: LabTask, nodes: int) -> None:
        with self.docker_lock:
            if gen == self.generation:
                self._start_locked(gen, task, nodes)

    def _start_locked(self, gen: int, task: LabTask, nodes: int) -> None:
        def alive() -> bool:
            return gen == self.generation

        def fail(msg: str) -> None:
            if alive():
                self.state.status, self.state.error = "error", msg
                self._log("ERROR: " + msg)

        env = task.environment
        self._log("Removing any previous lab…")
        self.run(self.compose(None, "down", "-v", "--remove-orphans"), None, 120)
        if not alive():
            return
        self._log(f"Starting cluster: {env} (first time: downloads images, ~1-2 min)…")
        rc, out = self.run(self.compose(env, "up", "-d", "--build", "--quiet-pull"), None, 600)
        if rc != 0:
            return fail(out[-800:] or "docker compose up failed")

        self._log(f"Waiting for {nodes} node(s) to be Ready…")
        deadline = time.time() + 240
        while alive():
            rc, out = self.bash("kubectl get nodes --no-headers 2>/dev/null | grep -cw Ready", 30)
            if rc == 0 and out.strip().isdigit() and int(out.strip()) >= nodes:
                break
            if time.time() > deadline:
                return fail("Nodes did not become Ready in 4 minutes. Is Docker running with enough memory?")
            time.sleep(self.poll)
        if not alive():
            return

        self._log("Waiting for cluster DNS and the default ServiceAccount…")
        rc, out = self.bash(
            "for i in $(seq 1 60); do kubectl get serviceaccount default >/dev/null 2>&1 && break; sleep 2; done\n"
            "kubectl -n kube-system rollout status deployment coredns --timeout=180s", 240)
        if rc != 0:
            return fail("Cluster add-ons did not start: " + out[-400:])

        if task.setup.strip() and alive():
            self._log("Preparing the task scenario…")
            rc, out = self.bash(task.setup, 300)
            if rc != 0:
                return fail("Task setup failed: " + out[-600:])

        if alive():
            self._log("Lab ready. Good luck!")
            self.state.status = "ready"
            self.state.started_at = time.time()

    def stop(self) -> dict:
        with self.lock:
            self.generation += 1
            env = self.state.environment
            self.state = LabState(status="stopping", environment=env)
        with self.docker_lock:
            self.run(self.compose(env, "down", "-v", "--remove-orphans"), None, 180)
        self.state = LabState()
        return self.status()

    def status(self) -> dict:
        return self.state.public(self.terminal_url)

    # ---------- grading ----------

    def check(self, task: LabTask) -> list[dict]:
        if self.state.status != "ready" or self.state.task_id != task.id:
            raise RuntimeError("This lab is not running. Start it first.")
        results = []
        for c in task.checks:
            rc, out = self.bash(c.run, 90)
            results.append({"name": c.name, "passed": rc == 0, "output": out[-300:] if rc else ""})
        return results
