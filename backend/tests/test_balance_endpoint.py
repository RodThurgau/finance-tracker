"""GET /api/v1/stats/balance — the anchored running balance."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import balance as balance_module
from balance import BalanceAnchor
from models import Transaction

ANCHOR_DATE = date(2026, 8, 10)
ANCHOR_BALANCE = Decimal("1608.90")


@pytest.fixture(autouse=True)
def one_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the anchors so these tests don't drift when the real list grows."""
    monkeypatch.setattr(
        balance_module, "BALANCE_ANCHORS", [BalanceAnchor(ANCHOR_DATE, ANCHOR_BALANCE)]
    )


def add(db: Session, on: date, amount: str, **kwargs) -> Transaction:
    transaction = Transaction(
        source=kwargs.pop("source", "ING"),
        composite_hash=f"hash-{on}-{amount}-{kwargs.get('counter_account', '')}",
        date=on,
        description="Testbuchung",
        amount=Decimal(amount),
        **kwargs,
    )
    db.add(transaction)
    db.flush()
    return transaction


def get_balance(client: TestClient) -> dict:
    response = client.get("/api/v1/stats/balance")
    assert response.status_code == 200
    return response.json()


def test_balance_is_the_anchor_when_nothing_is_newer(client: TestClient, db: Session) -> None:
    add(db, date(2026, 8, 1), "-50.00")

    body = get_balance(client)

    assert Decimal(body["current_balance"]) == ANCHOR_BALANCE
    assert body["as_of"] == "2026-08-10"


def test_movements_after_the_anchor_move_the_balance(client: TestClient, db: Session) -> None:
    add(db, date(2026, 8, 11), "-100.00")
    add(db, date(2026, 8, 12), "25.50")

    body = get_balance(client)

    assert Decimal(body["current_balance"]) == ANCHOR_BALANCE - Decimal("74.50")
    assert body["as_of"] == "2026-08-12"


def test_a_movement_on_the_anchor_day_is_already_included(
    client: TestClient, db: Session
) -> None:
    """The anchor is an end-of-day figure, so same-day rows must not be added
    on top of it — that would count them twice."""
    add(db, ANCHOR_DATE, "-500.00")

    body = get_balance(client)

    assert Decimal(body["current_balance"]) == ANCHOR_BALANCE


def test_implied_opening_balance_reverses_the_recorded_movements(
    client: TestClient, db: Session
) -> None:
    add(db, date(2026, 7, 1), "-200.00")
    add(db, date(2026, 7, 2), "50.00")

    body = get_balance(client)

    # 1608.90 back out -150.00 of net movement => 1758.90 before it all started.
    assert Decimal(body["implied_opening_balance"]) == Decimal("1758.90")
    assert body["opening_date"] == "2026-07-01"


def test_internal_transfers_do_not_move_the_balance(client: TestClient, db: Session) -> None:
    """A PayPal purchase and the ING debit settling it are the same money; the
    balance must fall by the amount once, not twice."""
    add(db, date(2026, 8, 11), "-37.50", source="PayPal", transaction_id="purchase")
    add(
        db,
        date(2026, 8, 11),
        "37.50",
        source="PayPal",
        transaction_id="funding",
        transaction_type="Bankgutschrift auf PayPal-Konto",
    )
    add(db, date(2026, 8, 11), "-37.50", counter_account="PayPal Europe S.a.r.l. et Cie S.C.A")

    body = get_balance(client)

    assert Decimal(body["current_balance"]) == ANCHOR_BALANCE - Decimal("37.50")


def test_excluded_rows_do_not_move_the_balance(client: TestClient, db: Session) -> None:
    add(db, date(2026, 8, 11), "-99.00", exclude_from_stats=True)

    body = get_balance(client)

    assert Decimal(body["current_balance"]) == ANCHOR_BALANCE


def test_no_transactions_yields_the_anchor_and_no_opening_balance(client: TestClient) -> None:
    body = get_balance(client)

    assert Decimal(body["current_balance"]) == ANCHOR_BALANCE
    assert body["opening_date"] is None
    assert body["implied_opening_balance"] is None


def test_single_anchor_has_nothing_to_check(client: TestClient) -> None:
    assert get_balance(client)["checks"] == []


def test_second_anchor_reports_zero_drift_when_the_data_is_complete(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        balance_module,
        "BALANCE_ANCHORS",
        [
            BalanceAnchor(date(2026, 8, 10), Decimal("1608.90")),
            BalanceAnchor(date(2026, 8, 31), Decimal("1408.90")),
        ],
    )
    add(db, date(2026, 8, 15), "-200.00")

    checks = get_balance(client)["checks"]

    assert len(checks) == 1
    assert Decimal(checks[0]["drift"]) == Decimal("0.00")
    assert checks[0]["on"] == "2026-08-31"


def test_second_anchor_surfaces_missing_data_as_drift(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reason for keeping more than one anchor: a gap in the imported data
    shows up as a number instead of going unnoticed."""
    monkeypatch.setattr(
        balance_module,
        "BALANCE_ANCHORS",
        [
            BalanceAnchor(date(2026, 8, 10), Decimal("1608.90")),
            BalanceAnchor(date(2026, 8, 31), Decimal("1408.90")),
        ],
    )
    # Only half the spending that really happened got imported.
    add(db, date(2026, 8, 15), "-100.00")

    checks = get_balance(client)["checks"]

    assert Decimal(checks[0]["expected"]) == Decimal("1508.90")
    assert Decimal(checks[0]["actual"]) == Decimal("1408.90")
    assert Decimal(checks[0]["drift"]) == Decimal("-100.00")
