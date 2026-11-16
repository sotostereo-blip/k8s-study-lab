"""Run hands-on labs: a small k3s cluster + a browser terminal, started with docker compose.

Only one lab runs at a time (like the real exam, you work in one environment).
Starting a lab tears down the previous one, so every lab starts from a clean cluster.
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml

from .content import Check

# runner(cmd, stdin, timeout) -> (exit_code, combined output)
Runner = Callable[[list[str], str | None, float], tuple[int, str]]


# Runs lab-teardown in every running container of the lab project that has it.
TEARDOWN = ("for c in $(docker ps -q --filter label=com.docker.compose.project={project}); do "
            "docker exec \"$c\" sh -c 'command -v lab-teardown >/dev/null 2>&1 && lab-teardown || true' "
            ">/dev/null 2>&1; done; true")


def _services(labs_dir: Path, env: str) -> dict:
    f = labs_dir / "envs" / env / "compose.yaml"
    return ((yaml.safe_load(f.read_text()) or {}).get("services") or {}) if f.exists() else {}


def _context(labs_dir: Path, env: str, svc: dict) -> Path | None:
    b = svc.get("build")
    ctx = b if isinstance(b, str) else (b or {}).get("context")
    return (labs_dir / "envs" / env / ctx).resolve() if ctx else None


def env_builds(labs_dir: Path, env: str) -> list[tuple[str, str, Path]]:
    """(service, image, build context) for every service of the environment built from labs/."""
    return [(name, svc["image"], _context(labs_dir, env, svc))
            for name, svc in _services(labs_dir, env).items() if svc.get("image") and svc.get("build")]


def lab_builds(labs_dir: Path) -> dict[str, tuple[str, str, Path]]:
    """image -> (environment, service, build context), over every lab environment."""
    built = {}
    for f in sorted((labs_dir / "envs").glob("*/compose.yaml")):
        for service, image, ctx in env_builds(labs_dir, f.parent.name):
            built.setdefault(image, (f.parent.name, service, ctx))
    return built


def bases_of(context: Path) -> list[str]:
    """Lab images (k8s-study-lab/...) that a Dockerfile is built FROM."""
    f = context / "Dockerfile"
    return re.findall(r"^FROM\s+(k8s-study-lab/\S+)", f.read_text(), re.M) if f.exists() else []


def base_images(labs_dir: Path, env: str) -> list[tuple[str, str, str]]:
    """Lab images built FROM another lab image (e.g. the Argo CD toolbox is FROM
    k8s-study-lab/toolbox:3). `docker compose up --build` cannot build that base first, so the
    caller must. Returns (image, environment, service) for each base image the environment needs:
    build it with `docker compose -f envs/<environment>/compose.yaml build <service>` (BuildKit)."""
    built = lab_builds(labs_dir)
    need = []
    for _, _, ctx in env_builds(labs_dir, env):
        for img in bases_of(ctx):
            if img in built and (img, *built[img][:2]) not in need:
                need.append((img, *built[img][:2]))
    return need


def prebuilt_name(registry: str, image: str) -> str:
    """k8s-study-lab/toolbox:3 -> <registry>/toolbox:3 (the name CI publishes it under)."""
    return f"{registry.rstrip('/')}/{image.split('/', 1)[1]}"


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
        # where CI publishes ready-made lab images; empty = always build them here
        self.registry = os.getenv("LAB_IMAGE_REGISTRY", "").strip()
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

    def teardown(self) -> None:
        """Before removing the lab: let each container release kernel objects it created (loop
        devices, LVM volumes, swap), which `docker compose down` would leave on the Docker host.
        Images that need it ship a `lab-teardown` script; the others are skipped."""
        self.run(["sh", "-c", TEARDOWN.format(project=self.PROJECT)], None, 120)

    def pull_prebuilt(self, env: str, gen: int) -> list[str]:
        """Download the ready-made images of this environment from LAB_IMAGE_REGISTRY and tag them
        with their local names. Returns the services that still need a local build: those whose
        image could not be downloaded and is not already on this machine (offline, private registry)."""
        to_build, seen = [], set()
        for service, image, _ in env_builds(self.labs_dir, env):
            if image in seen:      # several services can share one image
                continue
            seen.add(image)
            remote = prebuilt_name(self.registry, image)
            self._log(f"Downloading the ready-made image {remote}…", gen)
            rc, _ = self.run(["docker", "pull", "-q", remote], None, 1800)
            if rc == 0:
                self.run(["docker", "tag", remote, image], None, 30)
            elif self.run(["docker", "image", "inspect", image], None, 30)[0] != 0:
                to_build.append(service)
        return to_build

    def _log(self, msg: str, gen: int | None = None) -> None:
        if gen is None or gen == self.generation:   # a stale thread must not write into a newer lab's log
            self.state.log.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

    # ---------- lifecycle ----------

    def start(self, lab_id: str, env: str, nodes: int, setup: str = "", setup_timeout: float = 300,
              ready: str | None = None, ready_timeout: float = 300) -> dict:
        """Start a clean cluster for `lab_id` (a task id, or "mock-<session>" for a mock exam)."""
        if not self.compose_file(env).exists():
            raise ValueError(f"No compose file for environment '{env}'")
        with self.lock:
            self.generation += 1
            gen = self.generation
            self.state = LabState(status="starting", task_id=lab_id, environment=env)
        if ready is None and nodes == 0:
            ready = "lab-ready"
        threading.Thread(target=self._start, args=(gen, env, nodes, setup, setup_timeout, ready, ready_timeout),
                         daemon=True).start()
        return self.status()

    def _start(self, gen: int, env: str, nodes: int, setup: str, setup_timeout: float,
               ready: str | None, ready_timeout: float) -> None:
        with self.docker_lock:
            if gen == self.generation:
                self._start_locked(gen, env, nodes, setup, setup_timeout, ready, ready_timeout)

    def _start_locked(self, gen: int, env: str, nodes: int, setup: str, setup_timeout: float,
                      ready: str | None, ready_timeout: float) -> None:
        def alive() -> bool:
            return gen == self.generation

        def fail(msg: str) -> None:
            if alive():
                self.state.status, self.state.error = "error", msg
                self._log("ERROR: " + msg)

        self._log("Removing any previous lab…")
        self.teardown()
        self.run(self.compose(None, "down", "-v", "--remove-orphans"), None, 120)
        if not alive():
            return
        self._log(f"Starting the lab environment: {env} (first time: downloads images, a few minutes)…")
        if self.registry:
            to_build = self.pull_prebuilt(env, gen)
            if not alive():
                return
        else:
            to_build = None   # build every lab image here (`up --build`)
        if to_build is None or to_build:
            for image, base_env, service in base_images(self.labs_dir, env):
                if self.run(["docker", "image", "inspect", image], None, 30)[0] != 0:
                    self._log(f"Building the base image {image} (first time only)…", gen)
                    rc, out = self.run(self.compose(base_env, "build", service), None, 1200)
                    if rc != 0:
                        return fail(out[-800:] or f"could not build {image}")
        if to_build:
            self._log(f"Building {', '.join(to_build)} here (no ready-made image)…", gen)
            rc, out = self.run(self.compose(env, "build", *to_build), None, 1800)
            if rc != 0:
                return fail(out[-800:] or "docker compose build failed")
        up = ["up", "-d", "--quiet-pull"] + (["--build"] if to_build is None else [])
        rc, out = self.run(self.compose(env, *up), None, 600)
        if rc != 0:
            return fail(out[-800:] or "docker compose up failed")

        if nodes > 0:
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

        if ready and alive():   # e.g. LocalStack answers, Argo CD is running
            self._log("Waiting for the lab services…")
            deadline = time.time() + ready_timeout
            while alive():
                rc, out = self.bash(ready, 60)
                if rc == 0:
                    break
                if time.time() > deadline:
                    return fail(f"Lab services did not start in {ready_timeout / 60:.0f} minutes: " + out[-300:])
                time.sleep(self.poll)

        if setup.strip() and alive():
            self._log("Preparing the task scenario…")
            rc, out = self.bash(setup, setup_timeout)
            if rc != 0:
                return fail("Task setup failed: " + out[-600:])

        if alive():
            self._log("Lab ready. Good luck!")
            self.state.status = "ready"
            self.state.started_at = time.time()

    def stop(self) -> dict:
        with self.lock:
            self.generation += 1
            gen = self.generation
            env = self.state.environment
            self.state = LabState(status="stopping", environment=env)
        with self.docker_lock:
            if gen == self.generation:   # a newer start does its own "down" first
                self.teardown()
                self.run(self.compose(env, "down", "-v", "--remove-orphans"), None, 180)
        with self.lock:
            if gen == self.generation:   # never overwrite the state of a lab started after this stop
                self.state = LabState()
        return self.status()

    def status(self) -> dict:
        return self.state.public(self.terminal_url)

    # ---------- grading ----------

    def check(self, lab_id: str, checks: list[Check]) -> list[dict]:
        if self.state.status != "ready" or self.state.task_id != lab_id:
            raise RuntimeError("This lab is not running. Start it first.")
        results = []
        for c in checks:
            rc, out = self.bash(c.run, 90)
            results.append({"name": c.name, "passed": rc == 0, "output": out[-300:] if rc else ""})
        return results
