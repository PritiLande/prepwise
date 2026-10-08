"""
Tests for app/services/llm_service.py.

STRATEGY — mock, don't call
  Every test patches _call_groq (the single function that actually talks to
  Groq) with unittest.mock.patch.  This means:
    - No real HTTP requests, so the tests pass without a GROQ_API_KEY.
    - No cost.
    - Tests run in milliseconds.
    - We fully control what the "LLM" replies with.

  We patch at the llm_service module level ('app.services.llm_service._call_groq')
  because that is where the name is used, not where it is defined.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.llm_service import (
    LLMInvalidOutputError,
    LLMMissingKeyError,
    LLMModelError,
    LLMTimeoutError,
    analyze,
)

# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

RESUME = "Jane Doe\nSkills: Python, FastAPI, Docker\nExperience: 2 years backend dev"
JD     = "We need a backend engineer with Python, FastAPI, Kubernetes, and AWS."
CO     = "Acme Corp"

# A valid JSON string that matches AnalysisResult exactly.
# We define it once so every "happy path" test reuses the same fixture.
VALID_REPLY = json.dumps({
    "match_score": 72,
    "matched_skills": ["Python", "FastAPI"],
    "skill_gaps": [
        {"skill": "Kubernetes", "tip": "Complete the official Kubernetes basics tutorial."},
        {"skill": "AWS",        "tip": "Earn the AWS Cloud Practitioner certification."},
    ],
    "resume_wording_tips": [
        "Add 'pytest' to your skills section — your resume mentions 33 automated tests."
    ],
    "questions": [
        {
            "question": f"Q{i}?",
            "category": "technical",
            # Each outline is ≥80 chars to satisfy the answer_outline validator.
            "answer_outline": (
                f"This question covers topic {i} from the candidate's resume. "
                f"In the relevant project, Python and FastAPI were used to build the backend service."
            ),
        }
        for i in range(1, 11)
    ],
})


# ---------------------------------------------------------------------------
# Helper — override GROQ_API_KEY for tests that need it set
# ---------------------------------------------------------------------------

def _with_key(monkeypatch):
    """Patch settings so GROQ_API_KEY looks like it is set."""
    monkeypatch.setattr("app.services.llm_service.settings.GROQ_API_KEY", "test-key")


# ---------------------------------------------------------------------------
# Test 1: valid JSON on first attempt
# ---------------------------------------------------------------------------

def test_analyze_valid_json(monkeypatch):
    """analyze() returns an AnalysisResult when the LLM replies with valid JSON."""
    _with_key(monkeypatch)

    with patch("app.services.llm_service._call_groq", return_value=VALID_REPLY):
        result = analyze(RESUME, JD, CO)

    assert result.match_score == 72
    assert "Python" in result.matched_skills
    assert len(result.questions) == 10


# ---------------------------------------------------------------------------
# Test 2: invalid JSON first, valid on retry
# ---------------------------------------------------------------------------

def test_analyze_retries_on_bad_json(monkeypatch):
    """
    If the first reply is garbage, analyze() retries and succeeds on
    the second attempt.
    """
    _with_key(monkeypatch)
    # side_effect is a list: first call returns bad JSON, second returns good JSON
    with patch(
        "app.services.llm_service._call_groq",
        side_effect=["not valid json <<<", VALID_REPLY],
    ):
        result = analyze(RESUME, JD, CO)

    assert result.match_score == 72


# ---------------------------------------------------------------------------
# Test 3: always invalid — raises LLMInvalidOutputError after all retries
# ---------------------------------------------------------------------------

def test_analyze_raises_after_all_retries(monkeypatch):
    """
    If every attempt returns bad output, analyze() raises LLMInvalidOutputError.
    LLM_MAX_RETRIES defaults to 2, so we expect 3 total calls (1 + 2 retries).
    """
    _with_key(monkeypatch)
    # Patch MAX_RETRIES to 2 (the default) explicitly so the test is self-documenting
    monkeypatch.setattr("app.services.llm_service.settings.LLM_MAX_RETRIES", 2)

    mock_call = MagicMock(return_value="still not json")
    with patch("app.services.llm_service._call_groq", mock_call):
        with pytest.raises(LLMInvalidOutputError):
            analyze(RESUME, JD, CO)

    # 1 first attempt + 2 retries = 3 total calls
    assert mock_call.call_count == 3


# ---------------------------------------------------------------------------
# Test 4: timeout propagates
# ---------------------------------------------------------------------------

def test_analyze_raises_on_timeout(monkeypatch):
    """A timeout from _call_groq must propagate out of analyze() unchanged."""
    _with_key(monkeypatch)

    with patch(
        "app.services.llm_service._call_groq",
        side_effect=LLMTimeoutError("timed out"),
    ):
        with pytest.raises(LLMTimeoutError):
            analyze(RESUME, JD, CO)


# ---------------------------------------------------------------------------
# Test 5: missing API key
# ---------------------------------------------------------------------------

def test_analyze_raises_when_key_missing(monkeypatch):
    """analyze() must raise LLMMissingKeyError immediately if the key is blank."""
    monkeypatch.setattr("app.services.llm_service.settings.GROQ_API_KEY", "")

    with pytest.raises(LLMMissingKeyError):
        analyze(RESUME, JD, CO)


# ---------------------------------------------------------------------------
# Test 6: score outside 0-100 triggers retry → eventually raises
# ---------------------------------------------------------------------------

def test_analyze_rejects_invalid_score(monkeypatch):
    """
    A match_score of 150 fails Pydantic validation (ge=0, le=100).
    analyze() should retry and eventually raise LLMInvalidOutputError.
    """
    _with_key(monkeypatch)
    monkeypatch.setattr("app.services.llm_service.settings.LLM_MAX_RETRIES", 0)

    bad_score_reply = json.dumps({
        **json.loads(VALID_REPLY),
        "match_score": 150,   # out of range
    })

    with patch("app.services.llm_service._call_groq", return_value=bad_score_reply):
        with pytest.raises(LLMInvalidOutputError):
            analyze(RESUME, JD, CO)


# ---------------------------------------------------------------------------
# Test 7: fewer than 10 questions triggers retry → eventually raises
# ---------------------------------------------------------------------------

def test_analyze_rejects_fewer_than_10_questions(monkeypatch):
    """
    Our validator requires exactly 10 questions.
    A reply with 9 must fail validation and eventually raise LLMInvalidOutputError.
    """
    _with_key(monkeypatch)
    monkeypatch.setattr("app.services.llm_service.settings.LLM_MAX_RETRIES", 0)

    nine_q_reply = json.dumps({
        **json.loads(VALID_REPLY),
        "questions": [
            {
                "question": f"Q{i}?",
                "category": "technical",
                "answer_outline": (
                    f"This is question {i} about the candidate's Python experience. "
                    f"They built a FastAPI service with PostgreSQL in their backend project."
                ),
            }
            for i in range(1, 10)   # only 9
        ],
    })

    with patch("app.services.llm_service._call_groq", return_value=nine_q_reply):
        with pytest.raises(LLMInvalidOutputError):
            analyze(RESUME, JD, CO)


# ---------------------------------------------------------------------------
# Test 8: decommissioned model raises LLMModelError with helpful message
# ---------------------------------------------------------------------------

def test_analyze_raises_model_error_on_decommissioned_model(monkeypatch):
    """
    When Groq returns a 400 'model_decommissioned' error, _call_groq must
    raise LLMModelError (not LLMNetworkError).  The message must name the
    model and point to the docs — but must NOT contain the API key or any
    resume text.
    """
    import groq as groq_module

    _with_key(monkeypatch)
    # Tell the service we are using a known-bad model name
    monkeypatch.setattr(
        "app.services.llm_service.settings.GROQ_MODEL", "llama3-8b-8192"
    )

    # Build a fake APIStatusError that looks like Groq's real decommission reply.
    # APIStatusError needs a response object; we use a MagicMock for that.
    fake_response = MagicMock()
    fake_response.status_code = 400
    fake_status_error = groq_module.APIStatusError(
        message="The model `llama3-8b-8192` has been decommissioned",
        response=fake_response,
        body={"error": {"code": "model_decommissioned"}},
    )

    # We mock the Groq client's completions.create method so _call_groq
    # actually runs (and its except APIStatusError branch fires), but no
    # real HTTP request is made.
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = fake_status_error

    with patch("app.services.llm_service.Groq", return_value=mock_client):
        with pytest.raises(LLMModelError) as exc_info:
            analyze(RESUME, JD, CO)

    error_message = str(exc_info.value)
    # Must name the model so the user knows what to change
    assert "llama3-8b-8192" in error_message
    # Must tell the user where to look
    assert ".env" in error_message
    # Must never leak the API key
    assert "test-key" not in error_message
    # Must never leak resume content
    assert "Jane Doe" not in error_message


# ---------------------------------------------------------------------------
# Test 9: resume_wording_tips is returned and accessible
# ---------------------------------------------------------------------------

def test_analyze_returns_wording_tips(monkeypatch):
    """
    When the LLM includes resume_wording_tips, the field must be present on
    the AnalysisResult and contain the expected strings.
    """
    _with_key(monkeypatch)

    with patch("app.services.llm_service._call_groq", return_value=VALID_REPLY):
        result = analyze(RESUME, JD, CO)

    assert isinstance(result.resume_wording_tips, list)
    assert len(result.resume_wording_tips) == 1
    assert "pytest" in result.resume_wording_tips[0]


# ---------------------------------------------------------------------------
# Test 10: resume_wording_tips defaults to empty list when omitted
# ---------------------------------------------------------------------------

def test_analyze_wording_tips_defaults_to_empty(monkeypatch):
    """
    resume_wording_tips is optional — if the LLM omits it, Pydantic must
    default it to an empty list rather than raising a ValidationError.
    """
    _with_key(monkeypatch)

    # Build a reply that does NOT include resume_wording_tips
    reply_without_tips = json.dumps({
        "match_score": 60,
        "matched_skills": ["Python"],
        "skill_gaps": [
            {"skill": "Docker", "tip": "Complete the Docker getting-started tutorial."},
        ],
        # resume_wording_tips intentionally absent
        "questions": [
            {
                "question": f"Q{i}?",
                "category": "technical",
                "answer_outline": (
                    f"This is question {i} about the candidate's Python experience. "
                    f"They built a FastAPI service with PostgreSQL in their backend project."
                ),
            }
            for i in range(1, 11)
        ],
    })

    with patch("app.services.llm_service._call_groq", return_value=reply_without_tips):
        result = analyze(RESUME, JD, CO)

    # Must not raise — must default to empty list
    assert result.resume_wording_tips == []


# ---------------------------------------------------------------------------
# Tests for empty-content / finish_reason=length handling
# ---------------------------------------------------------------------------

def test_analyze_raises_on_empty_content_after_all_retries(monkeypatch):
    """
    When Groq returns empty content every time (finish_reason=length),
    analyze() must raise LLMInvalidOutputError after all retries.
    """
    _with_key(monkeypatch)
    monkeypatch.setattr("app.services.llm_service.settings.LLM_MAX_RETRIES", 1)
    monkeypatch.setattr("app.services.llm_service.settings.LLM_REASONING_EFFORT", "low")

    # _call_groq raises LLMInvalidOutputError when content is empty
    mock_call = MagicMock(
        side_effect=LLMInvalidOutputError(
            "Groq returned empty content (finish_reason='length')"
        )
    )
    with patch("app.services.llm_service._call_groq", mock_call):
        with pytest.raises(LLMInvalidOutputError) as exc_info:
            analyze(RESUME, JD, CO)

    # The error message must name finish_reason so the operator knows what happened
    assert "empty content" in str(exc_info.value).lower() or \
           "invalid" in str(exc_info.value).lower()


def test_analyze_escalates_reasoning_effort_on_empty_content(monkeypatch):
    """
    When the first attempt returns empty content (finish_reason=length),
    analyze() must retry with reasoning_effort="medium" instead of "low".

    We verify this by inspecting the effort argument passed to _call_groq
    on the second call.
    """
    _with_key(monkeypatch)
    monkeypatch.setattr("app.services.llm_service.settings.LLM_MAX_RETRIES", 1)
    monkeypatch.setattr("app.services.llm_service.settings.LLM_REASONING_EFFORT", "low")

    # First call: raises empty-content error. Second call: returns valid JSON.
    call_efforts = []

    def fake_call_groq(client, user_prompt, reasoning_effort):
        call_efforts.append(reasoning_effort)
        if len(call_efforts) == 1:
            raise LLMInvalidOutputError(
                "Groq returned empty content (finish_reason='length')"
            )
        return VALID_REPLY

    with patch("app.services.llm_service._call_groq", side_effect=fake_call_groq):
        result = analyze(RESUME, JD, CO)

    assert result.match_score == 72
    assert call_efforts[0] == "low"    # first attempt uses configured effort
    assert call_efforts[1] == "medium" # retry escalates


def test_analyze_reasoning_effort_passed_to_call_groq(monkeypatch):
    """
    The reasoning_effort from settings must be forwarded to _call_groq
    on the first attempt.
    """
    _with_key(monkeypatch)
    monkeypatch.setattr("app.services.llm_service.settings.LLM_REASONING_EFFORT", "high")

    captured = []

    def fake_call_groq(client, user_prompt, reasoning_effort):
        captured.append(reasoning_effort)
        return VALID_REPLY

    with patch("app.services.llm_service._call_groq", side_effect=fake_call_groq):
        analyze(RESUME, JD, CO)

    assert captured[0] == "high"


# ---------------------------------------------------------------------------
# Tests for answer_outline length validator
# ---------------------------------------------------------------------------

def test_analyze_rejects_short_answer_outlines(monkeypatch):
    """
    If the LLM returns questions with answer_outlines shorter than 80 chars,
    Pydantic validation must fail and the retry loop must eventually raise
    LLMInvalidOutputError.
    """
    _with_key(monkeypatch)
    monkeypatch.setattr("app.services.llm_service.settings.LLM_MAX_RETRIES", 0)

    short_outline_reply = json.dumps({
        "match_score": 65,
        "matched_skills": ["Python"],
        "skill_gaps": [{"skill": "Docker", "tip": "Learn Docker basics."}],
        "resume_wording_tips": [],
        "questions": [
            # "Too short." is 10 chars — well below the 80-char minimum
            {"question": f"Q{i}?", "category": "technical", "answer_outline": "Too short."}
            for i in range(1, 11)
        ],
    })

    with patch("app.services.llm_service._call_groq", return_value=short_outline_reply):
        with pytest.raises(LLMInvalidOutputError):
            analyze(RESUME, JD, CO)


def test_analyze_accepts_long_enough_answer_outlines(monkeypatch):
    """
    Questions with answer_outlines of 80+ chars must pass validation.
    """
    _with_key(monkeypatch)

    # VALID_REPLY already has long outlines — reuse it
    with patch("app.services.llm_service._call_groq", return_value=VALID_REPLY):
        result = analyze(RESUME, JD, CO)

    # All 10 outlines must be present and long enough
    for q in result.questions:
        assert len(q.answer_outline.strip()) >= 80, (
            f"answer_outline too short: {len(q.answer_outline)} chars"
        )
