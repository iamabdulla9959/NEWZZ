from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


def normalize_database_url(url: str) -> str:
    """Normalize database connection URLs for PostgreSQL and SQLite.

    Ensures standard PostgreSQL URLs (e.g. from Supabase, Neon, Render) starting with
    'postgres://' or 'postgresql://' are mapped to 'postgresql+psycopg://' so the
    modern psycopg 3 driver is used without requiring legacy psycopg2.
    """
    if not url:
        return url
    trimmed = url.strip()
    if trimmed.startswith("postgres://"):
        return "postgresql+psycopg://" + trimmed[len("postgres://"):]
    if trimmed.startswith("postgresql://") and not trimmed.startswith("postgresql+"):
        return "postgresql+psycopg://" + trimmed[len("postgresql://"):]
    return trimmed




def redact_database_url(url: str) -> str:
    """Safely redacts database credentials from URL for diagnostic output and logs."""
    if not url:
        return "<empty>"
    try:
        from urllib.parse import urlsplit, urlunsplit
        parts = urlsplit(url)
        if parts.password:
            netloc = f"{parts.username or ''}:***@{parts.hostname or ''}"
            if parts.port:
                netloc += f":{parts.port}"
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
        return url
    except Exception:
        return "<redacted>"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://newsreels:newsreels@localhost:5432/newsreels"
    redis_url: str = "redis://localhost:6379/0"
    llm_api_key: str = ""
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_model: str = "gemini-2.0-flash"
    newsdata_api_key: str = ""
    locationiq_api_key: str = ""
    admin_api_key: str = "change-me-local-only"
    internal_ingestion_key: str = ""
    crawl_cooldown_seconds: int = 10
    ingest_interval_seconds: int = 900
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "*"


settings = Settings()
