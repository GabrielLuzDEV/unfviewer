"""FastAPI application — Instagram Non-Follower Finder backend."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger(__name__)

# ── Secrets guard ─────────────────────────────────────────────────────────────
_secret_key = os.environ.get("SECRET_KEY", "")
if _secret_key in ("", "change-me-in-production"):
    if os.environ.get("ENVIRONMENT", "development") == "production":
        raise RuntimeError(
            "SECRET_KEY must be set to a random value before starting in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    log.warning("Running with default dev SECRET_KEY — do NOT use in production")

# Make the repo root importable so routes can reach config.py, core_live.py, etc.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.middleware.rate_limit import limiter
from backend.routes.auth import router as auth_router
from backend.routes.export import router as export_router
from backend.routes.followers import router as followers_router
from backend.routes.unfollow import router as unfollow_router
from backend.session_store import _evict_expired


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_eviction_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def _eviction_loop():
    while True:
        await asyncio.sleep(300)
        _evict_expired()


app = FastAPI(
    title="Instagram Non-Follower Finder API",
    description="Backend for unfviewer — free & premium tiers",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
_allowed_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# ── Security headers ──────────────────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if os.environ.get("COOKIE_SECURE", "false").lower() == "true":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' https://instagram.com https://*.cdninstagram.com; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'"
    )
    return response

app.include_router(auth_router)
app.include_router(export_router)
app.include_router(followers_router)
app.include_router(unfollow_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
