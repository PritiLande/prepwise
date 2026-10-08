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
  We DO log: exception types, finish_reason, reply length (chars),
  and which validation check failed — nothing that contains user data.

KEY GROQ FACTS FOR gpt-oss-20b (discovered from Groq docs):
  - Use max_completion_tokens, NOT max_tokens (the reasoning model ignores max_tokens).
  - reasoning_effort controls how many tokens the model spends thinking before
    writing the answer.  "low" saves budget for the visible JSON reply.
  - The SDK (groq==0.9.0) does not have reasoning_effort as a named parameter yet;
    pass it via extra_body which the SDK forwards verbatim to the Groq API.
  - Avoid system prompts — all instructions go in the user message (see prompt file).
"""

import json
import logging

from groq import APIStatusError, APITimeoutError, Groq
from pydantic import ValidationError

from app.core.config import settings
from app.prompts.analysis_prompt import SYSTEM_PROMPT, build_user_prompt
from app.schemas.analysis import AnalysisResult

logger = logging.getLogger(__name__)


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

def _call_groq(client: Groq, user_prompt: str, reasoning_effort: str) -> str:
    """
    Send one request to Groq and return the raw text reply.

    Parameters
    ----------
    client          : authenticated Groq client
    user_prompt     : the full prompt string (includes all instructions)
    reasoning_effort: "low" | "medium" | "high" — controls reasoning token budget

    Logs (no user content, no secrets):
      - finish_reason, reply_chars, max_completion_tokens, reasoning_effort used

    Raises LLMTimeoutError, LLMNetworkError, LLMModelError, or
    LLMInvalidOutputError on failure.
    """
    # Build the messages list.
    # SYSTEM_PROMPT is empty for gpt-oss-20b per Groq docs recommendation.
    # We still include it so the code works if the model is swapped.
    messages = []
    if SYSTEM_PROMPT:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
    messages.append({"role": "user", "content": user_prompt})

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            # temperature=0.6 is the range Groq recommends for reasoning models
            # (0.5–0.7). We use 0.6 exactly as shown in their docs.
            # Note: temperature=0 can cause repetition loops in reasoning models.
            temperature=0.6,
            # max_completion_tokens caps the VISIBLE output tokens.
            # For reasoning models this is separate from the reasoning token budget.
            # The SDK uses this field name; older max_tokens is ignored by Groq
            # for these models.
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            # extra_body is forwarded verbatim to the Groq REST API.
            # We use it because groq==0.9.0 doesn't have reasoning_effort as a
            # named parameter yet — but the API accepts it.
            extra_body={
                "reasoning_effort": reasoning_effort,
            },
        )
    except APITimeoutError as exc:
        raise LLMTimeoutError(
            f"Groq did not respond within {settings.LLM_TIMEOUT_SECONDS} seconds."
        ) from exc
    except APIStatusError as exc:
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

    choice        = response.choices[0]
    finish_reason = choice.finish_reason
    content       = choice.message.content or ""
    reply_chars   = len(content)

    logger.info(
        "Groq reply | model=%s | finish_reason=%s | reply_chars=%d | "
        "max_tokens=%d | reasoning_effort=%s",
        settings.GROQ_MODEL, finish_reason, reply_chars,
        settings.LLM_MAX_TOKENS, reasoning_effort,
    )

    if not content:
        logger.warning(
            "Empty content from Groq | finish_reason=%s | reasoning_effort=%s | "
            "LLM_MAX_TOKENS=%d — consider raising LLM_MAX_TOKENS or lowering "
            "LLM_REASONING_EFFORT in .env.",
            finish_reason, reasoning_effort, settings.LLM_MAX_TOKENS,
        )
        raise LLMInvalidOutputError(
            f"Groq returned empty content (finish_reason='{finish_reason}', "
            f"reasoning_effort='{reasoning_effort}', "
            f"LLM_MAX_TOKENS={settings.LLM_MAX_TOKENS}). "
            f"Try increasing LLM_MAX_TOKENS or setting LLM_REASONING_EFFORT=low in .env."
        )

    return content


def _parse_and_validate(raw: str, attempt: int) -> AnalysisResult:
    """
    Parse a JSON string and validate it against AnalysisResult.
    Logs which specific check failed without logging user data.
    Raises on failure (caught by the retry loop).
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Attempt %d: JSON parse failed | error=%s | reply_chars=%d",
            attempt, type(exc).__name__, len(raw),
        )
        raise

    # Pre-log obvious field problems before Pydantic to get clear messages
    score = data.get("match_score")
    if score is not None and not isinstance(score, int):
        logger.warning("Attempt %d: match_score wrong type | type=%s", attempt, type(score).__name__)
    elif score is not None and not (0 <= score <= 100):
        logger.warning("Attempt %d: match_score out of range | value=%s", attempt, score)

    questions = data.get("questions")
    if isinstance(questions, list) and len(questions) != 10:
        logger.warning("Attempt %d: wrong question count | got=%d expected=10", attempt, len(questions))

    try:
        return AnalysisResult(**data)
    except ValidationError as exc:
        error_summary = "; ".join(f"{e['loc']} — {e['msg']}" for e in exc.errors())
        logger.warning("Attempt %d: Pydantic validation failed | %s", attempt, error_summary)
        raise


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

    RETRY STRATEGY:
      Attempt 1: use LLM_REASONING_EFFORT from .env (default "low")
      On empty-content (finish_reason=length): escalate to "medium" for one retry.
      Other parse/validation failures: retry with same effort.
      All retries exhausted: raise LLMInvalidOutputError.
    """
    if not settings.GROQ_API_KEY:
        raise LLMMissingKeyError(
            "GROQ_API_KEY is not set. Add it to your .env file."
        )

    jd_trimmed = jd_text[: settings.MAX_JD_CHARS]

    user_prompt = build_user_prompt(
        resume_text=resume_text,
        jd_text=jd_trimmed,
        company_name=company_name,
    )

    total_attempts = 1 + settings.LLM_MAX_RETRIES
    client         = Groq(api_key=settings.GROQ_API_KEY)
    base_effort    = settings.LLM_REASONING_EFFORT   # "low" by default

    logger.info(
        "Starting LLM analysis | model=%s | max_tokens=%d | "
        "total_attempts=%d | reasoning_effort=%s | jd_chars=%d | resume_chars=%d",
        settings.GROQ_MODEL, settings.LLM_MAX_TOKENS,
        total_attempts, base_effort, len(jd_trimmed), len(resume_text),
    )

    last_error: Exception = LLMInvalidOutputError("No attempts made.")

    for attempt in range(1, total_attempts + 1):
        # If the previous attempt returned empty content (token budget exhausted),
        # escalate reasoning effort for this retry to give more budget to the answer.
        # "low" → "medium" gives the model moderately more reasoning tokens while
        # still leaving room for the full JSON reply.
        if attempt > 1 and isinstance(last_error, LLMInvalidOutputError) and \
                "empty content" in str(last_error).lower() and base_effort == "low":
            effort = "medium"
            logger.info(
                "Attempt %d: escalating reasoning_effort low→medium "
                "because previous attempt returned empty content.",
                attempt,
            )
        else:
            effort = base_effort

        logger.info("Attempt %d of %d | reasoning_effort=%s", attempt, total_attempts, effort)

        try:
            raw = _call_groq(client, user_prompt, effort)
        except (LLMTimeoutError, LLMNetworkError, LLMModelError):
            # These are non-retryable infrastructure errors — re-raise immediately.
            raise
        except LLMInvalidOutputError as exc:
            # Empty content (finish_reason=length) from _call_groq — treat like
            # a parse failure so the retry loop and escalation logic can handle it.
            last_error = exc
            logger.warning(
                "Attempt %d _call_groq returned empty content | exception_type=%s",
                attempt, type(exc).__name__,
            )
            if attempt < total_attempts:
                logger.info("Retrying…")
                continue
            break

        try:
            result = _parse_and_validate(raw, attempt)
            logger.info("Attempt %d succeeded.", attempt)
            return result
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Attempt %d parse/validate failed | exception_type=%s",
                attempt, type(exc).__name__,
            )
            if attempt < total_attempts:
                logger.info("Retrying…")
                continue

    logger.error(
        "All %d attempt(s) failed | last_exception_type=%s | last_message=%s",
        total_attempts, type(last_error).__name__, str(last_error)[:200],
    )
    raise LLMInvalidOutputError(
        f"LLM output was invalid after {total_attempts} attempt(s): {last_error}"
    ) from last_error
