import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Connection, create_engine
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

# Second engine over the same file, opened `mode=ro` so SQLite itself rejects
# any write. Used only by the SQL console, where the statement comes from the
# user rather than from the app: the console parses what it is given (see
# `services/sql_console.py`), and this is the backstop for anything that parse
# might miss. Forward slashes because the path goes into a `file:` URI.
readonly_engine = create_engine(
    f"sqlite:///file:{DB_PATH.as_posix()}?mode=ro&uri=true",
    connect_args={"check_same_thread": False},
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_readonly_connection() -> Iterator[Connection]:
    """A connection that cannot write, for user-supplied SQL.

    Separate from `get_db` on purpose — a request that reaches for this one is
    saying it does not know what statement it is about to run.
    """
    with readonly_engine.connect() as connection:
        yield connection
