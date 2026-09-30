"""
LLM analysis service.

WHY keep this separate from the route and the prompt?
  - The route handles HTTP (request in, response out).
  - The prompt file holds the English instructions.
  - This file holds the Python logic: calling Groq, parsing JSON,
    validating with Pydantic, retrying on failure.
  Each layer can be changed, tested, and reused independently.

PRIVACY RULE
  Resume and JD text are personal / confidential.  We never log them.
  We never log the API key either.
"""

import json

from groq import APIStatusError, APITimeoutError, Groq

from app.core.config import settings
from app.prompts.analysis_prompt import SYSTEM_PROMPT, build_user_prompt
from app.schemas.analysis import AnalysisResult


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class LLMMissingKeyError(Exception):
    """GROQ_API_KEY is blank — the service cannot be used."""


class LLMTimeoutError(Exception):
    """Groq did not respond within LLM_TIMEOUT_SECONDS."""


class LLMNetworkError(Exception):
    """A network or API-level error prevented the call from completing."""


class LLMInvalidOutputError(Exception):
    """
    The LLM replied but the output was not valid JSON or did not match
    the expected schema even after all retries.
    """


class LLMModelError(Exception):
    """
    The model name in GROQ_MODEL is not found or has been decommissioned.
    Update GROQ_MODEL in your .env file.
    """


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _call_groq(client: Groq, user_prompt: str) -> str:
    """
    Send one request to Groq and return the raw text reply.
    Raises LLMTimeoutError or LLMNetworkError on failure.
    """
    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            # temperature=0 makes the output deterministic — same input →
            # same output, which is what we want for structured data.
            temperature=0,
            # max_tokens caps the combined reasoning + reply token budget.
            # This model uses internal chain-of-thought reasoning tokens before
            # producing visible output. The value comes from settings so it can
            # be tuned via .env without touching code.
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
    except APITimeoutError as exc:
        raise LLMTimeoutError(
            f"Groq did not respond within {settings.LLM_TIMEOUT_SECONDS} seconds."
        ) from exc
    except APIStatusError as exc:
        # Groq returns 400 with code "model_decommissioned" or 404 for unknown
        # models.  We surface this as a distinct error so the user knows exactly
        # what to fix (the model name in .env), not a generic network failure.
        # We include the model name but never the API key or resume text.
        msg = str(exc.message).lower() if exc.message else ""
        if exc.status_code in (400, 404) and (
            "model" in msg or "decommission" in msg or "not found" in msg
        ):
            raise LLMModelError(
                f"Model '{settings.GROQ_MODEL}' was not found or has been decommissioned. "
                f"Update GROQ_MODEL in your .env file. "
                f"Current models: https://console.groq.com/docs/models"
            ) from exc
        raise LLMNetworkError(
            f"Groq API error {exc.status_code}: {exc.message}"
        ) from exc
    except Exception as exc:
        raise LLMNetworkError(f"Unexpected network error: {exc}") from exc

    # The SDK wraps the reply in a choices list; index 0 is the first (only) reply.
    content = response.choices[0].message.content or ""
    if not content:
        # finish_reason="length" means the model ran out of tokens before
        # producing any output.  Treat it like invalid output so the retry
        # loop can try again.
        raise LLMInvalidOutputError(
            f"Groq returned an empty response (finish_reason="
            f"'{response.choices[0].finish_reason}'). "
            f"The model may have hit its token limit."
        )
    return content


def _parse_and_validate(raw: str) -> AnalysisResult:
    """
    Parse a JSON string and validate it against AnalysisResult.
    Raises ValueError (caught by the retry loop) if anything is wrong.
    """
    # Strip accidental markdown fences like ```json … ``` that some models add
    text = raw.strip()
    if text.startswith("```"):
        # Remove the opening fence line and the closing fence
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    data = json.loads(text)          # raises json.JSONDecodeError if not valid JSON
    return AnalysisResult(**data)    # raises pydantic.ValidationError if schema mismatch


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze(
    resume_text: str,
    jd_text: str,
    company_name: str,
) -> AnalysisResult:
    """
    Call the Groq LLM to analyse a resume against a job description.

    Returns a validated AnalysisResult.

    Raises:
      LLMMissingKeyError     — GROQ_API_KEY not set
      LLMTimeoutError        — Groq timed out
      LLMNetworkError        — API / network failure
      LLMModelError          — model not found or decommissioned
      LLMInvalidOutputError  — bad JSON or schema mismatch after all retries
    """
    if not settings.GROQ_API_KEY:
        raise LLMMissingKeyError(
            "GROQ_API_KEY is not set. Add it to your .env file."
        )

    # Truncate the JD so we don't overshoot the model's context window.
    jd_trimmed = jd_text[: settings.MAX_JD_CHARS]

    user_prompt = build_user_prompt(
        resume_text=resume_text,
        jd_text=jd_trimmed,
        company_name=company_name,
    )

    # total_attempts = 1 first try + LLM_MAX_RETRIES extra attempts
    total_attempts = 1 + settings.LLM_MAX_RETRIES
    # Build the Groq client once and reuse it across retries.
    # We pass the key explicitly so it never falls back to an env lookup
    # that could accidentally log the key via an exception message.
    client = Groq(api_key=settings.GROQ_API_KEY)

    last_error: Exception = LLMInvalidOutputError("No attempts made.")

    for attempt in range(1, total_attempts + 1):
        raw = _call_groq(client, user_prompt)   # may raise Timeout/Network errors

        try:
            return _parse_and_validate(raw)
        except (json.JSONDecodeError, ValueError, Exception) as exc:
            last_error = exc
            # Log only that a retry is happening — never log the raw LLM reply
            # because it echoes resume content.
            if attempt < total_attempts:
                continue  # try again

    raise LLMInvalidOutputError(
        f"LLM output was invalid after {total_attempts} attempt(s): {last_error}"
    ) from last_error
