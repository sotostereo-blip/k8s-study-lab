"""Optional AI help (Claude API): feedback on interview answers and "Explain more" on questions.

The app works without it. It turns on when the Anthropic SDK finds credentials:
ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN). Set AI_FEEDBACK=0 to turn it off, and LLM_MODEL to
use another Claude model. Only the question (with its answer and explanation) and what you wrote
or chose are sent, and only when you press an AI button.
"""
from __future__ import annotations

import os

from pydantic import BaseModel, Field

from .content import InterviewQuestion, Question

DEFAULT_MODEL = "claude-opus-5-5"

SYSTEM = """You are a friendly interview coach for DevOps and Cloud Engineer jobs.
The candidate is a Spanish speaker practising job interviews in English. They answered aloud
(speech to text) or typed. Give feedback that helps them do better in the next interview.

Rules:
- Write in simple, clear English (CEFR B1): short sentences, common words. Technical terms are fine.
- Judge the technical content against the key points, but accept other correct ideas too.
- Speech-to-text makes mistakes (missing punctuation, wrong similar-sounding words). Do not
  correct those; correct only real grammar or word-choice mistakes a listener would notice.
- Be honest and specific. Do not invent facts about the candidate.
- "better_answer" keeps the candidate's own ideas and style, fixes the mistakes, adds what is
  missing, and sounds natural when spoken (about 90 to 160 words).
"""


class KeyPoint(BaseModel):
    index: int = Field(description="0-based index of the key point in the list given")
    covered: bool
    note: str = Field(description="One short sentence: what the answer said about it, or what was missing")


class EnglishFix(BaseModel):
    said: str = Field(description="The words the candidate used")
    better: str = Field(description="A more natural or correct way to say it")
    why: str = Field(description="Short reason, in simple English")


class Feedback(BaseModel):
    summary: str = Field(description="2 or 3 sentences: overall impression, as an interviewer would feel it")
    key_points: list[KeyPoint]
    strengths: list[str] = Field(description="1 to 3 things that were good")
    improve: list[str] = Field(description="1 to 3 concrete things to do better next time")
    english: list[EnglishFix] = Field(description="Up to 5 English corrections; empty if none")
    better_answer: str


EXPLAIN_SYSTEM = """You are a patient tutor for IT certification exams (Kubernetes, Linux, Docker,
Terraform, AWS, CI/CD, observability). The student is a Spanish speaker who studies in English.
They just answered a practice question and want to understand the topic better than the short
written explanation allows.

Rules:
- Write in simple, clear English (CEFR B1): short sentences, common words. Keep technical terms,
  but explain each new one the first time.
- Be technically exact and current. Base everything on the official documentation the question
  links to. If you are not sure about a detail, leave it out.
- Teach the idea behind the question, not only this question: the student will see other
  questions about the same topic.
- "example" is something concrete: a short command, a small YAML/HCL snippet, or a real situation.
  Use Markdown code fences for code.
- If the student asks something, answer it in "answer_to_student"; otherwise leave it empty.
- Never invent exam questions or claim to know the real exam's questions.
"""


class Explanation(BaseModel):
    idea: str = Field(description="The main idea behind the question, in 3 to 6 short sentences")
    why_right: str = Field(description="Why the correct answer is correct, 1 to 3 sentences")
    your_choice: str = Field(description="If the student chose a wrong option: why it is tempting and why "
                                         "it is wrong, 1 to 3 sentences. Empty if they were right")
    example: str = Field(description="A concrete example (command, snippet or situation), Markdown")
    remember: str = Field(description="One short sentence to remember for the exam")
    check_question: str = Field(description="A new short question to check understanding (not multiple choice)")
    check_answer: str = Field(description="The answer to check_question, 1 or 2 sentences")
    answer_to_student: str = Field(description="Answer to the student's own question; empty if none")


class Coach:
    """Calls the Claude API. `client` can be injected (tests use a fake)."""

    def __init__(self, client=None, model: str | None = None):
        self.model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self._client = client
        self.enabled = client is not None or self._configured()
        self.error: str | None = None

    @staticmethod
    def _configured() -> bool:
        if os.getenv("AI_FEEDBACK", "1") == "0":
            return False
        if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
            return False
        try:
            import anthropic  # noqa: F401  (optional dependency)
        except ImportError:
            return False
        return True

    @property
    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def prompt(self, q: InterviewQuestion, answer: str, seconds: int | None) -> str:
        points = "\n".join(f"{i}. {p}" for i, p in enumerate(q.key_points))
        timing = f"{seconds} seconds (target about {q.minutes:g} minutes)" if seconds else "not measured"
        return (f"Interview question ({q.level}, {q.type}):\n{q.question}\n\n"
                f"Key points a strong answer covers:\n{points}\n\n"
                f"Reference answer (for you, do not copy it):\n{q.model_answer}\n\n"
                f"Speaking time: {timing}\n\n"
                f"<candidate_answer>\n{answer.strip()}\n</candidate_answer>\n\n"
                "Give your feedback.")

    def _parse(self, system: str, user: str, schema: type[BaseModel]):
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",   # if the model declines, the API retries on a fallback model
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("The AI did not answer this request. Try again with different words.")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise RuntimeError("The AI answer was cut off. Try again.")
        return response.parsed_output, response.model

    def feedback(self, q: InterviewQuestion, answer: str, seconds: int | None = None) -> dict:
        fb, model = self._parse(SYSTEM, self.prompt(q, answer, seconds), Feedback)
        n = len(q.key_points)
        out = fb.model_dump()
        out["key_points"] = [k for k in out["key_points"] if 0 <= k["index"] < n]
        out["covered"] = sorted({k["index"] for k in out["key_points"] if k["covered"]})
        out["model"] = model
        return out

    @staticmethod
    def question_text(q: Question, exam_name: str) -> str:
        opts = "\n".join(f"{o.id.upper()}. {o.text}" + (" (correct)" if o.id in q.answer else "")
                         + (f"\n   Why not: {o.why}" if o.why and o.id not in q.answer else "")
                         for o in q.options)
        return (f"Exam: {exam_name}\nQuestion ({'one answer' if q.type == 'single' else 'several answers'}):\n"
                f"{q.question}\n\nOptions:\n{opts}\n\nWritten explanation:\n{q.explanation}\n\n"
                f"Official docs:\n" + "\n".join(q.docs))

    def explain(self, q: Question, exam_name: str, selected: list[str], ask: str | None = None) -> dict:
        right = sorted(selected) == sorted(q.answer)
        chose = ", ".join(s.upper() for s in selected) or "nothing"
        user = (self.question_text(q, exam_name) + f"\n\nThe student chose: {chose} ("
                + ("correct" if right else "wrong") + ")."
                + (f"\n\n<student_question>\n{ask.strip()}\n</student_question>" if ask and ask.strip() else "")
                + "\n\nExplain the topic.")
        ex, model = self._parse(EXPLAIN_SYSTEM, user, Explanation)
        return ex.model_dump() | {"model": model, "correct": right}
