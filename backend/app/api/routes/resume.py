from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.schemas.resume import ResumeParseResponse
from app.services.pdf_service import (
    PDFNoTextError,
    PDFParseError,
    PDFPasswordProtectedError,
    parse_resume,
)

router = APIRouter(prefix="/resume", tags=["resume"])

# Bytes in one megabyte — used to convert the config value to bytes.
_BYTES_PER_MB = 1024 * 1024


@router.post("/parse", response_model=ResumeParseResponse)
async def parse_resume_endpoint(file: UploadFile = File(...)):
    """
    Accept a resume PDF, extract its text, and return it.

    Validations (in order):
      1. File must have a .pdf extension.
      2. Content-Type must be application/pdf.
      3. File must not exceed MAX_UPLOAD_MB.
      4. The PDF must be readable, unlocked, and contain text.
    """

    # --- 1. Extension check ---
    # Checking the extension is a quick first guard against obvious mistakes
    # like uploading a .docx or .jpg by accident.
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Please upload a file with a .pdf extension.",
        )

    # --- 2. Content-Type check ---
    # A malicious user could rename any file to .pdf, so we also check what
    # the browser declared as the file type.
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Expected content-type application/pdf.",
        )

    # --- 3. Size check ---
    # We read all bytes into memory once, which is fine for files up to a few MB.
    # Reading first lets us reject oversized files before doing expensive PDF work.
    pdf_bytes = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * _BYTES_PER_MB
    if len(pdf_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_MB} MB. "
                f"Your file is {len(pdf_bytes) / _BYTES_PER_MB:.1f} MB."
            ),
        )

    # --- 4. Parse PDF ---
    # All the PDF logic lives in the service.  The route just translates
    # service exceptions into HTTP error codes — that separation makes
    # each layer easy to test and change independently.
    try:
        result = parse_resume(pdf_bytes)
    except PDFPasswordProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PDFNoTextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PDFParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # --- 5. Truncate if needed ---
    text = result["text"]
    if len(text) > settings.MAX_RESUME_CHARS:
        text = text[: settings.MAX_RESUME_CHARS]

    # NOTE: we deliberately do NOT log the text here — it is personal data.
    return ResumeParseResponse(
        text=text,
        page_count=result["page_count"],
        char_count=len(text),
    )
