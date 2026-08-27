"""The SQL console: run a read-only query, and keep the ones worth repeating.

Execution and storage are deliberately split across two connections. The
statement runs on `get_readonly_connection` (SQLite `mode=ro`, see
`database.py`), while saved queries are ordinary rows written through the ORM on
`get_db`. A query the console runs therefore cannot touch the queries the
console stores.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection, inspect, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db, get_readonly_connection
from models import SavedQuery
from schemas import (
    DatabaseSchema,
    FolderRename,
    SchemaColumn,
    SchemaTable,
    SqlQueryRequest,
    SqlQueryResultSchema,
)
from schemas import SavedQuery as SavedQuerySchema
from schemas import SavedQueryCreate, SavedQueryUpdate
from services.sql_console import SqlConsoleError, run_query

router = APIRouter(prefix="/api/v1/sql", tags=["sql"])

# Columns whose stored form is not what the name suggests. Shown next to the
# column in the schema panel, because `WHERE amount > 50` silently meaning 50
# cents is the mistake this console makes easiest.
COLUMN_NOTES = {
    ("transactions", "amount"): "INTEGER cents — 1234 = 12,34 €",
    ("transactions", "date"): "TEXT 'YYYY-MM-DD'",
    ("transactions", "composite_hash"): "sha256 of the raw ING cells; ING rows only",
    ("transactions", "exclude_from_stats"): "user-owned flag, 0/1",
    ("transactions", "user_categorized"): "0/1 — rules skip rows where this is 1",
    ("saved_queries", "folder"): "'' is the top level, never NULL",
}


def _get_or_404(db: Session, query_id: int) -> SavedQuery:
    saved = db.get(SavedQuery, query_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Saved query not found")
    return saved


@router.post("/execute", response_model=SqlQueryResultSchema)
def execute(
    request: SqlQueryRequest,
    connection: Connection = Depends(get_readonly_connection),
) -> SqlQueryResultSchema:
    """Run one read-only statement and return its rows.

    A rejected or failed statement is a 400 carrying the reason — a typo in a
    query the user typed is not a server error, and the editor prints `detail`
    straight under the statement.
    """
    try:
        result = run_query(connection, request.sql, limit=request.limit)
    except SqlConsoleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SqlQueryResultSchema(
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        truncated=result.truncated,
        elapsed_ms=result.elapsed_ms,
    )


@router.get("/schema", response_model=DatabaseSchema)
def database_schema(connection: Connection = Depends(get_readonly_connection)) -> DatabaseSchema:
    """Every table and column, for the reference panel next to the editor.

    Read off the live database rather than off `models.py`, so what the panel
    lists is what a query can actually select.
    """
    inspector = inspect(connection)
    tables = []
    for table_name in sorted(inspector.get_table_names()):
        if table_name == "alembic_version":
            continue
        columns = [
            SchemaColumn(
                name=column["name"],
                type=str(column["type"]),
                nullable=bool(column["nullable"]),
                primary_key=bool(column.get("primary_key")),
                note=COLUMN_NOTES.get((table_name, column["name"])),
            )
            for column in inspector.get_columns(table_name)
        ]
        tables.append(SchemaTable(name=table_name, columns=columns))
    return DatabaseSchema(tables=tables)


@router.get("/queries", response_model=list[SavedQuerySchema])
def list_saved_queries(db: Session = Depends(get_db)) -> list[SavedQuery]:
    """All saved queries, ordered folder-then-name — the order they are listed
    in. Unfiled queries carry `folder == ""`, which sorts first."""
    return list(
        db.scalars(select(SavedQuery).order_by(SavedQuery.folder.asc(), SavedQuery.name.asc())).all()
    )


@router.post("/queries", response_model=SavedQuerySchema, status_code=201)
def create_saved_query(data: SavedQueryCreate, db: Session = Depends(get_db)) -> SavedQuery:
    """Save a query. The folder is created implicitly by naming it — there is no
    folder table, so a folder exists exactly as long as something is in it."""
    if not data.name:
        raise HTTPException(status_code=400, detail="A saved query needs a name")

    saved = SavedQuery(name=data.name, sql=data.sql, folder=data.folder)
    db.add(saved)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"'{data.name}' already exists in this folder"
        ) from exc
    db.refresh(saved)
    return saved


@router.patch("/queries/{query_id}", response_model=SavedQuerySchema)
def update_saved_query(
    query_id: int, data: SavedQueryUpdate, db: Session = Depends(get_db)
) -> SavedQuery:
    """Rename, re-file, or overwrite the statement. Unset fields are left alone,
    so saving over an open tab sends `sql` and nothing else."""
    saved = _get_or_404(db, query_id)
    fields = data.model_fields_set

    if "name" in fields:
        if not data.name:
            raise HTTPException(status_code=400, detail="A saved query needs a name")
        saved.name = data.name
    if "sql" in fields:
        saved.sql = data.sql
    if "folder" in fields:
        saved.folder = data.folder or ""

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"'{saved.name}' already exists in this folder"
        ) from exc
    db.refresh(saved)
    return saved


@router.delete("/queries/{query_id}", status_code=204)
def delete_saved_query(query_id: int, db: Session = Depends(get_db)) -> None:
    db.delete(_get_or_404(db, query_id))
    db.commit()


@router.patch("/folders", response_model=list[SavedQuerySchema])
def rename_folder(data: FolderRename, db: Session = Depends(get_db)) -> list[SavedQuery]:
    """Move every query in one folder to another name, in a single statement.

    Renaming into an existing folder merges the two, which is the useful
    behavior and the only sane reading of "rename to a name already in use" when
    folders are just a label. A name collision inside the merged folder is what
    the unique constraint is for, and it comes back as a 400 with nothing moved.

    The folder name goes in the body rather than the path: folder names are free
    text and would otherwise need escaping for slashes and dots.
    """
    if not data.new_name:
        raise HTTPException(
            status_code=400,
            detail="Use an empty source name to move queries out of a folder, not an empty target",
        )

    affected = db.scalars(select(SavedQuery).where(SavedQuery.folder == data.name)).all()
    if not affected:
        raise HTTPException(status_code=404, detail=f"No saved queries in folder '{data.name}'")

    try:
        # SQLite checks the unique index as the UPDATE runs, not at COMMIT, so
        # the collision surfaces here rather than below.
        db.execute(
            update(SavedQuery).where(SavedQuery.folder == data.name).values(folder=data.new_name)
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"'{data.new_name}' already holds a query with one of these names",
        ) from exc

    return list(
        db.scalars(
            select(SavedQuery)
            .where(SavedQuery.folder == data.new_name)
            .order_by(SavedQuery.name.asc())
        ).all()
    )
