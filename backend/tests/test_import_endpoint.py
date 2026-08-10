"""POST /api/v1/import/csv — the full preclean → detect → parse → upsert path."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Transaction


def upload(client: TestClient, path: Path, content_type: str = "text/csv"):
    with path.open("rb") as handle:
        return client.post(
            "/api/v1/import/csv",
            files={"file": (path.name, handle, content_type)},
        )


def preview(client: TestClient, path: Path, content_type: str = "text/csv"):
    with path.open("rb") as handle:
        return client.post(
            "/api/v1/import/preview",
            files={"file": (path.name, handle, content_type)},
        )


def test_import_ing_demo(client: TestClient, db: Session, fixtures_dir: Path) -> None:
    response = upload(client, fixtures_dir / "ing_demo.csv")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "ING"
    assert (body["new"], body["updated"], body["skipped"]) == (7, 0, 0)
    assert body["errors"] == []
    assert body["date_range"] == ["2026-07-01", "2026-07-31"]
    assert db.scalar(select(func.count()).select_from(Transaction)) == 7


def test_import_paypal_demo(client: TestClient, db: Session, fixtures_dir: Path) -> None:
    response = upload(client, fixtures_dir / "paypal_demo.CSV")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "PayPal"
    assert (body["new"], body["updated"], body["skipped"]) == (9, 0, 0)
    assert db.scalar(select(func.count()).select_from(Transaction)) == 9


def test_reimport_reports_skipped_rows_as_strings(
    client: TestClient, fixtures_dir: Path
) -> None:
    upload(client, fixtures_dir / "ing_demo.csv")

    body = upload(client, fixtures_dir / "ing_demo.csv").json()

    assert body["skipped"] == 7
    assert len(body["skipped_rows"]) == 7
    first = body["skipped_rows"][0]
    assert isinstance(first["amount"], str)
    assert first["amount"] == "-15.26"


def test_malformed_rows_surface_as_errors(client: TestClient, generated_dir: Path) -> None:
    body = upload(client, generated_dir / "ing_malformed_row.csv").json()

    assert [(e["row_number"], e["column"]) for e in body["errors"]] == [
        (8, "Buchung"),
        (9, "Betrag"),
    ]


def test_no_header_found_returns_422_with_preamble(
    client: TestClient, generated_dir: Path
) -> None:
    response = upload(client, generated_dir / "not_a_csv.txt", content_type="text/plain")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert "Dies ist keine CSV-Datei" in detail


def test_preview_ing_demo_does_not_write_to_db(
    client: TestClient, db: Session, fixtures_dir: Path
) -> None:
    response = preview(client, fixtures_dir / "ing_demo.csv")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "ING"
    assert body["total_rows"] == 7
    assert len(body["rows"]) == 5  # capped, even though 7 rows parsed
    assert isinstance(body["rows"][0]["amount"], str)
    assert body["errors"] == []
    assert db.scalar(select(func.count()).select_from(Transaction)) == 0


def test_preview_reports_preamble_lines(client: TestClient, fixtures_dir: Path) -> None:
    body = preview(client, fixtures_dir / "ing_demo.csv").json()

    assert isinstance(body["preamble_lines"], list)
    assert len(body["preamble_lines"]) > 0


def test_preview_reports_malformed_rows_without_dropping_good_ones(
    client: TestClient, generated_dir: Path
) -> None:
    body = preview(client, generated_dir / "ing_malformed_row.csv").json()

    assert [(e["row_number"], e["column"]) for e in body["errors"]] == [
        (8, "Buchung"),
        (9, "Betrag"),
    ]


def test_preview_no_header_found_returns_422(client: TestClient, generated_dir: Path) -> None:
    response = preview(client, generated_dir / "not_a_csv.txt", content_type="text/plain")

    assert response.status_code == 422
    assert "Dies ist keine CSV-Datei" in response.json()["detail"]


def test_second_import_of_paypal_updates_in_place(
    client: TestClient, fixtures_dir: Path, generated_dir: Path
) -> None:
    upload(client, fixtures_dir / "paypal_demo.CSV")

    body = upload(client, generated_dir / "paypal_reimport_overlap.csv").json()

    assert body["updated"] == 9
    assert body["new"] == 1
