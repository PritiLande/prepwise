"""
JWT authentication dependencies — ES256 / JWKS implementation.
Uses PyJWT (not python-jose, which has unpatched CVEs through 3.3.0).

WHY PyJWT instead of python-jose?
  python-jose 3.3.0 has three unfixed CVEs:
    - CVE-2024-33663 (High): algorithm confusion with EC keys — directly in
      our ES256 verification path.
    - CVE-2024-33664 (Medium): JWE JWT bomb DoS.
    - CVE-2025-61152 (High): alg=none bypass (only when verify=False, but
      the library is unmaintained and no patch exists for any of these).
  PyJWT 2.13.0+ fixed analogous algorithm-confusion vulnerabilities and is
  actively maintained.  PyJWT 2.15.1 is already installed as a supabase
  dependency and supports Python 3.14.

HOW SUPABASE AUTH WORKS:
  1. User logs in via the frontend Supabase JS client.
  2. Supabase signs a JWT with its private EC key (ES256, alg in JWKS).
  3. Frontend sends the token as: Authorization: Bearer <token>
  4. Our backend fetches the EC public key from Supabase's JWKS endpoint,
     verifies the signature, and extracts the user's UUID.
  5. The raw token is kept in the returned dict so db_service can call
     postgrest.auth(token) to satisfy RLS policies.

SECURITY DESIGN:
  - Algorithm ALLOW-LIST ["ES256"] only.  The token header is NEVER trusted
    to choose the algorithm — alg=none or alg=HS256 in the header is ignored.
  - Keys are loaded by "kid" (key ID) from the JWKS.  We never use a key
    without matching it to the kid in the token header.
  - Audience "authenticated" and issuer "<SUPABASE_URL>/auth/v1" are both
    verified.  A token from a different project fails here.
  - JWKS is cached in memory for JWKS_CACHE_TTL_SECONDS (default 3600 s).
    On a cache miss: refetch once, then reject.  Handles key rotation.
  - If the JWKS endpoint is unreachable: return 503 (Service Unavailable).
    An invalid/expired token returns 401.  We never accept an unverified token.
  - truststore is respected: if USE_SYSTEM_CERTS is true, we patch SSL
    before fetching JWKS so Avast / corporate proxies don't break the fetch.

JWT_SECRET:
  Removed from config.py and both .env.example files. This project uses
  ES256 asymmetric signing via JWKS — a shared secret is not needed.
"""

import json
import logging
import ssl
import time
import urllib.request
from dataclasses import dataclass, field

import jwt as pyjwt
from jwt.algorithms import ECAlgorithm
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------

@dataclass
class _JwksCache:
    """
    In-memory store for the JWKS public keys.

    keys      : dict mapping kid (str) → cryptography public key object
    fetched_at: monotonic timestamp of last successful fetch (0 = never)

    WHY a module-level cache?
      The JWKS endpoint is public but we don't want to call it on every
      request.  We cache for JWKS_CACHE_TTL_SECONDS (default 3600 s).
    """
    keys: dict        = field(default_factory=dict)
    fetched_at: float = 0.0


_cache = _JwksCache()


def _jwks_url() -> str:
    return settings.SUPABASE_URL.rstrip("/") + "/auth/v1/.well-known/jwks.json"


def _expected_issuer() -> str:
    return settings.SUPABASE_URL.rstrip("/") + "/auth/v1"


def _make_ssl_context() -> ssl.SSLContext:
    """
    Return an SSL context for the JWKS fetch.
    If USE_SYSTEM_CERTS is true, truststore patches the OS certificate store
    so Avast / corporate proxies don't block the HTTPS request.
    """
    if settings.USE_SYSTEM_CERTS:
        try:
            import truststore
            truststore.inject_into_ssl()
        except Exception:
            pass   # truststore not installed; fall through to default
    return ssl.create_default_context()


def _fetch_jwks() -> dict:
    """
    Fetch the JWKS from Supabase and return a {kid: public_key} dict.
    Keys are loaded with PyJWT's ECAlgorithm.from_jwk().
    Raises RuntimeError on any network or parse failure.
    Never logs secrets.
    """
    url = _jwks_url()
    ctx = _make_ssl_context()
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        raise RuntimeError(
            f"JWKS fetch failed ({type(exc).__name__}): {exc}"
        ) from exc

    raw_keys = data.get("keys", [])
    if not raw_keys:
        raise RuntimeError("JWKS endpoint returned an empty keys array.")

    result = {}
    for raw in raw_keys:
        kid = raw.get("kid")
        alg = raw.get("alg", "")
        if alg not in ("ES256",):
            # Skip any key not in our algorithm allow-list.
            logger.warning("JWKS: skipping key kid=%s with unsupported alg=%s", kid, alg)
            continue
        try:
            # ECAlgorithm.from_jwk expects a JSON string, not a dict.
            result[kid] = ECAlgorithm.from_jwk(json.dumps(raw))
        except Exception as exc:
            logger.warning(
                "JWKS: could not load key kid=%s | %s", kid, type(exc).__name__
            )

    if not result:
        raise RuntimeError("JWKS contains no usable ES256 keys.")

    return result


def _get_public_key(kid: str, *, allow_refetch: bool = True):
    """
    Return the public key object for the given kid.

    1. Fresh cache + kid present → return immediately.
    2. Cache stale OR kid missing → refetch once.
    3. kid still missing after refetch → raise KeyError.
    4. Fetch fails → raise RuntimeError (caller converts to 503).
    """
    now        = time.monotonic()
    cache_stale = (now - _cache.fetched_at) > settings.JWKS_CACHE_TTL_SECONDS

    if not cache_stale and kid in _cache.keys:
        return _cache.keys[kid]

    if allow_refetch or cache_stale:
        logger.info(
            "JWKS: fetching keys (cache_stale=%s, kid_missing=%s)",
            cache_stale, kid not in _cache.keys,
        )
        new_keys          = _fetch_jwks()   # raises RuntimeError on failure
        _cache.keys       = new_keys
        _cache.fetched_at = now

        if kid in _cache.keys:
            return _cache.keys[kid]

    raise KeyError(f"kid '{kid}' not found in JWKS.")


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

_ALLOWED_ALGORITHMS = ["ES256"]
_EXPECTED_AUDIENCE  = "authenticated"


def _decode_token(token: str) -> dict:
    """
    Verify an ES256 JWT issued by Supabase and return the payload.

    Steps:
      1. Read the kid from the unverified header (we ignore the alg claim).
      2. Look up the EC public key for that kid.
         → 503 if JWKS is unreachable
         → 401 if kid is unknown
      3. Verify signature, expiry, audience, issuer with algorithms=["ES256"].
         PyJWT raises InvalidAlgorithmError if the token alg != ES256.
         → 401 for any failure
      4. Attach "_token" (raw JWT) to the payload for db_service.

    Never logs the token value or any secret.
    """
    # Step 1 — read kid from header (not trusted for algorithm choice)
    try:
        header = pyjwt.get_unverified_header(token)
    except pyjwt.exceptions.DecodeError as exc:
        logger.warning("Token header parse failed: %s", type(exc).__name__)
        _raise_401("Token format is invalid.")

    kid = header.get("kid")
    if not kid:
        logger.warning("Token has no kid in header.")
        _raise_401("Token is missing key ID.")

    # Step 2 — fetch key by kid
    try:
        public_key = _get_public_key(kid)
    except RuntimeError as exc:
        # JWKS endpoint unreachable → 503, not 401.
        # The token may be perfectly valid; the problem is on our side.
        logger.error("JWKS unavailable: %s", str(exc)[:120])
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable. Please try again.",
        )
    except KeyError:
        logger.warning("Unknown kid in token: %s", kid[:20])
        _raise_401("Token signed with unknown key.")

    # Step 3 — full cryptographic verification
    try:
        payload = pyjwt.decode(
            token,
            public_key,
            # WE choose the algorithm — never derived from the token header.
            # PyJWT raises InvalidAlgorithmError if the token's alg header
            # doesn't match this list, so HS256/none tokens are rejected here.
            algorithms=_ALLOWED_ALGORITHMS,
            audience=_EXPECTED_AUDIENCE,
            issuer=_expected_issuer(),
        )
    except pyjwt.exceptions.ExpiredSignatureError:
        logger.info("Rejected expired token.")
        _raise_401("Token has expired. Please log in again.")
    except pyjwt.exceptions.InvalidAudienceError:
        logger.warning("Token audience mismatch.")
        _raise_401("Token claims are invalid.")
    except pyjwt.exceptions.InvalidIssuerError:
        logger.warning("Token issuer mismatch.")
        _raise_401("Token claims are invalid.")
    except pyjwt.exceptions.InvalidAlgorithmError:
        # Catches HS256, alg=none, and any other non-ES256 token.
        logger.warning("Token uses disallowed algorithm.")
        _raise_401("Token uses a disallowed signing algorithm.")
    except pyjwt.exceptions.PyJWTError as exc:
        logger.warning("Token verification failed: %s", type(exc).__name__)
        _raise_401("Token signature is invalid.")

    # Step 4 — attach raw token for db_service (never logged)
    payload["_token"] = token
    return payload


def _raise_401(detail: str):
    """Raise a 401 HTTPException. Extracted to keep _decode_token readable."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------------------
# FastAPI dependency functions
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """
    REQUIRED authentication dependency.
    Raises 401 if header is missing or token is invalid.
    Raises 503 if the JWKS endpoint is unreachable.
    Returns the verified payload dict with "_token" added.
    """
    if credentials is None:
        _raise_401("Authentication required. Please include a Bearer token.")
    return _decode_token(credentials.credentials)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict | None:
    """
    OPTIONAL authentication dependency.
    Returns verified payload (with "_token") if a valid token is present
    AND the JWKS endpoint is reachable.
    Returns None in these cases (route continues unauthenticated):
      - No Authorization header provided.
      - JWKS endpoint is unreachable (503 situation) — the route still
        returns its result; the DB save is just skipped.  The user should
        not lose their analysis because our auth service is temporarily down.
    Raises 401 if a token IS provided but is cryptographically invalid
    (bad signature, expired, wrong audience, etc.).
    """
    if credentials is None:
        return None
    try:
        return _decode_token(credentials.credentials)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            # JWKS is down.  Treat as unauthenticated — skip DB save,
            # but do NOT block the analysis result.
            logger.warning(
                "JWKS unavailable during optional auth — proceeding as unauthenticated."
            )
            return None
        # Re-raise 401 (invalid token) — a bad token is always rejected.
        raise
