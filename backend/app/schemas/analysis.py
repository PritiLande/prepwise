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
        description="Short bullet outline drawn only from facts in the resume."
    )


class AnalysisResult(BaseModel):
    """
    The complete analysis returned by the LLM and validated by Pydantic.

    Pydantic will raise a ValidationError if the LLM returns the wrong types,
    a score outside 0-100, or fewer than 10 questions — we catch that in the
    service and retry.
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
