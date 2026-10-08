"""
Tests for app/dependencies/auth.py — PyJWT ES256 / JWKS verification.

CHANGES FROM PREVIOUS VERSION (python-jose → PyJWT):
  - Token creation now uses PyJWT + cryptography directly (no jose).
  - JWK dict loading uses jwt.algorithms.ECAlgorithm.from_jwk().
  - JWKS fetch failure now expects HTTP 503, not 401.
  - HS256 rejection tested via PyJWT's InvalidAlgorithmError path.

STRATEGY:
  - Generate a real EC key pair in-process (no real Supabase needed).
  - Patch _get_public_key / _fetch_jwks to avoid network calls.
  - Never print token values or secrets.
"""

import json
import time
from unittest.mock import patch

import jwt as pyjwt
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
)
from fastapi import HTTPException
from jwt.algorithms import ECAlgorithm

from app.dependencies import auth as auth_module
from app.dependencies.auth import _cache, _decode_token


# ---------------------------------------------------------------------------
# Test key pairs — generated once per module, never printed
# ---------------------------------------------------------------------------

def _generate_ec_pair():
    """
    Return (private_key_pem, public_key_object, jwk_dict_str).
    private_key_pem : bytes, for signing tokens with PyJWT
    public_key_object: cryptography public key, loaded via ECAlgorithm.from_jwk
    jwk_dict_str    : JSON string representing the JWK (for _fetch_jwks mock)
    """
    priv = ec.generate_private_key(ec.SECP256R1(), default_backend())
    pem  = priv.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    pub  = priv.public_key()

    # Build a minimal JWK dict from the public key
    # PyJWT's ECAlgorithm can also export to JWK but we build it manually
    # to stay explicit about what goes into the dict.
    from base64 import urlsafe_b64encode
    nums = pub.public_numbers()
    def i2b(n): return n.to_bytes((n.bit_length() + 7) // 8, "big").rjust(32, b"\x00")
    x_b64 = urlsafe_b64encode(i2b(nums.x)).rstrip(b"=").decode()
    y_b64 = urlsafe_b64encode(i2b(nums.y)).rstrip(b"=").decode()

    jwk_dict = {
        "kty": "EC",
        "crv": "P-256",
        "x":   x_b64,
        "y":   y_b64,
        "alg": "ES256",
        "kid": "test-kid-1",
        "use": "sig",
    }
    pub_key = ECAlgorithm.from_jwk(json.dumps(jwk_dict))
    return pem, pub_key, jwk_dict


# Module-level key pairs
_PRIV_PEM,       _PUB_KEY,       _JWK_DICT  = _generate_ec_pair()
_PRIV_PEM_OTHER, _PUB_KEY_OTHER, _          = _generate_ec_pair()

# Key maps: kid → public key object (what our cache stores)
_KEY_MAP       = {"test-kid-1": _PUB_KEY}
_KEY_MAP_OTHER = {"test-kid-1": _PUB_KEY_OTHER}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ISSUER   = "https://test-project-id.supabase.co/auth/v1"
_AUDIENCE = "authenticated"


def _make_token(
    sub: str = "user-uuid-123",
    aud: str = _AUDIENCE,
    iss: str = _ISSUER,
    exp_offset: int = 3600,
    kid: str = "test-kid-1",
    alg: str = "ES256",
    signing_pem: bytes = None,
) -> str:
    """Create a signed JWT. Never printed by callers."""
    if signing_pem is None:
        signing_pem = _PRIV_PEM
    now = int(time.time())
    payload = {"sub": sub, "aud": aud, "iss": iss, "iat": now, "exp": now + exp_offset}
    return pyjwt.encode(payload, signing_pem, algorithm=alg, headers={"kid": kid, "alg": alg})


def _patch_keys(key_map=None):
    """
    Patch _get_public_key to return from key_map without hitting the network.
    """
    if key_map is None:
        key_map = _KEY_MAP

    def fake(kid, *, allow_refetch=True):
        if kid not in key_map:
            raise KeyError(f"kid '{kid}' not found.")
        return key_map[kid]

    return patch("app.dependencies.auth._get_public_key", side_effect=fake)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_cache():
    """Clear JWKS cache before every test."""
    _cache.keys       = {}
    _cache.fetched_at = 0.0
    yield


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    monkeypatch.setattr("app.dependencies.auth.settings.SUPABASE_URL",
                        "https://test-project-id.supabase.co")
    monkeypatch.setattr("app.dependencies.auth.settings.JWKS_CACHE_TTL_SECONDS", 3600)
    monkeypatch.setattr("app.dependencies.auth.settings.USE_SYSTEM_CERTS", False)


# ---------------------------------------------------------------------------
# Test 1: valid token succeeds
# ---------------------------------------------------------------------------

def test_valid_token_returns_payload():
    """Correctly signed, unexpired token with correct aud+iss must succeed."""
    token = _make_token()
    with _patch_keys():
        payload = _decode_token(token)
    assert payload["sub"] == "user-uuid-123"
    assert payload["aud"] == _AUDIENCE
    assert payload["_token"] == token   # raw token attached for db_service


# ---------------------------------------------------------------------------
# Test 2: expired token → 401
# ---------------------------------------------------------------------------

def test_expired_token_raises_401():
    """A token whose exp is in the past must be rejected with 401."""
    token = _make_token(exp_offset=-3600)
    with _patch_keys():
        with pytest.raises(HTTPException) as exc_info:
            _decode_token(token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Test 3: wrong signature → 401
# ---------------------------------------------------------------------------

def test_wrong_signature_raises_401():
    """Token signed with a different private key must be rejected."""
    token = _make_token(signing_pem=_PRIV_PEM_OTHER)   # signed with key 2
    with _patch_keys(_KEY_MAP):                         # verified with key 1
        with pytest.raises(HTTPException) as exc_info:
            _decode_token(token)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Test 4: wrong audience → 401
# ---------------------------------------------------------------------------

def test_wrong_audience_raises_401():
    """Token with aud != 'authenticated' must be rejected."""
    token = _make_token(aud="service_role")
    with _patch_keys():
        with pytest.raises(HTTPException) as exc_info:
            _decode_token(token)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Test 5: unknown kid → 401
# ---------------------------------------------------------------------------

def test_unknown_kid_raises_401():
    """Token with a kid absent from JWKS must be rejected with 401."""
    token = _make_token(kid="unknown-kid")
    with _patch_keys(_KEY_MAP):   # only has "test-kid-1"
        with pytest.raises(HTTPException) as exc_info:
            _decode_token(token)
    assert exc_info.value.status_code == 401
    assert "unknown key" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Test 6: HS256 token → 401 (algorithm allow-list enforced)
# ---------------------------------------------------------------------------

def test_hs256_token_is_rejected():
    """
    HS256-signed token must be rejected even though it has aud/iss set.
    PyJWT raises InvalidAlgorithmError because HS256 ∉ ["ES256"].
    This proves the algorithm allow-list is enforced by the verifier,
    not by the token header.
    """
    import warnings
    now = int(time.time())
    hs_payload = {"sub": "attacker", "aud": _AUDIENCE, "iss": _ISSUER,
                  "iat": now, "exp": now + 3600}
    # Suppress PyJWT's InsecureKeyLengthWarning — key length is fine for tests
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hs_token = pyjwt.encode(hs_payload, "arbitrary-test-secret-32byteslong!!", algorithm="HS256")

    with _patch_keys():
        with pytest.raises(HTTPException) as exc_info:
            _decode_token(hs_token)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Test 7: JWKS fetch failure → 503 (not 401, not 500)
# ---------------------------------------------------------------------------

def test_jwks_fetch_failure_returns_503():
    """
    If the JWKS endpoint is unreachable, _decode_token must return 503
    (Service Unavailable), never 401 or 500.

    WHY 503 not 401?
      401 means "your token is bad." 503 means "our upstream is down."
      These are different problems. A frontend can retry a 503 silently;
      a 401 tells the user to log in again (which won't help if JWKS is down).
    """
    token = _make_token()
    with patch("app.dependencies.auth._get_public_key",
               side_effect=RuntimeError("Connection refused")):
        with pytest.raises(HTTPException) as exc_info:
            _decode_token(token)
    assert exc_info.value.status_code == 503
    assert "Connection refused" not in exc_info.value.detail   # no internals leaked


# ---------------------------------------------------------------------------
# Test 8: JWKS cache reused within TTL
# ---------------------------------------------------------------------------

def test_jwks_cache_is_used_on_second_call(monkeypatch):
    """Two consecutive calls within TTL must only fetch JWKS once."""
    monkeypatch.setattr("app.dependencies.auth.settings.JWKS_CACHE_TTL_SECONDS", 3600)
    fetch_count = {"n": 0}

    def counting_fetch():
        fetch_count["n"] += 1
        return _KEY_MAP

    token = _make_token()
    with patch("app.dependencies.auth._fetch_jwks", side_effect=counting_fetch):
        _cache.keys = {}
        _cache.fetched_at = 0.0
        _decode_token(token)
        _decode_token(token)   # second call — must use cache

    assert fetch_count["n"] == 1, "JWKS fetched more than once within TTL"


# ---------------------------------------------------------------------------
# Test 9: stale cache triggers refetch
# ---------------------------------------------------------------------------

def test_stale_cache_triggers_refetch(monkeypatch):
    """Cache older than TTL must trigger a refetch."""
    monkeypatch.setattr("app.dependencies.auth.settings.JWKS_CACHE_TTL_SECONDS", 1)
    fetch_count = {"n": 0}

    def counting_fetch():
        fetch_count["n"] += 1
        return _KEY_MAP

    token = _make_token()
    with patch("app.dependencies.auth._fetch_jwks", side_effect=counting_fetch):
        _cache.keys       = _KEY_MAP
        _cache.fetched_at = time.monotonic() - 10   # older than 1 s TTL
        _decode_token(token)

    assert fetch_count["n"] == 1, "Stale cache did not trigger a refetch"


# ---------------------------------------------------------------------------
# Test 10: get_optional_user returns None (not 503) when JWKS is down
# ---------------------------------------------------------------------------

def test_get_optional_user_returns_none_when_jwks_unavailable():
    """
    get_optional_user must return None when the JWKS endpoint is unreachable,
    NOT propagate a 503.  This allows POST /analyze to continue and return
    the analysis result as unauthenticated (DB save skipped).

    Only get_current_user (used by GET /analyses) should propagate 503.
    """
    from fastapi import HTTPException, status as http_status
    from app.dependencies.auth import get_optional_user

    # Patch _decode_token to raise the 503 that JWKS failure produces
    with patch(
        "app.dependencies.auth._decode_token",
        side_effect=HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        ),
    ):
        from fastapi.security import HTTPAuthorizationCredentials
        # Simulate a credential being present (token in header)
        fake_creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="fake.token.value"
        )
        result = get_optional_user(credentials=fake_creds)

    # Must return None, not raise 503
    assert result is None


def test_get_current_user_propagates_503_when_jwks_unavailable():
    """
    get_current_user must propagate 503 when JWKS is down — history is
    personal data and we cannot skip authentication for it.
    """
    from fastapi import HTTPException, status as http_status
    from app.dependencies.auth import get_current_user

    with patch(
        "app.dependencies.auth._decode_token",
        side_effect=HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        ),
    ):
        from fastapi.security import HTTPAuthorizationCredentials
        fake_creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="fake.token.value"
        )
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=fake_creds)

    assert exc_info.value.status_code == 503
