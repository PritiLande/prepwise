"""
Tests for POST /analyze.

STRATEGY — two levels of mocking
  1. pdf_service.parse_resume is patched so we never need a real PDF file.
  2. llm_service.analyze is patched so we never call the real Groq API.

  This tests the route's own responsibilities:
    - Input validation (extension, content-type, size, empty fields, JD length).
    - Correct HTTP status codes for every service error.
    - A successful end-to-end flow through the route.
    - Rate limiting (429 when the IP exceeds RATE_LIMIT_ANALYZE).

  The services themselves are tested in test_resume.py and test_llm_service.py.
"""

import io
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from app.main import app
from app.core.limiter import limiter
from app.core.supabase_client import get_supabase
from app.dependencies.auth import get_optional_user
from app.schemas.analysis import AnalysisResult
from app.services.llm_service import (
    LLMInvalidOutputError,
    LLMMissingKeyError,
    LLMModelError,
    LLMNetworkError,
    LLMTimeoutError,
)
from app.services.pdf_service import PDFNoTextError, PDFParseError

# Override Supabase and auth dependencies for ALL tests in this file.
# The existing 12 tests are unauthenticated so current_user must be None.
# get_supabase returns a MagicMock so no real DB connection is attempted.
_mock_supabase = MagicMock()
app.dependency_overrides[get_supabase] = lambda: _mock_supabase
app.dependency_overrides[get_optional_user] = lambda: None   # no auth by default

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Auto-reset the rate limiter before every test
# ---------------------------------------------------------------------------
# slowapi uses an in-memory counter that persists across tests in the same
# process.  Without this fixture tests 6+ would all hit 429 because the
# first 5 successful calls exhausted the default "5/minute" limit.
@pytest.fixture(autouse=True)
def reset_limiter():
    """Clear all rate-limit counters before each test."""
    limiter.reset()
    yield

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_pdf(text: str = "Jane Doe  Python Developer") -> bytes:
    """Create a minimal in-memory PDF with the given text."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.drawString(50, 700, text)
    c.save()
    return buf.getvalue()


# A valid AnalysisResult object returned by the mocked analyze().
MOCK_RESULT = AnalysisResult(
    match_score=75,
    matched_skills=["Python", "FastAPI"],
    skill_gaps=[
        {"skill": "Docker", "tip": "Learn Docker basics."},
    ],
    resume_wording_tips=["Add 'pytest' to your skills section."],
    questions=[
        {
            "question": f"Q{i}?",
            "category": "technical",
            "answer_outline": (
                f"This question covers topic {i} from the candidate's resume. "
                f"In the relevant project, Python and FastAPI were used to build the backend."
            ),
        }
        for i in range(1, 11)
    ],
)

# Parsed resume dict returned by the mocked parse_resume().
MOCK_PARSED = {"text": "Jane Doe  Python Developer", "page_count": 1}

# Multipart form fields used in every happy-path call.
GOOD_FIELDS = {
    "job_description": "We need a Python developer with FastAPI and Docker.",
    "company_name": "Acme Corp",
}


# ---------------------------------------------------------------------------
# Helper — post to /analyze with a PDF and form fields
# ---------------------------------------------------------------------------

def _post(pdf_bytes: bytes, fields: dict = None, filename: str = "resume.pdf",
          content_type: str = "application/pdf"):
    fields = fields or GOOD_FIELDS
    return client.post(
        "/analyze",
        files={"resume": (filename, pdf_bytes, content_type)},
        data=fields,
    )


# ---------------------------------------------------------------------------
# Test 1: success — returns 200 with the full AnalysisResult shape
# ---------------------------------------------------------------------------

def test_analyze_success():
    """A valid PDF + valid fields → 200 with the expected JSON shape."""
    with patch("app.api.routes.analyze.parse_resume", return_value=MOCK_PARSED), \
         patch("app.api.routes.analyze.analyze", return_value=MOCK_RESULT):
        response = _post(_make_pdf())

    assert response.status_code == 200
    body = response.json()
    assert body["match_score"] == 75
    assert "Python" in body["matched_skills"]
    assert len(body["questions"]) == 10
    assert isinstance(body["resume_wording_tips"], list)


# ---------------------------------------------------------------------------
# Test 2: non-PDF file → 400
# ---------------------------------------------------------------------------

def test_analyze_rejects_non_pdf():
    """Uploading a .txt file must return 400."""
    response = _post(
        b"just plain text",
        filename="resume.txt",
        content_type="text/plain",
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Test 3: empty job_description → 400
# ---------------------------------------------------------------------------

def test_analyze_rejects_empty_jd():
    """An empty job_description must return 400."""
    with patch("app.api.routes.analyze.parse_resume", return_value=MOCK_PARSED):
        response = _post(_make_pdf(), fields={"job_description": "  ", "company_name": "Acme"})
    assert response.status_code == 400
    assert "job_description" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Test 4: oversized file → 413
# ---------------------------------------------------------------------------

def test_analyze_rejects_oversized_file():
    """A file larger than MAX_UPLOAD_MB must return 413."""
    big = _make_pdf() + b"\x00" * (6 * 1024 * 1024)  # ~6 MB padding
    response = _post(big)
    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 5: corrupt PDF (PDFParseError) → 400
# ---------------------------------------------------------------------------

def test_analyze_corrupt_pdf_returns_400():
    """If parse_resume raises PDFParseError, the route must return 400."""
    with patch(
        "app.api.routes.analyze.parse_resume",
        side_effect=PDFParseError("Corrupt file."),
    ):
        response = _post(_make_pdf())
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Test 6: scanned PDF (PDFNoTextError) → 422
# ---------------------------------------------------------------------------

def test_analyze_no_text_pdf_returns_422():
    """If parse_resume raises PDFNoTextError, the route must return 422."""
    with patch(
        "app.api.routes.analyze.parse_resume",
        side_effect=PDFNoTextError("No text found."),
    ):
        response = _post(_make_pdf())
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test 7: LLMMissingKeyError → 500 (safe message)
# ---------------------------------------------------------------------------

def test_analyze_missing_key_returns_500():
    """LLMMissingKeyError must produce a 500 with no key details in the message."""
    with patch("app.api.routes.analyze.parse_resume", return_value=MOCK_PARSED), \
         patch(
             "app.api.routes.analyze.analyze",
             side_effect=LLMMissingKeyError("GROQ_API_KEY not set."),
         ):
        response = _post(_make_pdf())

    assert response.status_code == 500
    detail = response.json()["detail"]
    # Safe message — must not leak the real error text
    assert "GROQ_API_KEY" not in detail
    assert "configured" in detail.lower()


# ---------------------------------------------------------------------------
# Test 8: LLMModelError → 500 (safe message)
# ---------------------------------------------------------------------------

def test_analyze_model_error_returns_500():
    """LLMModelError must produce a 500 with a safe message."""
    with patch("app.api.routes.analyze.parse_resume", return_value=MOCK_PARSED), \
         patch(
             "app.api.routes.analyze.analyze",
             side_effect=LLMModelError("Model decommissioned."),
         ):
        response = _post(_make_pdf())

    assert response.status_code == 500
    assert "administrator" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 9: LLMTimeoutError → 504
# ---------------------------------------------------------------------------

def test_analyze_timeout_returns_504():
    """LLMTimeoutError must produce a 504 Gateway Timeout."""
    with patch("app.api.routes.analyze.parse_resume", return_value=MOCK_PARSED), \
         patch(
             "app.api.routes.analyze.analyze",
             side_effect=LLMTimeoutError("Timed out."),
         ):
        response = _post(_make_pdf())

    assert response.status_code == 504


# ---------------------------------------------------------------------------
# Test 10: LLMNetworkError → 504
# ---------------------------------------------------------------------------

def test_analyze_network_error_returns_504():
    """LLMNetworkError (unreachable upstream) must produce a 504."""
    with patch("app.api.routes.analyze.parse_resume", return_value=MOCK_PARSED), \
         patch(
             "app.api.routes.analyze.analyze",
             side_effect=LLMNetworkError("Connection refused."),
         ):
        response = _post(_make_pdf())

    assert response.status_code == 504


# ---------------------------------------------------------------------------
# Test 11: LLMInvalidOutputError → 502
# ---------------------------------------------------------------------------

def test_analyze_invalid_output_returns_502():
    """LLMInvalidOutputError must produce a 502 Bad Gateway."""
    with patch("app.api.routes.analyze.parse_resume", return_value=MOCK_PARSED), \
         patch(
             "app.api.routes.analyze.analyze",
             side_effect=LLMInvalidOutputError("Bad JSON."),
         ):
        response = _post(_make_pdf())

    assert response.status_code == 502


# ---------------------------------------------------------------------------
# Test 12: rate limit → 429
# ---------------------------------------------------------------------------

def test_analyze_rate_limit_returns_429(monkeypatch):
    """
    After RATE_LIMIT_ANALYZE requests from the same IP, the next one must
    return 429.  We patch the limit to '1/minute' so we only need 2 calls.
    """
    monkeypatch.setattr(
        "app.api.routes.analyze.settings.RATE_LIMIT_ANALYZE", "1/minute"
    )
    pdf = _make_pdf()

    with patch("app.api.routes.analyze.parse_resume", return_value=MOCK_PARSED), \
         patch("app.api.routes.analyze.analyze", return_value=MOCK_RESULT):
        # First request — must succeed
        r1 = _post(pdf)
        assert r1.status_code == 200

        # Second request — must be rejected
        r2 = _post(pdf)
        assert r2.status_code == 429

# ---------------------------------------------------------------------------
# Phase 6 additions — DB save behaviour
# ---------------------------------------------------------------------------

def test_analyze_saves_to_db_when_user_is_authenticated():
    """
    When a valid user is injected, save_analysis must be called once
    with the correct user_id and user_token after a successful analysis.
    resume_text and job_description must NOT be passed to save_analysis.
    """
    from app.dependencies.auth import get_optional_user as _opt

    app.dependency_overrides[_opt] = lambda: {"sub": "user-uuid-abc", "_token": "fake.jwt.token"}

    with patch("app.api.routes.analyze.parse_resume", return_value=MOCK_PARSED), \
         patch("app.api.routes.analyze.analyze", return_value=MOCK_RESULT), \
         patch("app.api.routes.analyze.save_analysis") as mock_save:

        response = _post(_make_pdf())

    assert response.status_code == 200
    mock_save.assert_called_once()
    call_kwargs = mock_save.call_args.kwargs
    assert call_kwargs["user_id"]    == "user-uuid-abc"
    assert call_kwargs["user_token"] == "fake.jwt.token"
    # Privacy: these must not be forwarded to the DB layer any more
    assert "resume_text"     not in call_kwargs
    assert "job_description" not in call_kwargs

    app.dependency_overrides[_opt] = lambda: None


def test_analyze_returns_result_even_if_db_save_fails():
    """
    If save_analysis raises DBSaveError, the /analyze route must still
    return 200 — the user already has their result.
    """
    from app.dependencies.auth import get_optional_user as _opt
    from app.services.db_service import DBSaveError

    app.dependency_overrides[_opt] = lambda: {"sub": "user-uuid-abc", "_token": "fake.jwt.token"}

    with patch("app.api.routes.analyze.parse_resume", return_value=MOCK_PARSED), \
         patch("app.api.routes.analyze.analyze", return_value=MOCK_RESULT), \
         patch("app.api.routes.analyze.save_analysis", side_effect=DBSaveError("fail")):

        response = _post(_make_pdf())

    assert response.status_code == 200

    app.dependency_overrides[_opt] = lambda: None


def test_analyze_does_not_call_save_when_unauthenticated():
    """
    When no token is provided (current_user is None), save_analysis must
    never be called — unauthenticated analyses are not persisted.
    """
    # Default override already sets current_user to None (see top of file)
    with patch("app.api.routes.analyze.parse_resume", return_value=MOCK_PARSED), \
         patch("app.api.routes.analyze.analyze", return_value=MOCK_RESULT), \
         patch("app.api.routes.analyze.save_analysis") as mock_save:

        response = _post(_make_pdf())

    assert response.status_code == 200
    mock_save.assert_not_called()


# ---------------------------------------------------------------------------
# Test: create_client raises → /analyze still returns 200
# ---------------------------------------------------------------------------

def test_analyze_returns_200_when_supabase_client_creation_fails():
    """
    If create_client() raises (e.g. Invalid API key), get_supabase() returns
    None.  The route must still return 200 with the full analysis result.
    """
    from app.dependencies.auth import get_optional_user as _opt
    from app.core.supabase_client import get_supabase as _get_sb

    app.dependency_overrides[_opt] = lambda: {"sub": "user-uuid-abc", "_token": "fake.jwt.token"}
    app.dependency_overrides[_get_sb] = lambda: None

    with patch("app.api.routes.analyze.parse_resume", return_value=MOCK_PARSED), \
         patch("app.api.routes.analyze.analyze", return_value=MOCK_RESULT), \
         patch("app.api.routes.analyze.save_analysis") as mock_save:

        response = _post(_make_pdf())

    assert response.status_code == 200
    assert response.json()["match_score"] == 75
    mock_save.assert_not_called()

    app.dependency_overrides[_opt] = lambda: None
    app.dependency_overrides[_get_sb] = lambda: _mock_supabase


# ---------------------------------------------------------------------------
# JWKS failure with optional auth — must still return 200
# ---------------------------------------------------------------------------

def test_analyze_returns_200_when_jwks_unavailable_with_token():
    """
    When a token IS present but the JWKS endpoint is unreachable (503),
    POST /analyze must still return 200 with the full analysis result.

    WHY: The user sent a valid-looking token but our auth service is down.
    They should not lose their analysis because of our infrastructure problem.
    get_optional_user catches the 503 from _decode_token and returns None,
    so the route runs as unauthenticated — analysis returned, DB save skipped.

    Contrast with GET /analyses (get_current_user): that correctly returns 503
    because history is personal data and we cannot skip authentication there.

    We test this by letting the real get_optional_user run (not overriding it)
    while patching _decode_token to raise a 503 — exactly what happens when
    _get_public_key raises RuntimeError during a real JWKS outage.
    """
    from fastapi import HTTPException, status
    from app.dependencies.auth import get_optional_user as _opt

    # Remove the module-level override so the REAL get_optional_user runs
    app.dependency_overrides.pop(_opt, None)

    with patch("app.api.routes.analyze.parse_resume", return_value=MOCK_PARSED), \
         patch("app.api.routes.analyze.analyze", return_value=MOCK_RESULT), \
         patch("app.api.routes.analyze.save_analysis") as mock_save, \
         patch("app.dependencies.auth._decode_token",
               side_effect=HTTPException(
                   status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                   detail="Authentication service temporarily unavailable.",
               )):

        # Send request WITH an Authorization header so get_optional_user
        # actually calls _decode_token (without a header it returns None immediately)
        response = client.post(
            "/analyze",
            files={"resume": ("resume.pdf", _make_pdf(), "application/pdf")},
            data=GOOD_FIELDS,
            headers={"Authorization": "Bearer fake.token.string"},
        )

    # Must return 200 — the analysis is not lost
    assert response.status_code == 200
    assert response.json()["match_score"] == 75

    # DB save must NOT be attempted — we have no verified user identity
    mock_save.assert_not_called()

    # Restore the module-level default (no auth)
    app.dependency_overrides[_opt] = lambda: None
