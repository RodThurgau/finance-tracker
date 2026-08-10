import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backup import BackupError, run_backup
from database import SessionLocal
from routers import imports, tags, transactions
from seed import seed_database

BACKEND_DIR = Path(__file__).resolve().parent
log = logging.getLogger(__name__)


def run_migrations() -> None:
    """Bring the database up to head. Alembic owns the schema, so this is the
    only place tables come into existence."""
    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    # Leave the host's logging alone; see the note in alembic/env.py.
    alembic_cfg.attributes["configure_logger"] = False
    logging.getLogger("alembic").setLevel(logging.INFO)
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        run_backup()
    except BackupError as exc:
        raise RuntimeError(f"Startup aborted: {exc}") from exc

    run_migrations()

    with SessionLocal() as session:
        result = seed_database(session)
    if not result.skipped:
        log.info(
            "Seeded %d categories, %d subcategories, %d tags",
            result.categories,
            result.subcategories,
            result.tags,
        )

    yield


app = FastAPI(title="Finance Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(imports.router)
app.include_router(transactions.router)
app.include_router(tags.router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
