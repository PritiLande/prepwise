"""
History endpoints — list and detail views for a user's saved analyses.

Both routes require a valid JWT (personal data — no anonymous access).
The raw token is passed to db_service so postgrest.auth() can satisfy RLS.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.core.supabase_client import get_supabase
from app.dependencies.auth import get_current_user
from app.schemas.history import AnalysisDetail, AnalysisSummary, HistoryResponse
from app.services.db_service import DBFetchError, DBNotFoundError, get_analysis_detail, get_user_analyses

router = APIRouter(tags=["history"])

# UUID v4 pattern — used to validate path parameters before hitting the DB.
# An invalid ID (e.g. "abc") would cause a PostgREST error; we catch it early.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@router.get("/analyses", response_model=HistoryResponse)
def get_history(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
    limit: int = Query(20, ge=1, le=100, description="Max results to return."),
    offset: int = Query(0, ge=0, description="Number of results to skip."),
):
    """
    Return the calling user's past analyses, newest first.
    Supports pagination via limit and offset query parameters.
    """
    user_id    = current_user["sub"]
    user_token = current_user["_token"]

    try:
        rows = get_user_analyses(
            supabase,
            user_id,
            user_token=user_token,
            limit=limit,
            offset=offset,
        )
    except DBFetchError:
        raise HTTPException(
            status_code=503,
            detail="Could not retrieve history right now. Please try again.",
        )

    summaries = [
        AnalysisSummary(
            id=row["id"],
            company_name=row["company_name"],
            match_score=row["match_score"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return HistoryResponse(analyses=summaries, total=len(summaries))


@router.get("/analyses/{analysis_id}", response_model=AnalysisDetail)
def get_history_detail(
    analysis_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """
    Return the full stored result for one analysis belonging to the
    calling user.

    404 is returned if:
      - The id is not a valid UUID format.
      - The row does not exist.
      - The row belongs to a different user.
    We never distinguish these cases so existence is not leaked.

    resume_text and job_description are never included in the response.
    """
    # Validate UUID format before touching the DB.
    # An invalid format returns 404 (not 422) — we don't want to reveal
    # that we have UUID-based primary keys.
    if not _UUID_RE.match(analysis_id):
        raise HTTPException(status_code=404, detail="Analysis not found.")

    user_id    = current_user["sub"]
    user_token = current_user["_token"]

    try:
        row = get_analysis_detail(
            supabase,
            analysis_id=analysis_id,
            user_id=user_id,
            user_token=user_token,
        )
    except DBNotFoundError:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    except DBFetchError:
        raise HTTPException(
            status_code=503,
            detail="Could not retrieve the analysis right now. Please try again.",
        )

    return AnalysisDetail(
        id=row["id"],
        company_name=row["company_name"],
        match_score=row["match_score"],
        created_at=row["created_at"],
        result_json=row["result_json"],
    )
