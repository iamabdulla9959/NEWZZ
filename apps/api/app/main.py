import sys
from pathlib import Path

# Ensure repository root is on sys.path for packages.* imports
_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from contextlib import asynccontextmanager
from app.db import engine
from app.models import Base
from app.routers.admin import router as admin_router
from app.routers.feed import router as feed_router
from app.routers.location import router as location_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create all schema tables if they do not exist on application startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="News Reels API", version="0.1.0", lifespan=lifespan)

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


@app.get("/health")
def health() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    provider = "locationiq" if settings.locationiq_api_key else "nominatim"
    return {
        "status": "ok",
        "database": "ok",
        "geocoder_provider": provider,
    }


# ---------------------------------------------------------------------------
# Ingestion Health Endpoint & Uptime Monitoring
# ---------------------------------------------------------------------------
# How to wire to UptimeRobot free tier once deployed:
# 1. Sign up for a free account at https://uptimerobot.com
# 2. Add New Monitor -> Monitor Type: "HTTP(s)"
# 3. Friendly Name: "NewsReels Ingestion Worker"
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

    db = SessionLocal()
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
        
        # Check staleness (e.g. if last run was > 45 minutes ago)
        now = datetime.now(timezone.utc)
        diff_seconds = 0.0
        if latest.timestamp:
            ts = latest.timestamp if latest.timestamp.tzinfo else latest.timestamp.replace(tzinfo=timezone.utc)
            diff_seconds = (now - ts).total_seconds()

        status = "ok"
        if latest.errors and len(latest.errors) > 0:
            status = "degraded"
        if diff_seconds > 2700:  # > 45 mins
            status = "stale"

        return {
            "status": status,
            "provider": getattr(latest, "provider", "rss"),
            "last_run_timestamp": latest.timestamp.isoformat() if latest.timestamp else None,
            "seconds_since_last_run": round(diff_seconds, 1),
            "sources_polled": latest.sources_polled,
            "articles_ingested": latest.articles_ingested,
            "credits_used": getattr(latest, "credits_used", 0),
            "errors": latest.errors or [],
            "duration_seconds": latest.duration_seconds,
        }
    finally:
        db.close()


_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")

