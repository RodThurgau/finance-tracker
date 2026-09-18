"""GET /api/v1/stats/by-category, /by-tag and /trend — the analytics tables.

These three share `_countable` with `/stats/summary`, so the excluded-row and
internal-transfer gates are exercised here too: an analytics page that counted
rows the Übersicht drops would report a different ledger than the rest of the
app.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Tag, Transaction, TransactionTag


def make_transaction(
    db: Session,
    *,
    amount: str,
    when: date = date(2026, 1, 15),
    composite_hash: str,
    category_id: int | None = None,
    subcategory_id: int | None = None,
    exclude_from_stats: bool = False,
    source: str = "ING",
    counter_account: str | None = None,
    transaction_type: str | None = None,
) -> Transaction:
    transaction = Transaction(
        source=source,
        composite_hash=composite_hash,
        date=when,
        description="Testbuchung",
        amount=Decimal(amount),
        counter_account=counter_account,
        transaction_type=transaction_type,
        category_id=category_id,
        subcategory_id=subcategory_id,
        exclude_from_stats=exclude_from_stats,
    )
    db.add(transaction)
    db.flush()
    return transaction


def make_category(client: TestClient, name: str) -> int:
    return client.post("/api/v1/categories", json={"name": name, "color": "#38bdf8"}).json()["id"]


def make_subcategory(client: TestClient, category_id: int, name: str) -> int:
    return client.post(
        f"/api/v1/categories/{category_id}/subcategories", json={"name": name}
    ).json()["id"]


def make_tag(db: Session, name: str, color: str = "#22d3ee") -> Tag:
    tag = Tag(name=name, color=color)
    db.add(tag)
    db.flush()
    return tag


def attach(db: Session, transaction: Transaction, tag: Tag) -> None:
    db.add(TransactionTag(transaction_id=transaction.id, tag_id=tag.id))
    db.flush()


# --- /stats/by-category -----------------------------------------------------


def test_by_category_splits_income_expenses_and_net(client: TestClient, db: Session) -> None:
    category_id = make_category(client, "Wohnen")
    make_transaction(db, amount="-800.00", composite_hash="a", category_id=category_id)
    make_transaction(db, amount="-200.00", composite_hash="b", category_id=category_id)
    make_transaction(db, amount="150.00", composite_hash="c", category_id=category_id)

    response = client.get("/api/v1/stats/by-category")

    assert response.status_code == 200
    body = response.json()
    entry = next(e for e in body["entries"] if e["category_id"] == category_id)
    assert entry["category_name"] == "Wohnen"
    assert entry["color"] == "#38bdf8"
    assert entry["income"] == "150.00"
    assert entry["expenses"] == "-1000.00"
    assert entry["net"] == "-850.00"
    assert entry["transaction_count"] == 3


def test_by_category_zero_fills_a_bucket_with_only_expenses(
    client: TestClient, db: Session
) -> None:
    """SUM over an empty half is NULL in SQLite; it must surface as 0.00, and as
    euros rather than as the raw integer-cents column."""
    category_id = make_category(client, "Wohnen")
    make_transaction(db, amount="-800.00", composite_hash="a", category_id=category_id)

    body = client.get("/api/v1/stats/by-category").json()

    entry = next(e for e in body["entries"] if e["category_id"] == category_id)
    assert entry["income"] == "0.00"
    assert entry["expenses"] == "-800.00"


def test_by_category_keeps_categories_that_net_positive(client: TestClient, db: Session) -> None:
    """Unlike /stats/summary's pie data, nothing is dropped for its sign."""
    category_id = make_category(client, "Gehalt")
    make_transaction(db, amount="2500.00", composite_hash="a", category_id=category_id)

    body = client.get("/api/v1/stats/by-category").json()

    assert [e["category_name"] for e in body["entries"]] == ["Gehalt"]
    assert body["entries"][0]["net"] == "2500.00"


def test_by_category_unfiled_rows_land_in_the_null_bucket(client: TestClient, db: Session) -> None:
    make_transaction(db, amount="-30.00", composite_hash="a")
    # Unfiled *income* too — /stats/summary drops it, this table must not.
    make_transaction(db, amount="80.00", composite_hash="b")

    body = client.get("/api/v1/stats/by-category").json()

    entry = next(e for e in body["entries"] if e["category_id"] is None)
    assert entry["category_name"] is None
    assert entry["net"] == "50.00"
    assert entry["transaction_count"] == 2


def test_by_category_entries_sum_to_totals(client: TestClient, db: Session) -> None:
    first = make_category(client, "Wohnen")
    second = make_category(client, "Gehalt")
    make_transaction(db, amount="-800.00", composite_hash="a", category_id=first)
    make_transaction(db, amount="2500.00", composite_hash="b", category_id=second)
    make_transaction(db, amount="-30.00", composite_hash="c")

    body = client.get("/api/v1/stats/by-category").json()

    assert sum(Decimal(e["net"]) for e in body["entries"]) == Decimal(body["totals"]["net"])
    assert body["totals"]["net"] == "1670.00"
    assert body["totals"]["income"] == "2500.00"
    assert body["totals"]["expenses"] == "-830.00"
    assert body["totals"]["transaction_count"] == 3


def test_by_category_nests_subcategories_that_sum_to_their_parent(
    client: TestClient, db: Session
) -> None:
    category_id = make_category(client, "Wohnen")
    rent = make_subcategory(client, category_id, "Miete")
    power = make_subcategory(client, category_id, "Strom")
    make_transaction(db, amount="-800.00", composite_hash="a", category_id=category_id, subcategory_id=rent)
    make_transaction(db, amount="-90.00", composite_hash="b", category_id=category_id, subcategory_id=power)
    # No subcategory — the "Ohne Unterkategorie" bucket.
    make_transaction(db, amount="-10.00", composite_hash="c", category_id=category_id)

    body = client.get("/api/v1/stats/by-category").json()

    entry = next(e for e in body["entries"] if e["category_id"] == category_id)
    assert entry["net"] == "-900.00"
    children = {e["subcategory_name"]: e for e in entry["subcategories"]}
    assert children["Miete"]["net"] == "-800.00"
    assert children["Strom"]["net"] == "-90.00"
    assert children[None]["subcategory_id"] is None
    assert children[None]["net"] == "-10.00"
    assert sum(Decimal(e["net"]) for e in entry["subcategories"]) == Decimal(entry["net"])


def test_by_category_orders_biggest_spender_first(client: TestClient, db: Session) -> None:
    small = make_category(client, "Klein")
    big = make_category(client, "Gross")
    income = make_category(client, "Gehalt")
    make_transaction(db, amount="-10.00", composite_hash="a", category_id=small)
    make_transaction(db, amount="-900.00", composite_hash="b", category_id=big)
    make_transaction(db, amount="2500.00", composite_hash="c", category_id=income)

    body = client.get("/api/v1/stats/by-category").json()

    assert [e["category_name"] for e in body["entries"]] == ["Gross", "Klein", "Gehalt"]


def test_by_category_respects_the_date_range(client: TestClient, db: Session) -> None:
    category_id = make_category(client, "Wohnen")
    make_transaction(db, amount="-10.00", when=date(2026, 1, 15), composite_hash="jan", category_id=category_id)
    make_transaction(db, amount="-20.00", when=date(2026, 2, 15), composite_hash="feb", category_id=category_id)

    body = client.get(
        "/api/v1/stats/by-category", params={"date_from": "2026-02-01", "date_to": "2026-02-28"}
    ).json()

    assert body["entries"][0]["net"] == "-20.00"
    assert body["totals"]["transaction_count"] == 1


def test_by_category_drops_excluded_rows_and_internal_transfers(
    client: TestClient, db: Session
) -> None:
    category_id = make_category(client, "Wohnen")
    make_transaction(db, amount="-10.00", composite_hash="counted", category_id=category_id)
    make_transaction(
        db, amount="-999.00", composite_hash="excluded", category_id=category_id, exclude_from_stats=True
    )
    make_transaction(
        db,
        amount="-777.00",
        composite_hash="internal",
        category_id=category_id,
        counter_account="PayPal Europe S.a.r.l. et Cie S.C.A",
    )

    body = client.get("/api/v1/stats/by-category").json()

    assert body["entries"][0]["net"] == "-10.00"
    assert body["totals"]["net"] == "-10.00"


def test_by_category_with_no_transactions(client: TestClient) -> None:
    body = client.get("/api/v1/stats/by-category").json()

    assert body["entries"] == []
    assert body["totals"] == {
        "income": "0.00",
        "expenses": "0.00",
        "net": "0.00",
        "transaction_count": 0,
    }


# --- /stats/by-tag ----------------------------------------------------------


def test_by_tag_reports_per_tag_figures(client: TestClient, db: Session) -> None:
    holiday = make_tag(db, "Urlaub")
    first = make_transaction(db, amount="-100.00", composite_hash="a")
    second = make_transaction(db, amount="-50.00", composite_hash="b")
    attach(db, first, holiday)
    attach(db, second, holiday)

    body = client.get("/api/v1/stats/by-tag").json()

    entry = next(e for e in body["entries"] if e["tag_id"] == holiday.id)
    assert entry["tag_name"] == "Urlaub"
    assert entry["color"] == "#22d3ee"
    assert entry["net"] == "-150.00"
    assert entry["transaction_count"] == 2


def test_by_tag_counts_a_multi_tagged_row_under_each_tag(client: TestClient, db: Session) -> None:
    """The documented overlap: entries deliberately do not sum to totals."""
    holiday = make_tag(db, "Urlaub")
    refund = make_tag(db, "Erstattung")
    transaction = make_transaction(db, amount="-100.00", composite_hash="a")
    attach(db, transaction, holiday)
    attach(db, transaction, refund)

    body = client.get("/api/v1/stats/by-tag").json()

    assert {e["tag_name"]: e["net"] for e in body["entries"]} == {
        "Urlaub": "-100.00",
        "Erstattung": "-100.00",
    }
    assert body["totals"]["net"] == "-100.00"
    assert body["totals"]["transaction_count"] == 1


def test_by_tag_includes_the_untagged_bucket(client: TestClient, db: Session) -> None:
    holiday = make_tag(db, "Urlaub")
    tagged = make_transaction(db, amount="-100.00", composite_hash="a")
    attach(db, tagged, holiday)
    make_transaction(db, amount="-25.00", composite_hash="b")

    body = client.get("/api/v1/stats/by-tag").json()

    untagged = next(e for e in body["entries"] if e["tag_id"] is None)
    assert untagged["tag_name"] is None
    assert untagged["net"] == "-25.00"
    assert untagged["transaction_count"] == 1


def test_by_tag_omits_the_untagged_bucket_when_everything_is_tagged(
    client: TestClient, db: Session
) -> None:
    holiday = make_tag(db, "Urlaub")
    transaction = make_transaction(db, amount="-100.00", composite_hash="a")
    attach(db, transaction, holiday)

    body = client.get("/api/v1/stats/by-tag").json()

    assert [e["tag_id"] for e in body["entries"]] == [holiday.id]


def test_by_tag_drops_excluded_rows_and_internal_transfers(client: TestClient, db: Session) -> None:
    holiday = make_tag(db, "Urlaub")
    counted = make_transaction(db, amount="-10.00", composite_hash="counted")
    excluded = make_transaction(db, amount="-999.00", composite_hash="excluded", exclude_from_stats=True)
    internal = make_transaction(
        db,
        amount="-777.00",
        composite_hash="internal",
        counter_account="PayPal Europe S.a.r.l. et Cie S.C.A",
    )
    for transaction in (counted, excluded, internal):
        attach(db, transaction, holiday)

    body = client.get("/api/v1/stats/by-tag").json()

    entry = next(e for e in body["entries"] if e["tag_id"] == holiday.id)
    assert entry["net"] == "-10.00"
    assert entry["transaction_count"] == 1


def test_by_tag_respects_the_date_range(client: TestClient, db: Session) -> None:
    holiday = make_tag(db, "Urlaub")
    january = make_transaction(db, amount="-10.00", when=date(2026, 1, 15), composite_hash="jan")
    february = make_transaction(db, amount="-20.00", when=date(2026, 2, 15), composite_hash="feb")
    attach(db, january, holiday)
    attach(db, february, holiday)

    body = client.get(
        "/api/v1/stats/by-tag", params={"date_from": "2026-02-01", "date_to": "2026-02-28"}
    ).json()

    entry = next(e for e in body["entries"] if e["tag_id"] == holiday.id)
    assert entry["net"] == "-20.00"


def test_by_tag_with_no_transactions(client: TestClient) -> None:
    body = client.get("/api/v1/stats/by-tag").json()

    assert body["entries"] == []
    assert body["totals"]["transaction_count"] == 0


# --- /stats/trend -----------------------------------------------------------


def test_trend_buckets_by_month(client: TestClient, db: Session) -> None:
    make_transaction(db, amount="-10.00", when=date(2026, 1, 5), composite_hash="a")
    make_transaction(db, amount="-20.00", when=date(2026, 1, 25), composite_hash="b")
    make_transaction(db, amount="100.00", when=date(2026, 3, 1), composite_hash="c")

    body = client.get("/api/v1/stats/trend").json()

    # February is omitted, not padded — the chart fills the gap.
    assert [p["month"] for p in body["points"]] == ["2026-01", "2026-03"]
    assert body["points"][0]["net"] == "-30.00"
    assert body["points"][0]["transaction_count"] == 2
    assert body["points"][1]["income"] == "100.00"
    assert body["totals"]["net"] == "70.00"


def test_trend_filtered_by_category(client: TestClient, db: Session) -> None:
    category_id = make_category(client, "Wohnen")
    make_transaction(db, amount="-800.00", when=date(2026, 1, 5), composite_hash="a", category_id=category_id)
    make_transaction(db, amount="-5.00", when=date(2026, 1, 6), composite_hash="b")

    body = client.get("/api/v1/stats/trend", params={"category_id": category_id}).json()

    assert body["points"] == [
        {
            "month": "2026-01",
            "income": "0.00",
            "expenses": "-800.00",
            "net": "-800.00",
            "transaction_count": 1,
        }
    ]
    assert body["totals"]["net"] == "-800.00"


def test_trend_filtered_by_subcategory(client: TestClient, db: Session) -> None:
    category_id = make_category(client, "Wohnen")
    rent = make_subcategory(client, category_id, "Miete")
    make_transaction(
        db, amount="-800.00", when=date(2026, 1, 5), composite_hash="a", category_id=category_id, subcategory_id=rent
    )
    make_transaction(db, amount="-90.00", when=date(2026, 1, 6), composite_hash="b", category_id=category_id)

    body = client.get("/api/v1/stats/trend", params={"subcategory_id": rent}).json()

    assert body["totals"]["net"] == "-800.00"


def test_trend_filtered_by_uncategorized_and_no_subcategory(client: TestClient, db: Session) -> None:
    category_id = make_category(client, "Wohnen")
    rent = make_subcategory(client, category_id, "Miete")
    make_transaction(
        db, amount="-800.00", when=date(2026, 1, 5), composite_hash="a", category_id=category_id, subcategory_id=rent
    )
    make_transaction(db, amount="-90.00", when=date(2026, 1, 6), composite_hash="b", category_id=category_id)
    make_transaction(db, amount="-7.00", when=date(2026, 1, 7), composite_hash="c")

    filed = client.get(
        "/api/v1/stats/trend", params={"category_id": category_id, "no_subcategory": "true"}
    ).json()
    unfiled = client.get("/api/v1/stats/trend", params={"uncategorized": "true"}).json()

    assert filed["totals"]["net"] == "-90.00"
    assert unfiled["totals"]["net"] == "-7.00"


def test_trend_filtered_by_tag_and_untagged(client: TestClient, db: Session) -> None:
    holiday = make_tag(db, "Urlaub")
    tagged = make_transaction(db, amount="-100.00", when=date(2026, 1, 5), composite_hash="a")
    attach(db, tagged, holiday)
    make_transaction(db, amount="-25.00", when=date(2026, 1, 6), composite_hash="b")

    by_tag = client.get("/api/v1/stats/trend", params={"tag_id": holiday.id}).json()
    untagged = client.get("/api/v1/stats/trend", params={"untagged": "true"}).json()

    assert by_tag["totals"]["net"] == "-100.00"
    assert untagged["totals"]["net"] == "-25.00"


def test_trend_drops_excluded_rows_and_internal_transfers(client: TestClient, db: Session) -> None:
    make_transaction(db, amount="-10.00", when=date(2026, 1, 5), composite_hash="counted")
    make_transaction(
        db, amount="-999.00", when=date(2026, 1, 6), composite_hash="excluded", exclude_from_stats=True
    )
    make_transaction(
        db,
        amount="-777.00",
        when=date(2026, 1, 7),
        composite_hash="internal",
        counter_account="PayPal Europe S.a.r.l. et Cie S.C.A",
    )

    body = client.get("/api/v1/stats/trend").json()

    assert body["totals"]["net"] == "-10.00"
    assert body["points"][0]["transaction_count"] == 1


def test_trend_respects_the_date_range(client: TestClient, db: Session) -> None:
    make_transaction(db, amount="-10.00", when=date(2026, 1, 15), composite_hash="jan")
    make_transaction(db, amount="-20.00", when=date(2026, 2, 15), composite_hash="feb")

    body = client.get(
        "/api/v1/stats/trend", params={"date_from": "2026-02-01", "date_to": "2026-02-28"}
    ).json()

    assert [p["month"] for p in body["points"]] == ["2026-02"]


def test_trend_with_no_matching_rows(client: TestClient) -> None:
    body = client.get("/api/v1/stats/trend", params={"category_id": 999999}).json()

    assert body["points"] == []
    assert body["totals"]["net"] == "0.00"
