"""
Tests for GET /analyses (list) and GET /analyses/{id} (detail).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.supabase_client import get_supabase
from app.dependencies.auth import get_current_user
from app.services.db_service import DBFetchError, DBNotFoundError

FAKE_USER = {"sub": "user-uuid-1234", "email": "test@example.com", "_token": "fake.jwt.token"}
FAKE_OTHER_USER = {"sub": "other-user-uuid", "email": "other@example.com", "_token": "other.token"}

FAKE_ROWS = [
    {"id": "aaaaaaaa-0000-0000-0000-000000000001", "company_name": "Acme Corp",
     "match_score": 72, "created_at": "2026-09-01T10:00:00Z"},
    {"id": "aaaaaaaa-0000-0000-0000-000000000002", "company_name": "Beta Ltd",
     "match_score": 55, "created_at": "2026-09-02T10:00:00Z"},
]

FAKE_DETAIL_ROW = {
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "company_name": "Acme Corp",
    "match_score": 72,
    "created_at": "2026-09-01T10:00:00Z",
    "result_json": {
        "match_score": 72,
        "matched_skills": ["Python"],
        "skill_gaps": [{"skill": "Docker", "tip": "Learn Docker."}],
        "resume_wording_tips": [],
        "questions": [],
    },
}

_mock_supabase = MagicMock()


def _client_with_auth(user=None):
    app.dependency_overrides[get_current_user] = lambda: (user or FAKE_USER)
    app.dependency_overrides[get_supabase]     = lambda: _mock_supabase
    return TestClient(app, raise_server_exceptions=False)


def _client_no_auth():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides[get_supabase] = lambda: _mock_supabase
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_supabase, None)


# ── List endpoint ────────────────────────────────────────────────────────────

def test_get_analyses_without_token_returns_401():
    client = _client_no_auth()
    assert client.get("/analyses").status_code == 401


def test_get_analyses_with_valid_token_returns_200():
    client = _client_with_auth()
    with patch("app.api.routes.history.get_user_analyses", return_value=FAKE_ROWS):
        response = client.get("/analyses")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["analyses"][0]["company_name"] == "Acme Corp"


def test_get_analyses_returns_empty_list_when_no_history():
    client = _client_with_auth()
    with patch("app.api.routes.history.get_user_analyses", return_value=[]):
        response = client.get("/analyses")
    assert response.status_code == 200
    assert response.json()["analyses"] == []


def test_get_analyses_returns_503_on_db_error():
    client = _client_with_auth()
    with patch("app.api.routes.history.get_user_analyses", side_effect=DBFetchError("DB down")):
        response = client.get("/analyses")
    assert response.status_code == 503
    assert "history" in response.json()["detail"].lower()


def test_get_analyses_pagination_passes_limit_and_offset():
    client = _client_with_auth()
    with patch("app.api.routes.history.get_user_analyses", return_value=[]) as mock_fn:
        client.get("/analyses?limit=5&offset=10")
    _, kwargs = mock_fn.call_args
    assert kwargs["limit"] == 5
    assert kwargs["offset"] == 10


def test_get_analyses_passes_token_to_db_service():
    client = _client_with_auth()
    with patch("app.api.routes.history.get_user_analyses", return_value=[]) as mock_fn:
        client.get("/analyses")
    _, kwargs = mock_fn.call_args
    assert kwargs["user_token"] == "fake.jwt.token"


# ── Detail endpoint ──────────────────────────────────────────────────────────

VALID_UUID = "aaaaaaaa-0000-0000-0000-000000000001"


def test_get_analysis_detail_returns_200_for_own_analysis():
    """Owner of the analysis gets 200 with result_json."""
    client = _client_with_auth()
    with patch("app.api.routes.history.get_analysis_detail", return_value=FAKE_DETAIL_ROW):
        response = client.get(f"/analyses/{VALID_UUID}")
    assert response.status_code == 200
    body = response.json()
    assert body["company_name"] == "Acme Corp"
    assert body["match_score"] == 72
    assert "result_json" in body
    # resume_text must not appear in the response
    assert "resume_text" not in body
    assert "job_description" not in body


def test_get_analysis_detail_returns_404_for_another_users_id():
    """
    If the row exists but belongs to another user, db_service raises
    DBNotFoundError (RLS returns 0 rows + our explicit user_id filter).
    The route must return 404, never 403, so existence is not leaked.
    """
    client = _client_with_auth()
    with patch(
        "app.api.routes.history.get_analysis_detail",
        side_effect=DBNotFoundError(VALID_UUID),
    ):
        response = client.get(f"/analyses/{VALID_UUID}")
    assert response.status_code == 404


def test_get_analysis_detail_returns_404_for_unknown_id():
    """A valid UUID that doesn't exist in the DB returns 404."""
    unknown = "bbbbbbbb-0000-0000-0000-000000000099"
    client = _client_with_auth()
    with patch(
        "app.api.routes.history.get_analysis_detail",
        side_effect=DBNotFoundError(unknown),
    ):
        response = client.get(f"/analyses/{unknown}")
    assert response.status_code == 404


def test_get_analysis_detail_returns_404_for_invalid_id_format():
    """
    A non-UUID string (e.g. 'not-a-uuid') must return 404 without
    hitting the database at all — UUID format is validated in the route.
    """
    client = _client_with_auth()
    with patch("app.api.routes.history.get_analysis_detail") as mock_fn:
        response = client.get("/analyses/not-a-uuid")
    assert response.status_code == 404
    # DB must not have been called for an invalid format
    mock_fn.assert_not_called()


def test_get_analysis_detail_requires_auth():
    """GET /analyses/{id} without a token must return 401."""
    client = _client_no_auth()
    response = client.get(f"/analyses/{VALID_UUID}")
    assert response.status_code == 401
