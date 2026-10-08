"""
Database service — all Supabase interactions live here.

WHY a service file instead of putting queries in the route?
  The route handles HTTP (validate input, return response).
  This file handles the database (build the query, handle DB errors).
  Keeping them separate means:
    - We can test DB logic by passing a mocked Supabase client directly.
    - If we ever switch databases, only this file changes.

WHY pass user_token to every function?
  Supabase uses Row Level Security (RLS) to decide whether a query is
  allowed.  The RLS policy on analyses is:
    "INSERT: auth.uid() = user_id"
    "SELECT: auth.uid() = user_id"
  auth.uid() only returns the correct UUID when the Supabase client knows
  WHO is making the request.  We tell it by calling:
    client.postgrest.auth(token)
  before the query.  Without this call, auth.uid() is null and every
  insert/select is rejected by RLS.  We use the raw JWT (not a service
  role key) so the user can only access their own rows.

PRIVACY
  resume_text and job_description are no longer stored — they contain
  personal data the app does not need to re-read after saving.
  user_token is never logged.
"""

import logging

from supabase import Client

from app.schemas.analysis import AnalysisResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class DBSaveError(Exception):
    """Raised when inserting a new analysis record fails."""


class DBFetchError(Exception):
    """Raised when fetching a user's history fails."""


class DBNotFoundError(Exception):
    """
    Raised when a specific analysis row does not exist OR belongs to a
    different user.  We treat both as "not found" so callers return 404
    without leaking whether the row exists at all.
    """


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _authenticated_client(supabase: Client, user_token: str) -> Client:
    """
    Return the same Supabase client after calling postgrest.auth(token).

    WHY: Calling .auth(token) sets an Authorization header on every
    subsequent postgrest query so auth.uid() returns the correct UUID
    and RLS policies are satisfied.
    """
    supabase.postgrest.auth(user_token)
    return supabase


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_analysis(
    supabase: Client,
    user_id: str,
    user_token: str,
    company_name: str,
    result: AnalysisResult,
) -> None:
    """
    Insert one analysis record into public.analyses.

    WHY resume_text and job_description are no longer stored:
      They contain personal data (the candidate's full resume and the
      employer's job description).  The app never needs to re-read them
      from the database — the analysis result_json already contains
      everything the user needs to review their history.  Storing them
      would create an unnecessary privacy liability.

    Raises DBSaveError if the insert fails.
    The caller swallows this so the user still gets their result.
    """
    try:
        client = _authenticated_client(supabase, user_token)
        client.table("analyses").insert({
            "user_id":      user_id,
            "company_name": company_name,
            "match_score":  result.match_score,
            "result_json":  result.model_dump(),
        }).execute()
    except Exception as exc:
        logger.error(
            "save_analysis failed | error_type=%s | message=%s",
            type(exc).__name__,
            str(exc)[:120],
        )
        raise DBSaveError(f"Could not save analysis: {type(exc).__name__}") from exc


def get_user_analyses(
    supabase: Client,
    user_id: str,
    user_token: str,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """
    Fetch a page of analysis summaries for one user, newest first.

    Returns list of dicts with keys: id, company_name, match_score, created_at
    Raises DBFetchError if the query fails.
    """
    try:
        client = _authenticated_client(supabase, user_token)
        response = (
            client.table("analyses")
            .select("id, company_name, match_score, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return response.data or []
    except Exception as exc:
        logger.error(
            "get_user_analyses failed | error_type=%s | message=%s",
            type(exc).__name__,
            str(exc)[:120],
        )
        raise DBFetchError(f"Could not fetch analyses: {type(exc).__name__}") from exc


def get_analysis_detail(
    supabase: Client,
    analysis_id: str,
    user_id: str,
    user_token: str,
) -> dict:
    """
    Fetch one analysis row by its UUID.

    Returns: id, company_name, match_score, created_at, result_json.
    resume_text and job_description are never selected — they are not
    stored any more and were never needed by the API response.

    Belt-and-braces security:
      1. postgrest.auth(token) → RLS "SELECT: auth.uid() = user_id"
      2. Explicit .eq("user_id", user_id) filter as a second layer.

    Raises DBNotFoundError if the row doesn't exist or belongs to
    another user.  Raises DBFetchError on any other DB error.
    """
    try:
        client = _authenticated_client(supabase, user_token)
        response = (
            client.table("analyses")
            .select("id, company_name, match_score, created_at, result_json")
            .eq("id", analysis_id)
            .eq("user_id", user_id)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise DBNotFoundError(analysis_id)
        return rows[0]
    except DBNotFoundError:
        raise
    except Exception as exc:
        logger.error(
            "get_analysis_detail failed | error_type=%s | message=%s",
            type(exc).__name__,
            str(exc)[:120],
        )
        raise DBFetchError(f"Could not fetch analysis: {type(exc).__name__}") from exc
