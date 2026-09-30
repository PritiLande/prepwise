from app.core.config import settings

# truststore must be patched before any SSL connection is opened.
# It must also be before any other app import that might trigger groq/httpx.
if settings.USE_SYSTEM_CERTS:
    import truststore
    truststore.inject_into_ssl()

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.limiter import limiter
from app.api.routes.health import router as health_router
from app.api.routes.resume import router as resume_router
from app.api.routes.analyze import router as analyze_router

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# Attach the limiter to app.state so slowapi can find it from any route.
app.state.limiter = limiter

# When a request exceeds the rate limit, slowapi raises RateLimitExceeded.
# This handler converts it to a clean JSON 429 response.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health_router)
app.include_router(resume_router)
app.include_router(analyze_router)
