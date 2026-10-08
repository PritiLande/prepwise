"""
Supabase client factory.

WHY a function instead of a module-level singleton?
  A module-level client is created once when Python imports this file.
  That means tests cannot swap it out easily.
  A function lets FastAPI's Depends() create one per request, and lets
  tests override it by replacing the dependency — no monkey-patching needed.

WHY return None instead of raising on failure?
  get_supabase() is called by FastAPI's dependency injection system BEFORE
  the route function runs.  If it raises, FastAPI converts it to a 500
  immediately — the route never gets a chance to catch it and still return
  the analysis result.
  By returning None on failure, we let the route decide what to do:
  skip the DB save and return the result anyway.
"""

import logging

from supabase import Client, create_client

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_supabase() -> Client | None:
    """
    Return a Supabase client configured from .env settings.
    Called once per request via FastAPI's Depends().

    Returns None (instead of raising) if the client cannot be created —
    for example when SUPABASE_URL or SUPABASE_KEY is blank or invalid.
    The route will skip the DB save and still return the analysis result.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        # Keys not configured — skip silently, don't crash the request.
        return None
    try:
        return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    except Exception as exc:
        # Log the ERROR TYPE only — never the key value itself.
        logger.error(
            "Supabase client creation failed (%s: %s). "
            "DB save will be skipped for this request.",
            type(exc).__name__,
            # exc message may contain partial key info from the SDK;
            # we log only the first 80 chars to limit exposure.
            str(exc)[:80],
        )
        return None
