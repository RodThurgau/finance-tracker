"""Shared pytest fixtures.

The suite runs against a throwaway SQLite file built by Alembic, never against
``data/finance.db``. The database path is pinned via ``FINANCE_DB_PATH`` before
``database`` is imported, so the app's engine and Alembic's ``env.py`` both pick
it up.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
GENERATED_DIR = FIXTURES_DIR / "generated"

_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="finance-tracker-tests-"))
os.environ["FINANCE_DB_PATH"] = str(_TEST_DB_DIR / "finance.db")

from database import DB_PATH, SessionLocal, engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import make_fixtures  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def generated_fixtures() -> None:
    """Regenerate derived fixtures so tests never run against a stale set."""
    make_fixtures.main()


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[Path]:
    """Build the test database from migrations once per session."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "head")
    yield DB_PATH
    engine.dispose()


@pytest.fixture
def db(migrated_database: Path) -> Iterator[Session]:
    """A session whose writes are rolled back at the end of the test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Directory holding the hand-written demo CSVs."""
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def generated_dir(generated_fixtures: None) -> Path:
    """Directory holding the fixtures derived from the demo CSVs."""
    return GENERATED_DIR


@pytest.fixture
def client(db: Session):
    """A TestClient whose requests run against the rolled-back `db` session."""
    from fastapi.testclient import TestClient

    from database import get_db
    from main import app

    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
