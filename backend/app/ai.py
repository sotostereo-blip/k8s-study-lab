"""Optional AI feedback on spoken interview answers (Claude API).

The app works without it. It turns on when the Anthropic SDK finds credentials:
ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN). Set AI_FEEDBACK=0 to turn it off, and LLM_MODEL to
use another Claude model. Only the question, its key points and your answer are sent, and only
when you press "Get AI feedback".
"""
from __future__ import annotations

import os

from pydantic import BaseModel, Field

from .content import InterviewQuestion

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

    def feedback(self, q: InterviewQuestion, answer: str, seconds: int | None = None) -> dict:
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": self.prompt(q, answer, seconds)}],
            output_format=Feedback,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",   # if the model declines, the API retries on a fallback model
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("The AI did not give feedback for this answer. Try again with a different answer.")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise RuntimeError("The AI feedback was cut off. Try again.")
        fb: Feedback = response.parsed_output
        n = len(q.key_points)
        out = fb.model_dump()
        out["key_points"] = [k for k in out["key_points"] if 0 <= k["index"] < n]
        out["covered"] = sorted({k["index"] for k in out["key_points"] if k["covered"]})
        out["model"] = response.model
        return out
