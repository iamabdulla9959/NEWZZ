import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "test.db"
os.environ["DATABASE_URL"] = "sqlite:///" + DB.as_posix()
os.environ.setdefault("ADMIN_API_KEY", "change-me-local-only")

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.models import Base


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    if DB.exists():
        DB.unlink()
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")
    yield
    engine.dispose()
    if DB.exists():
        DB.unlink()


@pytest.fixture()
def db() -> Session:
    session = SessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    try:
        yield session
    finally:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()
