"""Internal transfers: the funding legs of a PayPal purchase.

Covers the shared predicate in `services/internal_transfers.py` through the
three endpoints that consume it — the transaction list, the CSV export, and
`/stats/summary`.

The demo fixtures already carry both legs: `ing_demo.csv` has one
`PayPal Europe S.a.r.l. et Cie S.C.A.` debit, and `paypal_demo.CSV` has three
`Bankgutschrift auf PayPal-Konto` credits.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Transaction

ING_INTERNAL_ROWS = 1
PAYPAL_INTERNAL_ROWS = 3


def upload(client: TestClient, path: Path) -> None:
    with path.open("rb") as handle:
        client.post("/api/v1/import/csv", files={"file": (path.name, handle, "text/csv")})


def import_both(client: TestClient, fixtures_dir: Path) -> None:
    upload(client, fixtures_dir / "ing_demo.csv")
    upload(client, fixtures_dir / "paypal_demo.CSV")


# --- transaction list --------------------------------------------------------


def test_list_hides_internal_transfers_by_default(
    client: TestClient, fixtures_dir: Path
) -> None:
    import_both(client, fixtures_dir)

    everything = client.get("/api/v1/transactions", params={"internal": "show"}).json()
    default = client.get("/api/v1/transactions").json()

    assert default["total"] == everything["total"] - ING_INTERNAL_ROWS - PAYPAL_INTERNAL_ROWS
    descriptions = [row["description"] for row in default["items"]]
    assert not any("Bankgutschrift auf PayPal-Konto" in text for text in descriptions)
    assert not any("PayPal Europe" in text for text in descriptions)


def test_list_internal_only_returns_just_the_funding_legs(
    client: TestClient, fixtures_dir: Path
) -> None:
    import_both(client, fixtures_dir)

    response = client.get("/api/v1/transactions", params={"internal": "only", "page_size": 100})

    body = response.json()
    assert body["total"] == ING_INTERNAL_ROWS + PAYPAL_INTERNAL_ROWS
    for row in body["items"]:
        if row["source"] == "ING":
            assert "paypal" in row["counter_account"].lower()
        else:
            assert row["transaction_type"] == "Bankgutschrift auf PayPal-Konto"


def test_internal_filter_combines_with_other_filters(
    client: TestClient, fixtures_dir: Path
) -> None:
    """The predicate is ANDed in, not applied as a separate pass."""
    import_both(client, fixtures_dir)

    response = client.get(
        "/api/v1/transactions", params={"internal": "only", "source": "PayPal", "page_size": 100}
    )

    body = response.json()
    assert body["total"] == PAYPAL_INTERNAL_ROWS
    assert {row["source"] for row in body["items"]} == {"PayPal"}


def test_rows_without_a_counterparty_are_not_hidden(client: TestClient, db: Session) -> None:
    """Regression: `NULL ILIKE …` is NULL, and a NULL inside the predicate would
    make its negation NULL too, dropping every counterparty-less row from the
    list. ING books securities trades with no `Auftraggeber/Empfänger` at all."""
    db.add(
        Transaction(
            source="ING",
            composite_hash="no-counterparty",
            date=date(2026, 7, 1),
            description="WP-ABRECHNUNG Kauf ISIN IE00BK5BQT80",
            amount=Decimal("-10.00"),
            counter_account=None,
            transaction_type="Wertpapierkauf",
        )
    )
    db.flush()

    body = client.get("/api/v1/transactions").json()

    assert body["total"] == 1
    assert body["items"][0]["counter_account"] is None


def test_paypal_purchase_survives_while_its_funding_leg_is_hidden(
    client: TestClient, fixtures_dir: Path
) -> None:
    """The point of the feature: one copy of the amount is kept, and it is the
    one carrying the real merchant name."""
    upload(client, fixtures_dir / "paypal_demo.CSV")

    body = client.get("/api/v1/transactions", params={"page_size": 100}).json()

    descriptions = [row["description"] for row in body["items"]]
    assert "Taxi Nordstern GmbH" in " ".join(descriptions)
    assert "Bankgutschrift auf PayPal-Konto" not in descriptions


# --- stats -------------------------------------------------------------------


def test_stats_excludes_internal_transfers(client: TestClient, fixtures_dir: Path) -> None:
    """The PayPal funding credits are all positive, so counting them would
    inflate income by exactly their sum: 7,25 + 42,00 + 31,50 = 80,75.

    The 5,50 that remains is `Rückbuchung allgemeiner Einbehaltung`, the
    reversal of an authorization hold. It nets to zero against its own
    `Einbehaltung für offene Autorisierung` counterpart but is *not* one of the
    funding legs this feature filters — it is the known out-of-scope case
    recorded under "Open" in CHANGELOG.md. Pinning the number here means
    widening the definition later has to come past this test.
    """
    upload(client, fixtures_dir / "paypal_demo.CSV")

    summary = client.get("/api/v1/stats/summary").json()

    assert Decimal(summary["total_income"]) == Decimal("5.50")


def test_stats_excludes_ing_paypal_funding_debit(
    client: TestClient, fixtures_dir: Path
) -> None:
    upload(client, fixtures_dir / "ing_demo.csv")

    summary = client.get("/api/v1/stats/summary").json()

    merchants = [entry["counter_account"] for entry in summary["top_merchants"]]
    assert not any("PayPal" in name for name in merchants)


def test_stats_has_no_override_parameter(client: TestClient, fixtures_dir: Path) -> None:
    """Mirrors `exclude_from_stats`: unknown query params must not reopen the gate."""
    upload(client, fixtures_dir / "paypal_demo.CSV")

    with_param = client.get("/api/v1/stats/summary", params={"internal": "show"}).json()
    without = client.get("/api/v1/stats/summary").json()

    assert with_param == without


# --- export ------------------------------------------------------------------


def export_rows(client: TestClient, **params: str) -> list[dict[str, str]]:
    response = client.get("/api/v1/export/csv", params=params)
    assert response.status_code == 200
    return list(csv.DictReader(io.StringIO(response.text)))


def test_export_hides_internal_transfers_by_default(
    client: TestClient, fixtures_dir: Path
) -> None:
    import_both(client, fixtures_dir)

    rows = export_rows(client)

    assert not any(row["transaction_type"] == "Bankgutschrift auf PayPal-Konto" for row in rows)
    assert not any("PayPal Europe" in row["counter_account"] for row in rows)


def test_export_can_include_internal_transfers(client: TestClient, fixtures_dir: Path) -> None:
    import_both(client, fixtures_dir)

    default = export_rows(client)
    everything = export_rows(client, internal="show")

    assert len(everything) == len(default) + ING_INTERNAL_ROWS + PAYPAL_INTERNAL_ROWS
