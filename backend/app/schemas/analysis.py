"""
Pydantic models for the LLM analysis result.

WHY a separate file?
  The schema is the CONTRACT between the LLM output and the rest of the app.
  Keeping it here means the route, the service, and the tests all import from
  one place — change the shape once and every layer sees the update instantly.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SkillGap(BaseModel):
    """A skill the candidate is missing, plus one concrete tip to close the gap."""

    skill: str = Field(description="Name of the missing skill.")
    tip: str = Field(description="One actionable sentence on how to learn or demonstrate it.")


class InterviewQuestion(BaseModel):
    """A single interview question with metadata and a resume-grounded answer outline."""

    question: str = Field(description="The interview question text.")
    category: Literal["technical", "behavioral", "project"] = Field(
        description="Type of question."
    )
    answer_outline: str = Field(
        description=(
            "Honest outline drawn only from facts in the resume. "
            "Must be at least two sentences (minimum 80 characters)."
        )
    )

    @field_validator("answer_outline")
    @classmethod
    def answer_outline_must_be_substantive(cls, v: str) -> str:
        """
        Reject empty or very short answer outlines.

        WHY 80 characters?
          A useful outline must have at least two real sentences. A single
          short sentence like "I have experience." is 24 chars and useless.
          80 chars is roughly "This project used FastAPI. I built the auth
          layer with JWT tokens." — the minimum useful content.
          The LLM is instructed to write at least two sentences; this validator
          enforces that contract so the retry loop catches lazy responses.
        """
        stripped = v.strip()
        if len(stripped) < 80:
            raise ValueError(
                f"answer_outline is too short ({len(stripped)} chars). "
                f"Must be at least 80 characters (roughly two sentences). "
                f"Gap questions must admit the gap and bridge to resume experience. "
                f"Matched-skill questions must name the specific project and detail."
            )
        return stripped


class AnalysisResult(BaseModel):
    """
    The complete analysis returned by the LLM and validated by Pydantic.

    Pydantic will raise a ValidationError if the LLM returns the wrong types,
    a score outside 0-100, fewer than 10 questions, or a too-short
    answer_outline — we catch that in the service and retry.
    """

    match_score: int = Field(
        ge=0, le=100,
        description="How well the resume matches the job description (0-100)."
    )
    matched_skills: list[str] = Field(
        description="Skills present in both the resume and the job description."
    )
    skill_gaps: list[SkillGap] = Field(
        description="Skills required by the JD that are absent from the resume."
    )
    resume_wording_tips: list[str] = Field(
        default_factory=list,
        description=(
            "Keywords the candidate should add to their resume because the "
            "activity is clearly present but the standard term is missing. "
            "Empty list if no tips apply."
        ),
    )
    questions: list[InterviewQuestion] = Field(
        description="Exactly 10 tailored interview questions."
    )

    @field_validator("questions")
    @classmethod
    def must_have_ten_questions(cls, v: list) -> list:
        # We enforce exactly 10 here so the frontend can always render
        # a fixed grid — no partial results.
        if len(v) != 10:
            raise ValueError(
                f"Expected exactly 10 questions, got {len(v)}."
            )
        return v
