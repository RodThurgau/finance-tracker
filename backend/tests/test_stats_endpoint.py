"""GET /api/v1/stats/summary — totals, category/month breakdowns, top merchants,
and the exclude_from_stats gate that must apply to every one of them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Transaction


def make_transaction(
    db: Session,
    *,
    amount: str,
    when: date,
    composite_hash: str,
    description: str = "Testbuchung",
    counter_account: str | None = None,
    category_id: int | None = None,
    exclude_from_stats: bool = False,
) -> Transaction:
    transaction = Transaction(
        source="ING",
        composite_hash=composite_hash,
        date=when,
        description=description,
        amount=Decimal(amount),
        counter_account=counter_account,
        category_id=category_id,
        exclude_from_stats=exclude_from_stats,
    )
    db.add(transaction)
    db.flush()
    return transaction


def make_category(client: TestClient, name: str = "Testkategorie") -> int:
    return client.post("/api/v1/categories", json={"name": name, "color": "#38bdf8"}).json()["id"]


def test_totals_and_net(client: TestClient, db: Session) -> None:
    make_transaction(db, amount="1000.00", when=date(2026, 1, 5), composite_hash="a")
    make_transaction(db, amount="-40.00", when=date(2026, 1, 6), composite_hash="b")
    make_transaction(db, amount="-10.00", when=date(2026, 1, 7), composite_hash="c")

    response = client.get("/api/v1/stats/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_income"] == "1000.00"
    assert body["total_expenses"] == "-50.00"
    assert body["net"] == "950.00"
    assert all(isinstance(v, str) for v in (body["total_income"], body["total_expenses"], body["net"]))


def test_totals_default_to_zero_with_no_transactions(client: TestClient) -> None:
    response = client.get("/api/v1/stats/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_income"] == "0.00"
    assert body["total_expenses"] == "0.00"
    assert body["net"] == "0.00"
    assert body["by_category"] == []
    assert body["by_month"] == []
    assert body["top_merchants"] == []


def test_date_range_filters(client: TestClient, db: Session) -> None:
    make_transaction(db, amount="-10.00", when=date(2026, 1, 15), composite_hash="jan")
    make_transaction(db, amount="-20.00", when=date(2026, 2, 15), composite_hash="feb")

    response = client.get(
        "/api/v1/stats/summary", params={"date_from": "2026-02-01", "date_to": "2026-02-28"}
    )

    assert response.status_code == 200
    assert response.json()["total_expenses"] == "-20.00"


def test_by_category_includes_uncategorized_bucket_and_sums_correctly(
    client: TestClient, db: Session
) -> None:
    category_id = make_category(client, "Einkaufen")
    make_transaction(db, amount="-30.00", when=date(2026, 1, 1), composite_hash="a", category_id=category_id)
    make_transaction(db, amount="-20.00", when=date(2026, 1, 2), composite_hash="b", category_id=category_id)
    make_transaction(db, amount="-5.00", when=date(2026, 1, 3), composite_hash="c", category_id=None)

    response = client.get("/api/v1/stats/summary")

    assert response.status_code == 200
    by_category = response.json()["by_category"]
    by_id = {entry["category_id"]: entry for entry in by_category}
    assert by_id[category_id]["category_name"] == "Einkaufen"
    assert by_id[category_id]["total"] == "-50.00"
    assert by_id[None]["category_name"] is None
    assert by_id[None]["total"] == "-5.00"


def test_by_category_omits_a_category_that_only_earned(client: TestClient, db: Session) -> None:
    """A category netting above zero is not spending and has no pie slice."""
    category_id = make_category(client, "Einkommen")
    make_transaction(db, amount="2000.00", when=date(2026, 1, 1), composite_hash="a", category_id=category_id)

    response = client.get("/api/v1/stats/summary")

    assert response.json()["by_category"] == []


def test_by_category_nets_income_against_spending_in_the_same_category(
    client: TestClient, db: Session
) -> None:
    """Rent paid in full, partly paid back, reports what it actually cost."""
    category_id = make_category(client, "Wohnen")
    make_transaction(
        db, amount="-1200.00", when=date(2026, 1, 1), composite_hash="rent", category_id=category_id
    )
    make_transaction(
        db, amount="450.00", when=date(2026, 1, 3), composite_hash="repaid", category_id=category_id
    )

    by_category = client.get("/api/v1/stats/summary").json()["by_category"]

    assert [entry["total"] for entry in by_category] == ["-750.00"]


def test_by_category_netting_is_per_category(client: TestClient, db: Session) -> None:
    """A reimbursement only offsets the category it is filed under."""
    housing = make_category(client, "Wohnen")
    food = make_category(client, "Essen")
    make_transaction(
        db, amount="-1200.00", when=date(2026, 1, 1), composite_hash="rent", category_id=housing
    )
    make_transaction(
        db, amount="450.00", when=date(2026, 1, 3), composite_hash="repaid", category_id=housing
    )
    make_transaction(
        db, amount="-80.00", when=date(2026, 1, 4), composite_hash="food", category_id=food
    )

    by_id = {
        entry["category_id"]: entry["total"]
        for entry in client.get("/api/v1/stats/summary").json()["by_category"]
    }

    assert by_id[housing] == "-750.00"
    assert by_id[food] == "-80.00"


def test_by_category_drops_a_fully_reimbursed_category(client: TestClient, db: Session) -> None:
    """Netting exactly to zero means nothing was spent — no slice."""
    category_id = make_category(client, "Wohnen")
    make_transaction(
        db, amount="-500.00", when=date(2026, 1, 1), composite_hash="paid", category_id=category_id
    )
    make_transaction(
        db, amount="500.00", when=date(2026, 1, 2), composite_hash="back", category_id=category_id
    )

    assert client.get("/api/v1/stats/summary").json()["by_category"] == []


def test_total_expenses_stays_gross_while_by_category_nets(
    client: TestClient, db: Session
) -> None:
    """The two figures answer different questions and no longer reconcile —
    pinned so the divergence stays deliberate rather than becoming a surprise."""
    category_id = make_category(client, "Wohnen")
    make_transaction(
        db, amount="-1200.00", when=date(2026, 1, 1), composite_hash="rent", category_id=category_id
    )
    make_transaction(
        db, amount="450.00", when=date(2026, 1, 3), composite_hash="repaid", category_id=category_id
    )

    body = client.get("/api/v1/stats/summary").json()

    assert body["total_expenses"] == "-1200.00"
    assert body["by_category"][0]["total"] == "-750.00"


def test_uncategorized_bucket_stays_gross(client: TestClient, db: Session) -> None:
    """The unfiled bucket is not a budget, so income there is not a
    reimbursement of anything. Netting it would cancel an uncategorized salary
    against uncategorized spending and drop the bucket from the chart exactly
    when it most needs attention."""
    make_transaction(db, amount="-100.00", when=date(2026, 1, 1), composite_hash="a")
    make_transaction(db, amount="5000.00", when=date(2026, 1, 2), composite_hash="salary")

    by_category = client.get("/api/v1/stats/summary").json()["by_category"]

    assert [(entry["category_id"], entry["total"]) for entry in by_category] == [(None, "-100.00")]


def test_by_month_splits_income_and_expenses(client: TestClient, db: Session) -> None:
    make_transaction(db, amount="1000.00", when=date(2026, 1, 5), composite_hash="a")
    make_transaction(db, amount="-100.00", when=date(2026, 1, 20), composite_hash="b")
    make_transaction(db, amount="-50.00", when=date(2026, 2, 3), composite_hash="c")

    response = client.get("/api/v1/stats/summary")

    by_month = {e["month"]: e for e in response.json()["by_month"]}
    assert by_month["2026-01"]["income"] == "1000.00"
    assert by_month["2026-01"]["expenses"] == "-100.00"
    assert by_month["2026-02"]["income"] == "0.00"
    assert by_month["2026-02"]["expenses"] == "-50.00"


def test_top_merchants_groups_by_counter_account_and_orders_by_spend(
    client: TestClient, db: Session
) -> None:
    make_transaction(db, amount="-30.00", when=date(2026, 1, 1), composite_hash="a", counter_account="Rewe")
    make_transaction(db, amount="-20.00", when=date(2026, 1, 2), composite_hash="b", counter_account="Rewe")
    make_transaction(db, amount="-100.00", when=date(2026, 1, 3), composite_hash="c", counter_account="Vermieter GmbH")
    make_transaction(db, amount="-1.00", when=date(2026, 1, 4), composite_hash="d", counter_account=None)

    response = client.get("/api/v1/stats/summary")

    top_merchants = response.json()["top_merchants"]
    assert [m["counter_account"] for m in top_merchants] == ["Vermieter GmbH", "Rewe"]
    assert top_merchants[0]["total"] == "-100.00"
    assert top_merchants[1]["total"] == "-50.00"
    assert None not in [m["counter_account"] for m in top_merchants]


def test_top_merchants_is_limited_to_ten(client: TestClient, db: Session) -> None:
    for i in range(12):
        make_transaction(
            db,
            amount="-5.00",
            when=date(2026, 1, 1),
            composite_hash=f"m{i}",
            counter_account=f"Merchant {i}",
        )

    response = client.get("/api/v1/stats/summary")

    assert len(response.json()["top_merchants"]) == 10


def test_excluded_row_changes_every_figure(client: TestClient, db: Session) -> None:
    category_id = make_category(client, "Einkaufen")
    make_transaction(
        db,
        amount="1000.00",
        when=date(2026, 1, 5),
        composite_hash="income",
    )
    excluded = make_transaction(
        db,
        amount="-100.00",
        when=date(2026, 1, 10),
        composite_hash="excluded-candidate",
        counter_account="Rewe",
        category_id=category_id,
    )

    before = client.get("/api/v1/stats/summary").json()
    assert before["total_expenses"] == "-100.00"
    assert before["net"] == "900.00"
    assert before["by_category"][0]["total"] == "-100.00"
    assert before["by_month"][0]["expenses"] == "-100.00"
    assert before["top_merchants"][0]["total"] == "-100.00"

    excluded.exclude_from_stats = True
    db.flush()

    after = client.get("/api/v1/stats/summary").json()
    assert after["total_expenses"] == "0.00"
    assert after["net"] == "1000.00"
    assert after["by_category"] == []
    assert after["by_month"][0]["expenses"] == "0.00"
    assert after["top_merchants"] == []


def test_no_query_parameter_can_override_the_exclude_gate(client: TestClient, db: Session) -> None:
    """CLAUDE.md: 'No exceptions, no query parameter to override it.'"""
    make_transaction(
        db,
        amount="-100.00",
        when=date(2026, 1, 10),
        composite_hash="excluded",
        exclude_from_stats=True,
    )

    response = client.get(
        "/api/v1/stats/summary",
        params={"excluded": "true", "exclude_from_stats": "false", "include_excluded": "true"},
    )

    assert response.status_code == 200
    assert response.json()["total_expenses"] == "0.00"
