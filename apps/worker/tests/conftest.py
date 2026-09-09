import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

API_ROOT = Path(__file__).resolve().parents[2] / "api"
DB = API_ROOT / "worker_test.db"
os.environ["DATABASE_URL"] = "sqlite:///" + DB.as_posix()

from app.db import SessionLocal, engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    if DB.exists():
        DB.unlink()
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")
    yield
    engine.dispose()
    if DB.exists():
        DB.unlink()


@pytest.fixture()
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
