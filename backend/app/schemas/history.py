"""
Pydantic models for the history endpoints.

WHY not return the full AnalysisResult for the list?
  A history list with 20 full analyses (10 questions each) would be a huge
  payload. We return a lightweight summary per item. The frontend fetches
  the full result only when the user opens a specific analysis.
"""

from typing import Any

from pydantic import BaseModel, Field


class AnalysisSummary(BaseModel):
    """One row in the user's history list."""

    id: str = Field(description="UUID of this analysis record.")
    company_name: str = Field(description="Company name used in this analysis.")
    match_score: int = Field(description="Match score (0-100).")
    created_at: str = Field(description="ISO 8601 timestamp when this was saved.")


class HistoryResponse(BaseModel):
    """Response body for GET /analyses."""

    analyses: list[AnalysisSummary] = Field(
        description="List of analysis summaries, newest first."
    )
    total: int = Field(description="Number of items returned in this response.")


class AnalysisDetail(BaseModel):
    """
    Response body for GET /analyses/{analysis_id}.

    WHY result_json as Any (not AnalysisResult)?
      Old rows saved before recent prompt changes may have slightly
      different shapes (e.g. missing resume_wording_tips).  Returning
      the raw stored dict lets the frontend handle missing fields
      gracefully rather than having Pydantic reject old rows with
      a validation error.  The frontend always checks for missing fields.
    """

    id: str = Field(description="UUID of this analysis record.")
    company_name: str = Field(description="Company name used in this analysis.")
    match_score: int = Field(description="Match score (0-100).")
    created_at: str = Field(description="ISO 8601 timestamp when this was saved.")
    result_json: Any = Field(
        description="The full analysis result as stored (dict). "
                    "resume_text and job_description are never included."
    )
