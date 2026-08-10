"""GET /api/v1/export/csv — filtered CSV export."""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Tag, Transaction, TransactionTag


def make_transaction(
    db: Session,
    *,
    amount: str,
    when: date,
    composite_hash: str,
    description: str = "Testbuchung",
    currency: str = "EUR",
    source: str = "ING",
    counter_account: str | None = None,
    transaction_type: str | None = None,
    category_id: int | None = None,
    subcategory_id: int | None = None,
    exclude_from_stats: bool = False,
) -> Transaction:
    transaction = Transaction(
        source=source,
        composite_hash=composite_hash,
        date=when,
        description=description,
        amount=Decimal(amount),
        currency=currency,
        counter_account=counter_account,
        transaction_type=transaction_type,
        category_id=category_id,
        subcategory_id=subcategory_id,
        exclude_from_stats=exclude_from_stats,
    )
    db.add(transaction)
    db.flush()
    return transaction


def make_category(client: TestClient, name: str = "Testkategorie") -> int:
    return client.post("/api/v1/categories", json={"name": name, "color": "#38bdf8"}).json()["id"]


def parse_csv(response) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(response.text)))


def test_export_has_expected_columns_and_headers(client: TestClient) -> None:
    response = client.get("/api/v1/export/csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    reader = csv.reader(io.StringIO(response.text))
    header = next(reader)
    assert header == [
        "date",
        "description",
        "amount",
        "currency",
        "source",
        "category",
        "subcategory",
        "tags",
        "counter_account",
        "transaction_type",
    ]


def test_export_row_contents(client: TestClient, db: Session) -> None:
    category_id = make_category(client, "Wohnen")
    subcategory_id = client.post(
        f"/api/v1/categories/{category_id}/subcategories", json={"name": "Miete"}
    ).json()["id"]
    tag = Tag(name="Wiederkehrend", color="#818cf8")
    db.add(tag)
    db.flush()
    txn = make_transaction(
        db,
        amount="-950.00",
        when=date(2026, 1, 3),
        composite_hash="a",
        description="Miete Januar",
        counter_account="Vermieter GmbH",
        transaction_type="Lastschrift",
        category_id=category_id,
        subcategory_id=subcategory_id,
    )
    db.add(TransactionTag(transaction_id=txn.id, tag_id=tag.id))
    db.flush()

    rows = parse_csv(client.get("/api/v1/export/csv"))

    assert len(rows) == 1
    row = rows[0]
    assert row["date"] == "2026-01-03"
    assert row["description"] == "Miete Januar"
    assert row["amount"] == "-950.00"
    assert row["currency"] == "EUR"
    assert row["source"] == "ING"
    assert row["category"] == "Wohnen"
    assert row["subcategory"] == "Miete"
    assert row["tags"] == "Wiederkehrend"
    assert row["counter_account"] == "Vermieter GmbH"
    assert row["transaction_type"] == "Lastschrift"


def test_export_multiple_tags_are_semicolon_joined(client: TestClient, db: Session) -> None:
    a = Tag(name="Gemeinsame Ausgabe", color="#22d3ee")
    b = Tag(name="Erstattungsfaehig", color="#fbbf24")
    db.add_all([a, b])
    db.flush()
    txn = make_transaction(db, amount="-10.00", when=date(2026, 1, 1), composite_hash="a")
    db.add(TransactionTag(transaction_id=txn.id, tag_id=a.id))
    db.add(TransactionTag(transaction_id=txn.id, tag_id=b.id))
    db.flush()

    rows = parse_csv(client.get("/api/v1/export/csv"))

    assert rows[0]["tags"] == "Gemeinsame Ausgabe;Erstattungsfaehig"


def test_export_blank_fields_for_uncategorized_untagged_row(client: TestClient, db: Session) -> None:
    make_transaction(db, amount="-10.00", when=date(2026, 1, 1), composite_hash="a")

    rows = parse_csv(client.get("/api/v1/export/csv"))

    row = rows[0]
    assert row["category"] == ""
    assert row["subcategory"] == ""
    assert row["tags"] == ""
    assert row["counter_account"] == ""
    assert row["transaction_type"] == ""


def test_export_includes_excluded_rows_by_default(client: TestClient, db: Session) -> None:
    make_transaction(
        db, amount="-10.00", when=date(2026, 1, 1), composite_hash="a", exclude_from_stats=True
    )

    rows = parse_csv(client.get("/api/v1/export/csv"))

    assert len(rows) == 1


def test_export_accepts_excluded_filter_same_as_transaction_list(
    client: TestClient, db: Session
) -> None:
    make_transaction(
        db, amount="-10.00", when=date(2026, 1, 1), composite_hash="a", exclude_from_stats=True
    )
    make_transaction(
        db, amount="-20.00", when=date(2026, 1, 2), composite_hash="b", exclude_from_stats=False
    )

    only_excluded = parse_csv(client.get("/api/v1/export/csv", params={"excluded": "true"}))
    only_included = parse_csv(client.get("/api/v1/export/csv", params={"excluded": "false"}))

    assert len(only_excluded) == 1 and only_excluded[0]["amount"] == "-10.00"
    assert len(only_included) == 1 and only_included[0]["amount"] == "-20.00"


def test_export_applies_category_and_source_filters(client: TestClient, db: Session) -> None:
    category_id = make_category(client)
    make_transaction(
        db, amount="-10.00", when=date(2026, 1, 1), composite_hash="a", category_id=category_id
    )
    make_transaction(db, amount="-20.00", when=date(2026, 1, 2), composite_hash="b")
    make_transaction(
        db, amount="-30.00", when=date(2026, 1, 3), composite_hash="c", source="PayPal"
    )

    by_category = parse_csv(client.get("/api/v1/export/csv", params={"category_id": category_id}))
    by_source = parse_csv(client.get("/api/v1/export/csv", params={"source": "PayPal"}))

    assert len(by_category) == 1 and by_category[0]["amount"] == "-10.00"
    assert len(by_source) == 1 and by_source[0]["amount"] == "-30.00"


def test_export_respects_sort(client: TestClient, db: Session) -> None:
    make_transaction(db, amount="-30.00", when=date(2026, 1, 1), composite_hash="a")
    make_transaction(db, amount="-10.00", when=date(2026, 1, 2), composite_hash="b")
    make_transaction(db, amount="-20.00", when=date(2026, 1, 3), composite_hash="c")

    rows = parse_csv(
        client.get("/api/v1/export/csv", params={"sort_by": "amount", "sort_dir": "asc"})
    )

    assert [r["amount"] for r in rows] == ["-30.00", "-20.00", "-10.00"]


# --- filename -----------------------------------------------------------


def test_filename_reflects_actual_exported_data_range(client: TestClient, db: Session) -> None:
    make_transaction(db, amount="-10.00", when=date(2026, 3, 5), composite_hash="a")
    make_transaction(db, amount="-20.00", when=date(2026, 1, 20), composite_hash="b")
    make_transaction(db, amount="-30.00", when=date(2026, 5, 1), composite_hash="c")

    response = client.get("/api/v1/export/csv")

    assert 'filename="finance_export_2026-01-20_2026-05-01.csv"' in response.headers[
        "content-disposition"
    ]


def test_filename_reflects_filtered_subset_not_full_table(client: TestClient, db: Session) -> None:
    category_id = make_category(client)
    make_transaction(
        db, amount="-10.00", when=date(2026, 6, 1), composite_hash="a", category_id=category_id
    )
    # Outside the filter, and outside the date range that should end up in the filename.
    make_transaction(db, amount="-20.00", when=date(2026, 1, 1), composite_hash="b")

    response = client.get("/api/v1/export/csv", params={"category_id": category_id})

    assert 'filename="finance_export_2026-06-01_2026-06-01.csv"' in response.headers[
        "content-disposition"
    ]


def test_filename_falls_back_to_today_when_export_is_empty(client: TestClient) -> None:
    from datetime import date as date_cls

    today = date_cls.today().isoformat()

    response = client.get("/api/v1/export/csv", params={"category_id": 999999})

    assert f'filename="finance_export_{today}_{today}.csv"' in response.headers[
        "content-disposition"
    ]
    assert parse_csv(response) == []


def test_filename_ignores_requested_date_filter_bounds(client: TestClient, db: Session) -> None:
    """A wide requested range over sparse data names the file after the data, not the request."""
    make_transaction(db, amount="-10.00", when=date(2026, 6, 15), composite_hash="a")

    response = client.get(
        "/api/v1/export/csv", params={"date_from": "2020-01-01", "date_to": "2030-12-31"}
    )

    assert 'filename="finance_export_2026-06-15_2026-06-15.csv"' in response.headers[
        "content-disposition"
    ]
