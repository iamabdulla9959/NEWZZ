import asyncio
import logging
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger("newzz.api")

# Ensure repository root is on sys.path for packages.* imports
_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.db import engine, get_db
from app.models import Base, IngestionRequest
from app.coordination import (
    check_trigger_rate_limit_and_concurrency,
    create_ingestion_request,
    atomic_create_ingestion_request_if_allowed,
)
from sqlalchemy.orm import Session
from app.models import Base
from app.routers.admin import router as admin_router
from app.routers.feed import router as feed_router
from app.routers.location import router as location_router


async def _render_self_keepalive():
    """Background task inside FastAPI to ping itself via public Render URL every 13.5 minutes (810s),
    ensuring inbound traffic hits Render's reverse proxy and prevents container spin-down."""
    import asyncio
    import os
    import sys
    import urllib.request

    if "pytest" in sys.modules or os.getenv("TESTING") == "1":
        return

    keepalive_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("RENDER_KEEP_ALIVE_URL") or "https://newzz-5e19.onrender.com"
    target = f"{keepalive_url.rstrip('/')}/health"

    # Wait 10s after startup before first ping & initial crawl
    await asyncio.sleep(10)
    try:
        from scripts.ingest_real_live_news import fetch_and_build_live_feed
        logger.info("[SelfKeepAlive] Initiating startup live news crawl...")
        await asyncio.to_thread(fetch_and_build_live_feed, target_state=None, max_per_feed=15)
    except Exception as exc:
        logger.warning("[SelfKeepAlive] Startup live ingest notice: %s", exc)

    while True:
        try:
            def _ping():
                req = urllib.request.Request(target, headers={"User-Agent": "NEWZZ-SelfKeepAlive/1.0"})
                with urllib.request.urlopen(req, timeout=15) as res:
                    return res.status
            status = await asyncio.to_thread(_ping)
            logger.info("[SelfKeepAlive] Keepalive ping -> %s returned %s", target, status)

            # Automatically refresh live news in background right before 14min sleep threshold
            from scripts.ingest_real_live_news import fetch_and_build_live_feed
            await asyncio.to_thread(fetch_and_build_live_feed, target_state=None, max_per_feed=10)
        except Exception as exc:
            logger.debug("[SelfKeepAlive] Keepalive ping notice for %s: %s", target, exc)
        await asyncio.sleep(810)  # 13.5 minutes (safely before Render's 15-minute sleep threshold)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Production schema is authoritatively managed by Alembic migrations (start.sh).
    # Skip create_all() in production to eliminate redundant startup DDL network latency.
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logger.warning("Table initialization notice: %s", exc)
    
    keepalive_task = asyncio.create_task(_render_self_keepalive())
    try:
        yield
    finally:
        if keepalive_task:
            keepalive_task.cancel()


app = FastAPI(title="NEWZZ API", version="0.1.0", lifespan=lifespan)

_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(feed_router)
app.include_router(admin_router)
app.include_router(location_router)



_ingestion_lock = threading.Lock()
_ingestion_running = False
_last_trigger_time: float = 0.0
TRIGGER_COOLDOWN_SECONDS: float = 10.0


def require_ingestion_auth(
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
) -> str:
    """Verifies administrative credentials with fail-closed security and constant-time comparison."""
    import secrets
    admin_key = (settings.admin_api_key or "").strip()
    internal_key = (getattr(settings, "internal_ingestion_key", "") or "").strip()
    is_prod = (settings.app_env or "").lower() == "production"

    if is_prod and (not admin_key or admin_key == "change-me-local-only"):
        logger.error("Administrative crawl trigger blocked: admin_api_key unconfigured or default in production")
        raise HTTPException(
            status_code=403,
            detail="Administrative trigger disabled: secure admin key not configured",
        )

    if not admin_key and not internal_key:
        raise HTTPException(
            status_code=403,
            detail="Administrative trigger disabled: secure admin key not configured",
        )

    token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
        else:
            token = authorization.strip()
    elif x_admin_key:
        token = x_admin_key.strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Administrative credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    is_admin_valid = bool(admin_key and secrets.compare_digest(token, admin_key))
    is_internal_valid = bool(internal_key and secrets.compare_digest(token, internal_key))

    if not (is_admin_valid or is_internal_valid):
        raise HTTPException(
            status_code=403,
            detail="Invalid administrative credentials",
        )

    return token


@app.api_route("/crawl/trigger", methods=["POST", "GET"])
def trigger_crawl(
    auth_token: str = Depends(require_ingestion_auth),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    cooldown = getattr(settings, "crawl_cooldown_seconds", 10)
    req, reason, remaining = atomic_create_ingestion_request_if_allowed(
        db, cooldown_seconds=cooldown, trigger_origin="manual_api"
    )
    if not req:
        if reason == "concurrency_busy":
            raise HTTPException(
                status_code=409,
                detail="Ingestion job is already running",
            )
        if reason == "rate_limited":
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: trigger cooling down ({remaining}s remaining)",
            )
        raise HTTPException(
            status_code=409,
            detail="Ingestion job is already running",
        )

    return {
        "status": "pending",
        "request_id": req.id,
        "message": "Ingestion request queued for worker execution",
    }


@app.get("/crawl/status/{request_id}")
def get_crawl_status(
    request_id: str,
    auth_token: str = Depends(require_ingestion_auth),
    db: Session = Depends(get_db),
) -> dict:
    req = db.query(IngestionRequest).filter(IngestionRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Ingestion request not found")
    return {
        "request_id": req.id,
        "status": req.status,
        "trigger_origin": req.trigger_origin,
        "worker_id": req.worker_id,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "started_at": req.started_at.isoformat() if req.started_at else None,
        "completed_at": req.completed_at.isoformat() if req.completed_at else None,
        "error_message": req.error_message,
        "result_summary": req.result_summary,
    }

@app.api_route("/feed/refresh", methods=["POST", "GET"])
def refresh_live_feed(
    background_tasks: BackgroundTasks,
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Public rate-friendly endpoint for client reload button to trigger fresh live dispatches."""
    try:
        from scripts.ingest_real_live_news import fetch_and_build_live_feed
        # Run targeted live ingest for requested state + national in background
        background_tasks.add_task(fetch_and_build_live_feed, target_state=state, max_per_feed=15)
    except Exception as exc:
        logger.warning("Background live feed sync schedule warning: %s", exc)

    return {
        "status": "ok",
        "message": f"Live feed refresh task scheduled for {state or 'National'}",
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe: confirms API process is running and responsive."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    """Readiness probe: verifies database connectivity and schema migration status."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            res = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            if not res or not res[0]:
                raise HTTPException(status_code=503, detail="Database schema uninitialized: missing alembic_version")
            migration_ver = res[0]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Database readiness check failed: {type(exc).__name__}")
        raise HTTPException(status_code=503, detail="Database unavailable")

    provider = "locationiq" if settings.locationiq_api_key else "nominatim"
    return {
        "status": "ok",
        "database": "ok",
        "migration_version": migration_ver,
        "geocoder_provider": provider,
    }


# ---------------------------------------------------------------------------
# Ingestion Health Endpoint & Uptime Monitoring
# ---------------------------------------------------------------------------
# How to wire to UptimeRobot free tier once deployed:
# 1. Sign up for a free account at https://uptimerobot.com
# 2. Add New Monitor -> Monitor Type: "HTTP(s)"
# 3. Friendly Name: "NEWZZ Ingestion Worker"
# 4. URL (or IP): "https://<your-api-domain>/health/ingestion"
# 5. Monitoring Interval: 5 minutes (or 15 minutes on free tier)
# 6. Advanced Settings -> Keyword: Alert when keyword does NOT exist -> "status": "ok"
#    (or set HTTP status alert if health/ingestion returns 503 on worker stalls > 30m)
# 7. Add Alert Contact to receive email/webhook notifications when ingestion stops.
# ---------------------------------------------------------------------------
@app.get("/health/ingestion")
def health_ingestion() -> dict:
    from app.db import SessionLocal
    from app.models import WorkerRun
    from datetime import datetime, timezone

    try:
        db = SessionLocal()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database connection error: {exc}")

    try:
        latest = db.query(WorkerRun).order_by(WorkerRun.timestamp.desc()).first()
        if not latest:
            return {
                "status": "warning",
                "message": "No worker runs recorded yet",
                "last_run_timestamp": None,
                "sources_polled": 0,
                "articles_ingested": 0,
                "errors": [],
            }

        now = datetime.now(timezone.utc)
        diff_seconds = 0.0
        if latest.timestamp:
            ts = latest.timestamp if latest.timestamp.tzinfo else latest.timestamp.replace(tzinfo=timezone.utc)
            diff_seconds = (now - ts).total_seconds()

        stale_threshold = getattr(settings, "ingest_interval_seconds", 900) * 3

        if diff_seconds > stale_threshold:
            status = "stale"
        elif latest.errors and len(latest.errors) > 0:
            if latest.articles_ingested == 0:
                status = "failed"
            else:
                status = "degraded"
        else:
            status = "ok"

        return {
            "status": status,
            "provider": getattr(latest, "provider", "rss_pipeline"),
            "last_run_timestamp": latest.timestamp.isoformat() if latest.timestamp else None,
            "seconds_since_last_run": round(diff_seconds, 1),
            "sources_polled": latest.sources_polled,
            "articles_ingested": latest.articles_ingested,
            "credits_used": getattr(latest, "credits_used", 0),
            "errors": latest.errors or [],
            "duration_seconds": latest.duration_seconds,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database query error: {exc}")
    finally:
        db.close()


_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")

