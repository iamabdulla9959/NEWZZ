from collections.abc import Generator
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool, StaticPool

from app.config import normalize_database_url, settings

logger = logging.getLogger("newzz.db")


class Base(DeclarativeBase):
    pass


def create_db_engine(custom_url: str | None = None):
    raw_url = custom_url if custom_url is not None else settings.database_url
    is_prod = getattr(settings, "app_env", "development").strip().lower() == "production"

    if is_prod:
        if not raw_url or not str(raw_url).strip():
            raise RuntimeError(
                "CRITICAL PRODUCTION CONFIGURATION ERROR: DATABASE_URL is missing or empty. "
                "Production requires a valid PostgreSQL connection string."
            )
        trimmed = str(raw_url).strip().lower()
        if trimmed.startswith("sqlite"):
            raise RuntimeError(
                "CRITICAL PRODUCTION CONFIGURATION ERROR: Production refuses to run against SQLite. "
                "DATABASE_URL must be configured with a durable managed PostgreSQL database."
            )
        if not (trimmed.startswith("postgres://") or trimmed.startswith("postgresql://") or trimmed.startswith("postgresql+")):
            raise ValueError(
                f"CRITICAL PRODUCTION CONFIGURATION ERROR: Malformed or unsupported DATABASE_URL scheme for production: "
                f"'{raw_url.split('://')[0] if '://' in raw_url else raw_url}'."
            )

    url = normalize_database_url(raw_url)

    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        poolclass = StaticPool if ":memory:" in url else NullPool
        return create_engine(
            url,
            poolclass=poolclass,
            connect_args=connect_args,
        )
    else:
        # PostgreSQL / Production: use connection pooling and pre-ping
        return create_engine(
            url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            connect_args=connect_args,
        )


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
