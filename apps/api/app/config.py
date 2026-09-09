from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://newsreels:newsreels@localhost:5432/newsreels"
    redis_url: str = "redis://localhost:6379/0"
    llm_api_key: str = ""
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_model: str = "gemini-2.0-flash"
    newsdata_api_key: str = ""
    admin_api_key: str = "change-me-local-only"
    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()
