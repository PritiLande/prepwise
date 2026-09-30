"""
PDF parsing service.

WHY keep logic here and not in the route?
  Routes should only handle HTTP concerns (read the request, return a response).
  Business logic — like how to extract text from a PDF — belongs in a service.
  This way we can test parse_resume() directly without spinning up an HTTP server,
  and we can reuse it from other routes in the future.
"""

import io
import re

import pdfplumber


# ---------------------------------------------------------------------------
# Custom exceptions — we raise these in the service and catch them in the
# route, converting them into proper HTTP error responses there.
# ---------------------------------------------------------------------------

class PDFParseError(Exception):
    """The PDF could not be read at all (corrupt or not a real PDF)."""


class PDFPasswordProtectedError(Exception):
    """The PDF is encrypted and requires a password."""


class PDFNoTextError(Exception):
    """The PDF opened fine but has no extractable text (e.g. a scanned image)."""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _clean_text(raw: str) -> str:
    """
    Turn messy PDF text into something readable.

    Steps:
      1. Replace runs of spaces/tabs with a single space per line.
      2. Remove lines that are now completely empty.
      3. Collapse three or more consecutive blank lines down to two,
         so section gaps are preserved but excessive whitespace is gone.
    """
    lines = []
    for line in raw.splitlines():
        # Collapse internal whitespace on each line
        cleaned = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(cleaned)

    # Drop lines that became empty after stripping
    lines = [l for l in lines if l]

    # Rejoin — each line separated by a single newline
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_resume(pdf_bytes: bytes) -> dict:
    """
    Accept raw PDF bytes and return a dict with:
      - text       : cleaned extracted text
      - page_count : number of pages in the PDF

    Raises:
      PDFPasswordProtectedError  if the file is encrypted
      PDFParseError              if pdfplumber cannot open the file at all
      PDFNoTextError             if the PDF opens but yields no text
    """
    # Wrap bytes in a file-like object so pdfplumber can read it without
    # writing anything to disk — safer and faster than saving a temp file.
    stream = io.BytesIO(pdf_bytes)

    try:
        pdf = pdfplumber.open(stream)
    except Exception as exc:
        # pdfplumber raises pdfminer.pdfdocument.PDFPasswordIncorrect for
        # encrypted files.  We catch broadly and inspect the message so we
        # don't have to import pdfminer internals directly.
        msg = str(exc).lower()
        if "password" in msg or "encrypt" in msg:
            raise PDFPasswordProtectedError(
                "This PDF is password-protected. Please upload an unlocked version."
            ) from exc
        raise PDFParseError(
            "Could not read the PDF. The file may be corrupt or not a valid PDF."
        ) from exc

    with pdf:
        page_count = len(pdf.pages)

        # Extract text from every page and join with a blank line between pages
        # so section headings from the next page don't run into the previous one.
        raw_pages = []
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            raw_pages.append(page_text)

        raw_text = "\n\n".join(raw_pages)

    text = _clean_text(raw_text)

    if not text:
        raise PDFNoTextError(
            "No text could be extracted. The PDF may contain only scanned images. "
            "Please upload a text-based PDF."
        )

    return {"text": text, "page_count": page_count}
