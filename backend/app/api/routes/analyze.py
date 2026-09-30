"""
POST /analyze — the main Prepwise endpoint.

WHY keep logic in services, not here?
  This route is only responsible for HTTP concerns:
    - Read the incoming request fields.
    - Validate inputs (size, type, length).
    - Call the service functions.
    - Map service exceptions to the right HTTP status codes.
    - Return the response.

  All PDF parsing lives in pdf_service.py and all LLM logic lives in
  llm_service.py.  That means:
    - Each service can be tested without HTTP.
    - The route stays short and easy to read.
    - We can reuse the services from other routes later.

ERROR MAPPING
  400  bad file (not PDF, corrupt, password-protected) or bad input
  413  file too large
  422  PDF has no extractable text (scanned image)
  429  rate limit exceeded (slowapi)
  500  LLM key missing or model decommissioned (safe message, no key leak)
  502  LLM returned invalid output after all retries
  504  LLM timed out or network failure

PRIVACY
  Never log resume text, JD text, or the API key.
"""

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.core.config import settings
from app.core.limiter import limiter
from app.schemas.analysis import AnalysisResult
from app.services.llm_service import (
    LLMInvalidOutputError,
    LLMMissingKeyError,
    LLMModelError,
    LLMNetworkError,
    LLMTimeoutError,
    analyze,
)
from app.services.pdf_service import (
    PDFNoTextError,
    PDFParseError,
    PDFPasswordProtectedError,
    parse_resume,
)

router = APIRouter(tags=["analyze"])

_BYTES_PER_MB = 1024 * 1024


@router.post("/analyze", response_model=AnalysisResult)
@limiter.limit(lambda: settings.RATE_LIMIT_ANALYZE)
async def analyze_endpoint(
    request: Request,
    resume: UploadFile = File(..., description="Resume PDF, max 5 MB."),
    job_description: str = Form(..., description="Job description text."),
    company_name: str = Form(..., description="Company name (1-100 characters)."),
):
    """
    Accept a resume PDF, a job description, and a company name.
    Return a match score, skill gaps, wording tips, and 10 interview questions.
    """

    # ------------------------------------------------------------------ #
    # 1. Validate company_name                                             #
    # ------------------------------------------------------------------ #
    company_name = company_name.strip()
    if not company_name:
        raise HTTPException(status_code=400, detail="company_name must not be empty.")
    if len(company_name) > 100:
        raise HTTPException(
            status_code=400,
            detail="company_name must be 100 characters or fewer.",
        )

    # ------------------------------------------------------------------ #
    # 2. Validate job_description                                          #
    # ------------------------------------------------------------------ #
    job_description = job_description.strip()
    if not job_description:
        raise HTTPException(status_code=400, detail="job_description must not be empty.")
    if len(job_description) > settings.MAX_JD_CHARS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"job_description exceeds {settings.MAX_JD_CHARS} characters. "
                "Please shorten it."
            ),
        )

    # ------------------------------------------------------------------ #
    # 3. Validate resume — extension and content-type                      #
    # ------------------------------------------------------------------ #
    filename = resume.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Please upload a .pdf file.",
        )
    if resume.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Expected content-type application/pdf.",
        )

    # ------------------------------------------------------------------ #
    # 4. Read bytes and enforce size limit                                 #
    # ------------------------------------------------------------------ #
    pdf_bytes = await resume.read()
    max_bytes = settings.MAX_UPLOAD_MB * _BYTES_PER_MB
    if len(pdf_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_MB} MB. "
                f"Your file is {len(pdf_bytes) / _BYTES_PER_MB:.1f} MB."
            ),
        )

    # ------------------------------------------------------------------ #
    # 5. Parse PDF                                                         #
    # ------------------------------------------------------------------ #
    try:
        parsed = parse_resume(pdf_bytes)
    except PDFPasswordProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PDFNoTextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PDFParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    resume_text = parsed["text"]
    if len(resume_text) > settings.MAX_RESUME_CHARS:
        resume_text = resume_text[: settings.MAX_RESUME_CHARS]

    # ------------------------------------------------------------------ #
    # 6. Call LLM — map every service exception to a clean HTTP response  #
    # ------------------------------------------------------------------ #
    # NOTE: resume_text, job_description, and company_name are NOT logged.
    try:
        result = analyze(
            resume_text=resume_text,
            jd_text=job_description,
            company_name=company_name,
        )
    except (LLMMissingKeyError, LLMModelError):
        # Server misconfiguration — safe message, nothing internal exposed.
        raise HTTPException(
            status_code=500,
            detail="The AI service is not configured correctly. "
                   "Contact the administrator.",
        )
    except LLMTimeoutError:
        raise HTTPException(
            status_code=504,
            detail="The AI service did not respond in time. Please try again.",
        )
    except LLMNetworkError:
        raise HTTPException(
            status_code=504,
            detail="Could not reach the AI service. Please try again later.",
        )
    except LLMInvalidOutputError:
        raise HTTPException(
            status_code=502,
            detail="The AI service returned an unexpected response. "
                   "Please try again.",
        )

    return result
