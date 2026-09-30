"""
Tests for POST /resume/parse.

We generate all PDF bytes in-process using reportlab so no binary files
need to be committed to git.  Each helper function returns bytes that
represent a specific scenario.
"""

import io

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# PDF factory helpers
# ---------------------------------------------------------------------------

def _make_pdf_with_text(text: str) -> bytes:
    """Create a minimal single-page PDF containing the given text string."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    # drawString(x, y, text) — coordinates are in points from bottom-left
    c.drawString(50, 700, text)
    c.save()
    return buf.getvalue()


def _make_pdf_no_text() -> bytes:
    """
    Create a PDF that has a page but no text operators.
    pdfplumber will open it fine but extract an empty string — our service
    should raise PDFNoTextError in this case.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    # Save the page without drawing any text
    c.save()
    return buf.getvalue()


def _make_oversized_pdf(mb: int = 6) -> bytes:
    """
    Return a bytes object that is larger than MAX_UPLOAD_MB (default 5 MB).
    We embed a large comment block to pad the size — still a valid PDF.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.drawString(50, 700, "Oversized file")
    c.save()
    # Pad with null bytes to push it over the limit
    pdf_bytes = buf.getvalue()
    padding = b"\x00" * (mb * 1024 * 1024)
    return pdf_bytes + padding


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_valid_pdf_returns_text():
    """A well-formed PDF with text should return 200 with the extracted text."""
    pdf_bytes = _make_pdf_with_text("Python Developer  Skills: FastAPI  Experience: 2 years")

    response = client.post(
        "/resume/parse",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    # All three fields must be present
    assert "text" in body
    assert "page_count" in body
    assert "char_count" in body
    # The extracted text must contain something meaningful
    assert len(body["text"]) > 0
    assert body["page_count"] == 1
    assert body["char_count"] == len(body["text"])


def test_non_pdf_file_rejected():
    """Uploading a plain-text file with a .txt extension must return 400."""
    text_bytes = b"This is just a plain text file, not a PDF."

    response = client.post(
        "/resume/parse",
        files={"file": ("resume.txt", text_bytes, "text/plain")},
    )

    assert response.status_code == 400
    # The error message should guide the user
    assert "PDF" in response.json()["detail"]


def test_empty_file_rejected():
    """
    An empty file has 0 bytes — pdfplumber cannot open it, so it should
    come back as a 400 (corrupt/unreadable PDF).
    """
    response = client.post(
        "/resume/parse",
        files={"file": ("resume.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400


def test_oversized_file_rejected():
    """A file larger than MAX_UPLOAD_MB must return 413."""
    big_bytes = _make_oversized_pdf(mb=6)

    response = client.post(
        "/resume/parse",
        files={"file": ("resume.pdf", big_bytes, "application/pdf")},
    )

    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()


def test_pdf_with_no_text_rejected():
    """
    A PDF with no text content (e.g. a blank canvas) must return 422
    with a message explaining why.
    """
    pdf_bytes = _make_pdf_no_text()

    response = client.post(
        "/resume/parse",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 422
    assert "text" in response.json()["detail"].lower()
