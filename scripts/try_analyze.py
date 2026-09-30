"""
Manual smoke-test script for the LLM analysis service.

Run from the backend/ folder with the venv active:

  python ../scripts/try_analyze.py resume.pdf jd.txt "Acme Corp"

Arguments:
  1. Path to a resume PDF
  2. Path to a plain-text file containing the job description
  3. Company name (in quotes if it has spaces)

This file is intentionally NOT inside the app/ package so it cannot be
accidentally imported by FastAPI or tests.
"""

# truststore MUST be imported and injected before anything that opens an SSL
# connection — including the groq SDK and httpx.  Doing it here, at the very
# top, guarantees that order no matter how Python reorders later imports.
import truststore
truststore.inject_into_ssl()

import json
import sys
from pathlib import Path

# Allow imports from app/ even though this script lives outside backend/
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# Load .env before importing anything from app/ so settings picks up the key
from dotenv import load_dotenv                          # noqa: E402
load_dotenv(Path(__file__).parent.parent / ".env")     # noqa: E402

from app.services.pdf_service import parse_resume      # noqa: E402
from app.services.llm_service import (                 # noqa: E402
    analyze,
    LLMMissingKeyError,
    LLMTimeoutError,
    LLMNetworkError,
    LLMInvalidOutputError,
)


def main() -> None:
    if len(sys.argv) != 4:
        print("Usage: python try_analyze.py <resume.pdf> <jd.txt> \"Company Name\"")
        sys.exit(1)

    pdf_path  = Path(sys.argv[1])
    jd_path   = Path(sys.argv[2])
    company   = sys.argv[3]

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)
    if not jd_path.exists():
        print(f"ERROR: JD file not found: {jd_path}")
        sys.exit(1)

    print(f"\n→ Parsing resume: {pdf_path.name}")
    resume_result = parse_resume(pdf_path.read_bytes())
    print(f"  Pages: {resume_result['page_count']}  "
          f"Characters: {len(resume_result['text'])}")

    print(f"→ Reading job description: {jd_path.name}")
    jd_text = jd_path.read_text(encoding="utf-8")

    print(f"→ Calling Groq (model: from .env) …\n")

    try:
        result = analyze(
            resume_text=resume_result["text"],
            jd_text=jd_text,
            company_name=company,
        )
    except LLMMissingKeyError as e:
        print(f"CONFIG ERROR: {e}")
        sys.exit(1)
    except LLMTimeoutError as e:
        print(f"TIMEOUT: {e}")
        sys.exit(1)
    except (LLMNetworkError, LLMInvalidOutputError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Pretty-print the result as JSON — model_dump() converts Pydantic → dict
    data = result.model_dump()
    print(json.dumps(data, indent=2))

    # Surface the wording tips separately so they are easy to spot
    if result.resume_wording_tips:
        print("\n── Resume Wording Tips ──────────────────────────────")
        for tip in result.resume_wording_tips:
            print(f"  • {tip}")
    else:
        print("\n(No resume wording tips — all relevant keywords already present.)")


if __name__ == "__main__":
    main()
