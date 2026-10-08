"""
Tests for app/services/db_service.py.

STRATEGY — mock the Supabase client entirely.
  We pass a MagicMock as the 'supabase' argument to each function.
  No real network calls, no real database needed.

KEY ASSERTIONS:
  - postgrest.auth(token) must be called before every insert/select
    so that RLS auth.uid() = user_id is satisfied.
  - resume_text and job_description must NOT appear in the insert dict —
    they are no longer stored.
"""

from unittest.mock import MagicMock
import pytest

from app.schemas.analysis import AnalysisResult
from app.services.db_service import (
    DBFetchError,
    DBSaveError,
    get_user_analyses,
    save_analysis,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

USER_ID    = "user-uuid-1234"
USER_TOKEN = "fake.jwt.token"

MOCK_RESULT = AnalysisResult(
    match_score=70,
    matched_skills=["Python"],
    skill_gaps=[{"skill": "Docker", "tip": "Learn Docker."}],
    resume_wording_tips=[],
    questions=[
        {
            "question": f"Q{i}?",
            "category": "technical",
            "answer_outline": (
                f"This question covers topic {i} from the resume. "
                f"The candidate used Python to build a REST API in their backend project."
            ),
        }
        for i in range(1, 11)
    ],
)


# ---------------------------------------------------------------------------
# save_analysis tests
# ---------------------------------------------------------------------------

def test_save_analysis_calls_postgrest_auth_before_insert():
    """
    save_analysis must call client.postgrest.auth(user_token) BEFORE the
    insert so that RLS auth.uid() = user_id is satisfied in the database.
    """
    mock_supabase = MagicMock()

    save_analysis(
        supabase=mock_supabase,
        user_id=USER_ID,
        user_token=USER_TOKEN,
        company_name="Acme Corp",
        result=MOCK_RESULT,
    )

    mock_supabase.postgrest.auth.assert_called_once_with(USER_TOKEN)
    mock_supabase.table.assert_called_once_with("analyses")


def test_save_analysis_calls_insert_with_correct_data():
    """
    save_analysis must pass the correct field values to the insert call.
    resume_text and job_description must NOT be in the insert dict.
    """
    mock_supabase = MagicMock()

    save_analysis(
        supabase=mock_supabase,
        user_id=USER_ID,
        user_token=USER_TOKEN,
        company_name="Acme Corp",
        result=MOCK_RESULT,
    )

    insert_call = mock_supabase.table.return_value.insert
    insert_call.assert_called_once()
    inserted_data = insert_call.call_args[0][0]

    assert inserted_data["user_id"]      == USER_ID
    assert inserted_data["company_name"] == "Acme Corp"
    assert inserted_data["match_score"]  == 70
    assert "result_json"                 in inserted_data

    # Privacy check — these must not be stored any more
    assert "resume_text"     not in inserted_data
    assert "job_description" not in inserted_data


def test_save_analysis_raises_db_save_error_on_failure():
    """
    If the Supabase client raises any exception, save_analysis must
    wrap it in DBSaveError.
    """
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.side_effect = (
        Exception("network failure")
    )

    with pytest.raises(DBSaveError):
        save_analysis(
            supabase=mock_supabase,
            user_id=USER_ID,
            user_token=USER_TOKEN,
            company_name="Acme",
            result=MOCK_RESULT,
        )


# ---------------------------------------------------------------------------
# get_user_analyses tests
# ---------------------------------------------------------------------------

def test_get_user_analyses_calls_postgrest_auth_before_select():
    mock_supabase = MagicMock()
    mock_supabase.table.return_value \
        .select.return_value.eq.return_value \
        .order.return_value.range.return_value \
        .execute.return_value.data = []

    get_user_analyses(mock_supabase, USER_ID, user_token=USER_TOKEN)

    mock_supabase.postgrest.auth.assert_called_once_with(USER_TOKEN)


def test_get_user_analyses_returns_mapped_list():
    mock_supabase = MagicMock()
    fake_rows = [
        {"id": "uuid-1", "company_name": "Acme", "match_score": 70, "created_at": "2026-01-01T00:00:00Z"},
        {"id": "uuid-2", "company_name": "Beta", "match_score": 55, "created_at": "2026-01-02T00:00:00Z"},
    ]
    mock_supabase.table.return_value \
        .select.return_value.eq.return_value \
        .order.return_value.range.return_value \
        .execute.return_value.data = fake_rows

    result = get_user_analyses(mock_supabase, USER_ID, user_token=USER_TOKEN)

    assert len(result) == 2
    assert result[0]["company_name"] == "Acme"


def test_get_user_analyses_returns_empty_list_when_no_rows():
    mock_supabase = MagicMock()
    mock_supabase.table.return_value \
        .select.return_value.eq.return_value \
        .order.return_value.range.return_value \
        .execute.return_value.data = []

    assert get_user_analyses(mock_supabase, USER_ID, user_token=USER_TOKEN) == []


def test_get_user_analyses_raises_db_fetch_error_on_failure():
    mock_supabase = MagicMock()
    mock_supabase.table.return_value \
        .select.return_value.eq.return_value \
        .order.return_value.range.return_value \
        .execute.side_effect = Exception("DB down")

    with pytest.raises(DBFetchError):
        get_user_analyses(mock_supabase, USER_ID, user_token=USER_TOKEN)
