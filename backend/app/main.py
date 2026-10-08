from app.core.config import settings

# truststore must be patched before any SSL connection is opened.
if settings.USE_SYSTEM_CERTS:
    import truststore
    truststore.inject_into_ssl()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.limiter import limiter
from app.api.routes.health import router as health_router
from app.api.routes.resume import router as resume_router
from app.api.routes.analyze import router as analyze_router
from app.api.routes.history import router as history_router

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# WHY: Browsers enforce the Same-Origin Policy — a page served from
# http://localhost:5173 (Vite) is NOT allowed to fetch from
# http://localhost:8000 (FastAPI) unless the server sends back an
# "Access-Control-Allow-Origin" header that matches.
# CORSMiddleware adds that header automatically for every listed origin.
# We split the comma-separated string from .env into a list.
_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,       # only the explicitly listed origins
    allow_credentials=True,       # allow cookies/auth headers (needed later for JWT)
    allow_methods=["*"],          # GET, POST, etc.
    allow_headers=["*"],          # Content-Type, Authorization, etc.
)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health_router)
app.include_router(resume_router)
app.include_router(analyze_router)
app.include_router(history_router)
