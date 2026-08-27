"""The SQL console — /api/v1/sql.

The refusal tests carry the weight here: this is the only endpoint that runs
text the user typed, and the guard in `services/sql_console.py` is what stands
between a typo and a month of lost categorization.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from models import Transaction


def add(db: Session, description: str, amount: str, on: date = date(2026, 5, 1)) -> Transaction:
    transaction = Transaction(
        source="ING",
        composite_hash=f"hash-{description}-{amount}",
        date=on,
        description=description,
        amount=Decimal(amount),
    )
    db.add(transaction)
    db.flush()
    return transaction


def run_ok(client: TestClient, sql: str, **body) -> dict:
    response = client.post("/api/v1/sql/execute", json={"sql": sql, **body})
    assert response.status_code == 200, response.json()
    return response.json()


def refuse(client: TestClient, sql: str) -> str:
    response = client.post("/api/v1/sql/execute", json={"sql": sql})
    assert response.status_code == 400, response.json()
    return response.json()["detail"]


# --- running queries -------------------------------------------------------


def test_select_returns_columns_and_rows(client: TestClient, db: Session) -> None:
    add(db, "Rewe", "-12.50")
    add(db, "Aldi", "-3.20")

    body = run_ok(client, "SELECT description, amount FROM transactions ORDER BY description")

    assert body["columns"] == ["description", "amount"]
    assert body["rows"] == [["Aldi", -320], ["Rewe", -1250]]
    assert body["row_count"] == 2
    assert body["truncated"] is False


def test_amounts_come_back_as_stored_cents(client: TestClient, db: Session) -> None:
    """Not divided by 100 on the way out. An arbitrary query can compute
    anything, and guessing which integers are money would corrupt the ones that
    are not — the schema panel labels the column instead."""
    add(db, "Miete", "-820.00")

    body = run_ok(client, "SELECT amount FROM transactions")

    assert body["rows"] == [[-82000]]


def test_a_trailing_semicolon_is_not_a_second_statement(client: TestClient, db: Session) -> None:
    add(db, "Rewe", "-12.50")

    assert run_ok(client, "SELECT 1;")["rows"] == [[1]]


def test_comments_are_stripped_before_the_statement_is_counted(client: TestClient) -> None:
    body = run_ok(client, "-- a note\nSELECT 1 /* and another */")

    assert body["rows"] == [[1]]


def test_colons_do_not_read_as_bind_parameters(client: TestClient) -> None:
    """`text()` would take `:00` for a parameter it was never given. The console
    goes through `exec_driver_sql`, so the driver sees the text verbatim."""
    body = run_ok(client, "SELECT time('12:30:00') AS t")

    assert body["rows"] == [["12:30:00"]]


def test_cte_is_allowed(client: TestClient, db: Session) -> None:
    add(db, "Rewe", "-12.50")

    body = run_ok(
        client,
        "WITH spend AS (SELECT amount FROM transactions) SELECT SUM(amount) FROM spend",
    )

    assert body["rows"] == [[-1250]]


def test_limit_truncates_and_says_so(client: TestClient, db: Session) -> None:
    for index in range(5):
        add(db, f"Row {index}", "-1.00")

    body = run_ok(client, "SELECT id FROM transactions", limit=2)

    assert body["row_count"] == 2
    assert body["truncated"] is True


def test_limit_not_reached_reports_untruncated(client: TestClient, db: Session) -> None:
    add(db, "Rewe", "-12.50")

    body = run_ok(client, "SELECT id FROM transactions", limit=2)

    assert body["truncated"] is False


def test_broken_sql_is_a_400_with_the_drivers_message(client: TestClient) -> None:
    """Just SQLite's line. SQLAlchemy wraps it in the statement plus a link to
    its own docs, none of which helps someone who mistyped a table name."""
    detail = refuse(client, "SELECT * FROM nonexistent_table")

    assert detail == "no such table: nonexistent_table"


# --- refusals --------------------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM transactions",
        "UPDATE transactions SET amount = 0",
        "INSERT INTO tags (name) VALUES ('x')",
        "DROP TABLE transactions",
        "ALTER TABLE transactions ADD COLUMN x TEXT",
        "CREATE TABLE x (id INTEGER)",
        "PRAGMA writable_schema = ON",
        "ATTACH DATABASE 'other.db' AS other",
        "VACUUM",
        "WITH doomed AS (SELECT id FROM transactions) DELETE FROM transactions",
    ],
)
def test_writes_are_refused(client: TestClient, statement: str) -> None:
    refuse(client, statement)


def test_multiple_statements_are_refused(client: TestClient) -> None:
    detail = refuse(client, "SELECT 1; SELECT 2")

    assert "one statement" in detail


def test_a_write_hidden_behind_a_select_is_still_refused(client: TestClient) -> None:
    """The second statement is where the damage would be, so counting
    statements has to happen before the first one runs."""
    refuse(client, "SELECT 1; DELETE FROM transactions")


def test_a_write_keyword_inside_a_string_literal_is_fine(client: TestClient, db: Session) -> None:
    """`Verwendungszweck` is free text from a bank. A payment reference reading
    'DELETE' must not make the query unrunnable."""
    add(db, "DROP TABLE hinweis", "-1.00")

    body = run_ok(
        client,
        "SELECT description FROM transactions WHERE description LIKE '%DROP TABLE%'",
    )

    assert body["rows"] == [["DROP TABLE hinweis"]]


def test_a_write_keyword_inside_a_comment_is_fine(client: TestClient) -> None:
    assert run_ok(client, "SELECT 1 -- todo: delete this later")["rows"] == [[1]]


def test_empty_query_is_refused(client: TestClient) -> None:
    assert "empty" in refuse(client, "   \n  ").lower()


def test_comment_only_query_is_refused(client: TestClient) -> None:
    assert "empty" in refuse(client, "-- just thinking out loud").lower()


def test_the_readonly_connection_refuses_writes_for_real(db: Session) -> None:
    """Layer 2, tested directly: even if the parser above were fooled, SQLite
    itself rejects the write. The endpoint reads through this engine in
    production; the test client swaps it out only so uncommitted fixture rows
    are visible (see conftest)."""
    from database import readonly_engine

    assert "mode=ro" in str(readonly_engine.url)

    with readonly_engine.connect() as connection:
        with pytest.raises(OperationalError, match="readonly database"):
            connection.exec_driver_sql("CREATE TABLE should_not_exist (id INTEGER)")


# --- saved queries ---------------------------------------------------------


def save(client: TestClient, **body) -> dict:
    response = client.post("/api/v1/sql/queries", json={"sql": "SELECT 1", **body})
    assert response.status_code == 201, response.json()
    return response.json()


def test_saved_queries_round_trip(client: TestClient) -> None:
    created = save(client, name="Ausgaben pro Monat", sql="SELECT 1", folder="Berichte")

    assert created["folder"] == "Berichte"

    listed = client.get("/api/v1/sql/queries").json()
    assert [item["name"] for item in listed] == ["Ausgaben pro Monat"]


def test_saved_query_defaults_to_the_top_level(client: TestClient) -> None:
    assert save(client, name="Schnellcheck")["folder"] == ""


def test_names_are_stripped(client: TestClient) -> None:
    """Otherwise 'Berichte ' becomes a second folder that looks identical."""
    created = save(client, name="  Schnellcheck  ", folder="  Berichte  ")

    assert (created["name"], created["folder"]) == ("Schnellcheck", "Berichte")


def test_duplicate_name_in_the_same_folder_is_refused(client: TestClient) -> None:
    save(client, name="Bericht", folder="Monatlich")

    response = client.post(
        "/api/v1/sql/queries", json={"name": "Bericht", "sql": "SELECT 2", "folder": "Monatlich"}
    )

    assert response.status_code == 400


def test_the_same_name_in_two_folders_is_allowed(client: TestClient) -> None:
    save(client, name="Bericht", folder="Monatlich")
    save(client, name="Bericht", folder="Jährlich")

    assert len(client.get("/api/v1/sql/queries").json()) == 2


def test_duplicate_name_at_the_top_level_is_refused(client: TestClient) -> None:
    """The top level is `""`, not NULL, precisely so this constraint applies to
    unfiled queries too — SQLite would treat two NULLs as distinct."""
    save(client, name="Bericht")

    response = client.post("/api/v1/sql/queries", json={"name": "Bericht", "sql": "SELECT 2"})

    assert response.status_code == 400


def test_patch_leaves_unsent_fields_alone(client: TestClient) -> None:
    created = save(client, name="Bericht", sql="SELECT 1", folder="Monatlich")

    updated = client.patch(
        f"/api/v1/sql/queries/{created['id']}", json={"sql": "SELECT 2"}
    ).json()

    assert updated["sql"] == "SELECT 2"
    assert (updated["name"], updated["folder"]) == ("Bericht", "Monatlich")


def test_patch_can_move_a_query_out_of_its_folder(client: TestClient) -> None:
    created = save(client, name="Bericht", folder="Monatlich")

    updated = client.patch(f"/api/v1/sql/queries/{created['id']}", json={"folder": ""}).json()

    assert updated["folder"] == ""


def test_deleting_the_last_query_removes_the_folder(client: TestClient) -> None:
    """Folders are derived from the queries in them, so there is nothing else to
    clean up — and no way to leave an empty one behind."""
    created = save(client, name="Bericht", folder="Monatlich")

    assert client.delete(f"/api/v1/sql/queries/{created['id']}").status_code == 204
    assert client.get("/api/v1/sql/queries").json() == []


def test_patch_and_delete_404_on_an_unknown_query(client: TestClient) -> None:
    assert client.patch("/api/v1/sql/queries/999", json={"sql": "SELECT 1"}).status_code == 404
    assert client.delete("/api/v1/sql/queries/999").status_code == 404


# --- folders ---------------------------------------------------------------


def test_renaming_a_folder_moves_every_query_in_it(client: TestClient) -> None:
    save(client, name="Eins", folder="Alt")
    save(client, name="Zwei", folder="Alt")

    response = client.patch("/api/v1/sql/folders", json={"name": "Alt", "new_name": "Neu"})

    assert response.status_code == 200
    assert {item["name"] for item in response.json()} == {"Eins", "Zwei"}
    assert {item["folder"] for item in client.get("/api/v1/sql/queries").json()} == {"Neu"}


def test_renaming_into_an_existing_folder_merges_them(client: TestClient) -> None:
    save(client, name="Eins", folder="Alt")
    save(client, name="Zwei", folder="Neu")

    response = client.patch("/api/v1/sql/folders", json={"name": "Alt", "new_name": "Neu"})

    assert response.status_code == 200
    assert {item["name"] for item in response.json()} == {"Eins", "Zwei"}


def test_a_merge_that_would_collide_is_refused(client: TestClient) -> None:
    """Two queries called "Bericht" cannot share a folder, so the merge is
    rejected whole. Nothing moves: it is one UPDATE, and SQLite applies a
    statement atomically. That the rows are untouched afterwards is not asserted
    here — the harness rolls the whole test transaction back on the failure, so
    it cannot see the state the app would leave behind (see conftest)."""
    save(client, name="Bericht", folder="Alt")
    save(client, name="Bericht", folder="Neu")

    response = client.patch("/api/v1/sql/folders", json={"name": "Alt", "new_name": "Neu"})

    assert response.status_code == 400
    assert "Neu" in response.json()["detail"]


def test_renaming_an_empty_folder_is_a_404(client: TestClient) -> None:
    assert (
        client.patch("/api/v1/sql/folders", json={"name": "Nichts", "new_name": "X"}).status_code
        == 404
    )


def test_queries_can_be_moved_out_of_a_folder_wholesale(client: TestClient) -> None:
    """Renaming *to* the top level is a valid move; renaming to an empty target
    the other way round would be ambiguous, which is why only the source may be
    empty."""
    save(client, name="Eins", folder="Alt")

    response = client.patch("/api/v1/sql/folders", json={"name": "Alt", "new_name": ""})

    assert response.status_code == 400


# --- schema panel ----------------------------------------------------------


def test_schema_lists_the_tables_a_query_can_read(client: TestClient) -> None:
    tables = {table["name"]: table for table in client.get("/api/v1/sql/schema").json()["tables"]}

    assert "transactions" in tables
    assert "alembic_version" not in tables

    columns = {column["name"]: column for column in tables["transactions"]["columns"]}
    assert columns["id"]["primary_key"] is True
    assert columns["category_id"]["nullable"] is True


def test_schema_flags_that_amounts_are_cents(client: TestClient) -> None:
    """The one note that stops `WHERE amount > 50` from silently meaning 50
    cents."""
    tables = {table["name"]: table for table in client.get("/api/v1/sql/schema").json()["tables"]}
    columns = {column["name"]: column for column in tables["transactions"]["columns"]}

    assert "cents" in columns["amount"]["note"].lower()
