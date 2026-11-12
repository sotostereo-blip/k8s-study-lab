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
    facts_note: str | None = None   # e.g. which exam facts are not published officially


class Term(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    term: str
    match: list[str] = []
    definition: str
    es: str
    # Certification ids where the term is highlighted automatically (labs, interviews). Empty = all.
    # For common words with a specific meaning in one area ("workflow", "bucket", "Role").
    certs: list[str] = []


class Word(BaseModel):
    """General (non-technical) English vocabulary found in the content (content/vocabulary.yaml)."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    word: str
    match: list[str] = Field(min_length=1)
    definition: str
    example: str
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
    # Runnable bash used only by scripts/verify_labs.py when `solution` has manual steps
    # (for example "edit the file"). Never shown to the learner.
    auto_solution: str = ""
    # Mock exams run many tasks in ONE cluster. A task that changes the whole cluster
    # (for example draining a node) sets mock_exam: false; tasks that cannot share a
    # cluster (same object names, taints on every node) list each other in conflicts_with.
    mock_exam: bool = True
    conflicts_with: list[str] = []

    def public(self) -> dict:
        """Everything except the checker scripts (solution is shown on demand)."""
        return self.model_dump(exclude={"checks", "setup", "solution", "auto_solution", "mock_exam", "conflicts_with"}) | {
            "checks": [c.name for c in self.checks]
        }


class LabEnvironment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    nodes: int = Field(ge=0)   # Kubernetes nodes; 0 = no cluster (its toolbox must ship a `lab-ready` script)
    label: str | None = None   # short label on the lab cards (default: "1 node", "2 nodes")
    tools: str | None = None   # terminal bar text, e.g. "kubectl is ready (alias `k`)"
    # bash run in the toolbox until it exits 0 before the task setup starts (after the nodes
    # are Ready, for Kubernetes). Default: `lab-ready` when nodes is 0, nothing otherwise.
    ready: str | None = None
    ready_timeout: int = Field(default=300, ge=30, le=1200)

    @property
    def ready_command(self) -> str | None:
        return self.ready or ("lab-ready" if self.nodes == 0 else None)


class LabTrack(BaseModel):
    """Lab metadata for one exam (content/<exam>/labs.yaml)."""
    id: str
    name: str
    exam_minutes: int
    passing_score: int
    domains: list[Domain]
    environments: dict[str, LabEnvironment]
    mock: bool = True                       # offer a multi-task mock exam for this track
    mock_environment: str | None = None     # environment that runs all mock exam tasks together
    intro: str | None = None                # "Choosing a lab starts <intro> with a terminal in your browser"


class OfficialExam(BaseModel):
    """Facts about the real exam, from the official page (content/certifications.yaml `official`)."""
    model_config = ConfigDict(extra="forbid")
    provider: str                       # who runs the exam
    format: str                         # multiple choice, performance-based…
    questions: str                      # "65 questions"; say when the number is not official
    minutes: int = Field(gt=0)
    passing: str = ""                   # passing score, and whether it is official
    cost: str                           # price of the exam alone, in USD
    includes: list[str] = []            # free retake, simulator sessions…
    prerequisites: str = "None"         # certification you must hold first
    valid: str                          # how long the certification lasts
    renewal: str = ""                   # how to keep it
    notes: list[str] = []
    url: str = Field(pattern=r"^https://")
    checked: str = Field(pattern=r"^\d{4}-\d{2}$")   # month the facts were checked


class Certification(BaseModel):
    """What the app offers for one certification (content/certifications.yaml)."""
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    short: str
    area: str
    exam: str | None = None    # multiple-choice exam id (content/<id>/exam.yaml)
    track: str | None = None   # hands-on lab track id (content/<id>/labs.yaml)
    interview: bool = False    # interview practice (content/interviews/)
    description: str = ""
    official: OfficialExam | None = None   # the real exam: questions, time, cost, validity


class InterviewCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z]+$")
    name: str
    description: str = ""


class InterviewQuestion(BaseModel):
    """A job-interview question answered aloud (content/interviews/<category>.yaml)."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^iv-[a-z]+-\d{3}$")
    category: str = ""
    level: Literal["junior", "mid", "senior"]
    type: Literal["technical", "behavioral", "scenario", "design"]
    question: str
    key_points: list[str] = Field(min_length=2, max_length=8)   # what a good answer covers (self check)
    model_answer: str                                           # a strong spoken answer, 60-200 words
    follow_ups: list[str] = []                                  # what the interviewer may ask next
    tips: str = ""                                              # how to structure the answer
    glossary: list[str] = []
    docs: list[str] = []
    minutes: float = Field(default=2, ge=0.5, le=10)            # target speaking time

    def public(self) -> dict:
        """Without the key points and model answer (shown after answering)."""
        return self.model_dump(include={"id", "category", "level", "type", "question", "tips", "glossary", "minutes"})


class Phrase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    es: str
    note: str = ""


class PhraseGroup(BaseModel):
    """Useful spoken English for interviews (content/interviews/phrases.yaml)."""
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    when: str
    phrases: list[Phrase] = Field(min_length=1)


class Library(BaseModel):
    exams: dict[str, Exam]
    questions: dict[str, Question]
    glossary: dict[str, Term]
    tracks: dict[str, LabTrack] = {}
    tasks: dict[str, LabTask] = {}
    vocabulary: dict[str, Word] = {}
    certifications: list[Certification] = []
    interview_categories: dict[str, InterviewCategory] = {}
    interview_questions: dict[str, InterviewQuestion] = {}
    phrase_groups: list[PhraseGroup] = []
    errors: list[str] = []

    def tasks_for(self, track_id: str) -> list[LabTask]:
        return [t for t in self.tasks.values() if t.id.startswith(f"{track_id}-")]

    def questions_for(self, exam_id: str, domain: str | None = None) -> list[Question]:
        prefix = f"{exam_id}-"
        return [
            q for q in self.questions.values()
            if q.id.startswith(prefix) and (domain is None or q.domain == domain)
        ]


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_library(content_dir: Path, strict: bool = True) -> Library:
    """Load everything and raise ValueError with all problems found.

    strict=False skips broken files instead of raising (used by scripts/verify_labs.py
    while other content is being edited); the problems are in Library.errors."""
    errors: list[str] = []

    def _read(path: Path) -> dict:   # a YAML syntax error becomes a reported problem, not a crash
        try:
            return _read_yaml(path)
        except yaml.YAMLError as e:
            errors.append(f"{path}: invalid YAML: {e}")
            return {}
    glossary: dict[str, Term] = {}
    # glossary.yaml plus one file per area in glossary.d/ (terraform.yaml, security.yaml, ...)
    gfiles = [content_dir / "glossary.yaml", *sorted((content_dir / "glossary.d").glob("*.yaml"))]
    for gpath in gfiles:
        if not gpath.exists():
            continue
        for raw in _read(gpath).get("terms", []):
            try:
                t = Term(**raw)
            except Exception as e:
                errors.append(f"{gpath.name}: {raw.get('id', '?')}: {e}")
                continue
            if t.id in glossary:
                errors.append(f"{gpath.name}: duplicate term id {t.id}")
            glossary[t.id] = t

    term_form_owner: dict[str, str] = {}
    for t in glossary.values():   # one highlighted form must point to one term only
        for m in t.match:
            if m.lower() in term_form_owner and term_form_owner[m.lower()] != t.id:
                errors.append(f"glossary: '{m}' is a match form of both {term_form_owner[m.lower()]} and {t.id}")
            term_form_owner[m.lower()] = t.id

    vocabulary: dict[str, Word] = {}
    term_forms = {m.lower() for t in glossary.values() for m in t.match}
    seen_forms: dict[str, str] = {}
    # vocabulary.yaml plus one file per area in vocabulary.d/
    for vpath in [content_dir / "vocabulary.yaml", *sorted((content_dir / "vocabulary.d").glob("*.yaml"))]:
        if not vpath.exists():
            continue
        for raw in _read(vpath).get("words", []):
            try:
                w = Word(**raw)
            except Exception as e:
                errors.append(f"{vpath.name}: {raw.get('id', '?')}: {e}")
                continue
            if w.id in vocabulary:
                errors.append(f"vocabulary: duplicate id {w.id}")
            for m in w.match:
                key = m.lower()
                if key in term_forms:
                    errors.append(f"vocabulary: {w.id}: '{m}' is already a glossary term")
                if key in seen_forms:
                    errors.append(f"vocabulary: {w.id}: '{m}' is also used by {seen_forms[key]}")
                seen_forms[key] = w.id
            vocabulary[w.id] = w

    exams: dict[str, Exam] = {}
    questions: dict[str, Question] = {}
    for exam_file in sorted(content_dir.glob("*/exam.yaml")):
        try:
            exam = Exam(**_read(exam_file))
        except Exception as e:
            errors.append(f"{exam_file}: {e}")
            continue
        exams[exam.id] = exam
        domain_ids = {d.id for d in exam.domains}
        for qfile in sorted(exam_file.parent.glob("*.yaml")):
            if qfile.name in ("exam.yaml", "labs.yaml"):
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
        if track.mock and track.mock_environment not in track.environments:
            errors.append(f"{track_file}: mock_environment must be one of the track environments")
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
            elif track.mock and t.mock_exam and track.environments[t.environment].nodes > \
                    track.environments[track.mock_environment or t.environment].nodes:
                errors.append(f"{tfile}: needs more nodes than the mock exam environment")
            if t.id in tasks:
                errors.append(f"{tfile}: duplicate task id {t.id}")
            tasks[t.id] = t

    interview_categories: dict[str, InterviewCategory] = {}
    interview_questions: dict[str, InterviewQuestion] = {}
    phrase_groups: list[PhraseGroup] = []
    idir = content_dir / "interviews"
    if (idir / "interviews.yaml").exists():
        for raw in _read(idir / "interviews.yaml").get("categories", []):
            try:
                c = InterviewCategory(**raw)
            except Exception as e:
                errors.append(f"interviews.yaml: {raw.get('id', '?')}: {e}")
                continue
            interview_categories[c.id] = c
        for qfile in sorted(idir.glob("*.yaml")):
            if qfile.name in ("interviews.yaml", "phrases.yaml"):
                continue
            data = _read(qfile)
            cat = data.get("category")
            if cat not in interview_categories:
                errors.append(f"{qfile}: unknown interview category '{cat}'")
                continue
            for raw in data.get("questions", []):
                try:
                    q = InterviewQuestion(**raw, **({} if "category" in raw else {"category": cat}))
                except Exception as e:
                    errors.append(f"{qfile}: {raw.get('id', '?')}: {e}")
                    continue
                if q.id in interview_questions:
                    errors.append(f"{qfile}: duplicate interview question id {q.id}")
                for g in q.glossary:
                    if g not in glossary:
                        errors.append(f"{qfile}: {q.id} references unknown glossary term '{g}'")
                interview_questions[q.id] = q
        if (idir / "phrases.yaml").exists():
            for raw in _read(idir / "phrases.yaml").get("groups", []):
                try:
                    phrase_groups.append(PhraseGroup(**raw))
                except Exception as e:
                    errors.append(f"phrases.yaml: {raw.get('id', '?')}: {e}")

    certifications: list[Certification] = []
    cpath = content_dir / "certifications.yaml"
    if cpath.exists():
        for raw in _read(cpath).get("certifications", []):
            try:
                c = Certification(**raw)
            except Exception as e:
                errors.append(f"certifications.yaml: {raw.get('id', '?')}: {e}")
                continue
            if c.exam and c.exam not in exams:
                errors.append(f"certifications.yaml: {c.id}: unknown exam '{c.exam}'")
            if c.track and c.track not in tracks:
                errors.append(f"certifications.yaml: {c.id}: unknown lab track '{c.track}'")
            if c.interview and not interview_questions:
                errors.append(f"certifications.yaml: {c.id}: no interview questions in content/interviews/")
            certifications.append(c)

    cert_ids = {c.id for c in certifications}
    for t in glossary.values():
        for c in t.certs:
            if cert_ids and c not in cert_ids:
                errors.append(f"glossary: {t.id}: unknown certification '{c}' in certs")

    for t in tasks.values():
        for other in t.conflicts_with:
            if other not in tasks:
                errors.append(f"{t.id}: conflicts_with unknown task '{other}'")

    if errors and strict:
        raise ValueError("\n".join(errors))
    return Library(errors=errors, exams=exams, questions=questions, glossary=glossary, tracks=tracks, tasks=tasks,
                   vocabulary=vocabulary, certifications=certifications,
                   interview_categories=interview_categories, interview_questions=interview_questions,
                   phrase_groups=phrase_groups)
