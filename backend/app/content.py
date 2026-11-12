"""Load and validate study content from YAML files in content/."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Option(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-f]$")
    text: str
    why: str | None = None  # why this option is wrong (or right); shown after answering


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9]+-[a-z]+-\d{3}$")
    domain: str = ""
    difficulty: int = Field(ge=1, le=3)
    type: Literal["single", "multiple"]
    question: str
    options: list[Option] = Field(min_length=2, max_length=6)
    answer: list[str] = Field(min_length=1)
    explanation: str
    docs: list[str] = Field(min_length=1)
    glossary: list[str] = []

    @model_validator(mode="after")
    def check_answer(self) -> "Question":
        ids = [o.id for o in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError(f"{self.id}: duplicate option ids")
        missing = set(self.answer) - set(ids)
        if missing:
            raise ValueError(f"{self.id}: answer {missing} not in options")
        if self.type == "single" and len(self.answer) != 1:
            raise ValueError(f"{self.id}: single-choice needs exactly one answer")
        if self.type == "multiple" and len(self.answer) < 2:
            raise ValueError(f"{self.id}: multiple-choice needs 2+ answers")
        missing_why = [o.id for o in self.options if o.id not in self.answer and not (o.why or "").strip()]
        if missing_why:
            raise ValueError(f"{self.id}: wrong options {missing_why} need a 'why' (why the option is wrong)")
        return self

    def public(self) -> dict:
        """Question without answer/explanation, safe to send before answering."""
        return self.model_dump(include={"id", "domain", "difficulty", "type", "question", "glossary"}) | {
            "options": [{"id": o.id, "text": o.text} for o in self.options],  # 'why' would leak the answer
            "select": len(self.answer),
        }


class Domain(BaseModel):
    id: str
    name: str
    weight: int
    notes: str | None = None


class Exam(BaseModel):
    id: str
    name: str
    format: str
    exam_minutes: int
    exam_questions: int
    passing_score: int
    domains: list[Domain]


class Term(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    term: str
    match: list[str] = []
    definition: str
    es: str


class Check(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    run: str  # bash, run in the lab terminal container; exit code 0 = pass
    # A guard is already true before the task (e.g. "do not remove the taint"). It gives no
    # points in a mock exam, and breaking it makes the task worth 0.
    guard: bool = False


class LabTask(BaseModel):
    """A hands-on task solved in a real cluster (content/<exam>/tasks/<id>.yaml)."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9]+-[a-z]+-\d{3}$")
    title: str
    domain: str
    difficulty: int = Field(ge=1, le=3)
    minutes: int = Field(ge=1, le=60)
    environment: str
    task: str
    setup: str = ""
    checks: list[Check] = Field(min_length=1)
    solution: str
    docs: list[str] = Field(min_length=1)
    # Mock exams run many tasks in ONE cluster. A task that changes the whole cluster
    # (for example draining a node) sets mock_exam: false; tasks that cannot share a
    # cluster (same object names, taints on every node) list each other in conflicts_with.
    mock_exam: bool = True
    conflicts_with: list[str] = []

    def public(self) -> dict:
        """Everything except the checker scripts (solution is shown on demand)."""
        return self.model_dump(exclude={"checks", "setup", "solution", "mock_exam", "conflicts_with"}) | {
            "checks": [c.name for c in self.checks]
        }


class LabEnvironment(BaseModel):
    name: str
    nodes: int = Field(ge=1)


class LabTrack(BaseModel):
    """Lab metadata for one exam (content/<exam>/labs.yaml)."""
    id: str
    name: str
    exam_minutes: int
    passing_score: int
    domains: list[Domain]
    environments: dict[str, LabEnvironment]


class Library(BaseModel):
    exams: dict[str, Exam]
    questions: dict[str, Question]
    glossary: dict[str, Term]
    tracks: dict[str, LabTrack] = {}
    tasks: dict[str, LabTask] = {}

    def questions_for(self, exam_id: str, domain: str | None = None) -> list[Question]:
        prefix = f"{exam_id}-"
        return [
            q for q in self.questions.values()
            if q.id.startswith(prefix) and (domain is None or q.domain == domain)
        ]


def _read(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_library(content_dir: Path) -> Library:
    """Load everything and raise ValueError with all problems found."""
    errors: list[str] = []
    glossary: dict[str, Term] = {}
    gpath = content_dir / "glossary.yaml"
    if gpath.exists():
        for raw in _read(gpath).get("terms", []):
            t = Term(**raw)
            if t.id in glossary:
                errors.append(f"glossary: duplicate term id {t.id}")
            glossary[t.id] = t

    exams: dict[str, Exam] = {}
    questions: dict[str, Question] = {}
    for exam_file in sorted(content_dir.glob("*/exam.yaml")):
        exam = Exam(**_read(exam_file))
        exams[exam.id] = exam
        domain_ids = {d.id for d in exam.domains}
        for qfile in sorted(exam_file.parent.glob("*.yaml")):
            if qfile.name == "exam.yaml":
                continue
            data = _read(qfile)
            domain = data.get("domain")
            if domain not in domain_ids:
                errors.append(f"{qfile}: unknown domain '{domain}'")
                continue
            for raw in data.get("questions", []):
                try:
                    q = Question(**raw, **({} if "domain" in raw else {"domain": domain}))
                except Exception as e:  # pydantic ValidationError
                    errors.append(f"{qfile}: {raw.get('id', '?')}: {e}")
                    continue
                if not q.id.startswith(f"{exam.id}-"):
                    errors.append(f"{qfile}: {q.id} must start with '{exam.id}-'")
                if q.id in questions:
                    errors.append(f"{qfile}: duplicate question id {q.id}")
                for g in q.glossary:
                    if g not in glossary:
                        errors.append(f"{qfile}: {q.id} references unknown glossary term '{g}'")
                questions[q.id] = q

    tracks: dict[str, LabTrack] = {}
    tasks: dict[str, LabTask] = {}
    for track_file in sorted(content_dir.glob("*/labs.yaml")):
        try:
            track = LabTrack(**_read(track_file))
        except Exception as e:
            errors.append(f"{track_file}: {e}")
            continue
        tracks[track.id] = track
        domain_ids = {d.id for d in track.domains}
        for tfile in sorted((track_file.parent / "tasks").glob("*.yaml")):
            raw = _read(tfile)
            try:
                t = LabTask(**raw)
            except Exception as e:
                errors.append(f"{tfile}: {raw.get('id', '?')}: {e}")
                continue
            if tfile.stem != t.id:
                errors.append(f"{tfile}: file name must be {t.id}.yaml")
            if not t.id.startswith(f"{track.id}-"):
                errors.append(f"{tfile}: {t.id} must start with '{track.id}-'")
            if t.domain not in domain_ids:
                errors.append(f"{tfile}: unknown domain '{t.domain}'")
            if all(c.guard for c in t.checks):
                errors.append(f"{tfile}: needs at least one check that is not a guard")
            if t.environment not in track.environments:
                errors.append(f"{tfile}: unknown environment '{t.environment}'")
            if t.id in tasks:
                errors.append(f"{tfile}: duplicate task id {t.id}")
            tasks[t.id] = t

    for t in tasks.values():
        for other in t.conflicts_with:
            if other not in tasks:
                errors.append(f"{t.id}: conflicts_with unknown task '{other}'")

    if errors:
        raise ValueError("\n".join(errors))
    return Library(exams=exams, questions=questions, glossary=glossary, tracks=tracks, tasks=tasks)
