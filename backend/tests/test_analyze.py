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
from app.schemas.analysis import AnalysisResult
from app.services.llm_service import (
    LLMInvalidOutputError,
    LLMMissingKeyError,
    LLMModelError,
    LLMNetworkError,
    LLMTimeoutError,
)
from app.services.pdf_service import PDFNoTextError, PDFParseError

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
        {"question": f"Q{i}?", "category": "technical", "answer_outline": f"A{i}"}
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
