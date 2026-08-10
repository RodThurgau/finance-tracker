import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# FINANCE_DB_PATH lets the test suite point engine, backups, and Alembic at a
# throwaway database. Unset in normal use.
_db_path_override = os.environ.get("FINANCE_DB_PATH")
DB_PATH = (
    Path(_db_path_override).resolve()
    if _db_path_override
    else Path(__file__).resolve().parent.parent / "data" / "finance.db"
)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
