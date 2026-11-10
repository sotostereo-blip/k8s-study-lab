"""Load and validate study content from YAML files in content/."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class Option(BaseModel):
    id: str = Field(pattern=r"^[a-f]$")
    text: str


class Question(BaseModel):
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
        return self

    def public(self) -> dict:
        """Question without answer/explanation, safe to send before answering."""
        return self.model_dump(include={"id", "domain", "difficulty", "type", "question", "options", "glossary"}) | {
            "select": len(self.answer)
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
    id: str
    term: str
    match: list[str] = []
    definition: str
    es: str


class Library(BaseModel):
    exams: dict[str, Exam]
    questions: dict[str, Question]
    glossary: dict[str, Term]

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

    if errors:
        raise ValueError("\n".join(errors))
    return Library(exams=exams, questions=questions, glossary=glossary)
