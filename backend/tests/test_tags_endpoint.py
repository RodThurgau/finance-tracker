"""Tag CRUD and transaction-tag linking endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Tag, Transaction, TransactionTag


def upload(client: TestClient, path: Path, content_type: str = "text/csv"):
    with path.open("rb") as handle:
        return client.post(
            "/api/v1/import/csv",
            files={"file": (path.name, handle, content_type)},
        )


def make_transaction(db: Session) -> Transaction:
    """One bare transaction row, independent of the CSV fixtures."""
    transaction = Transaction(
        source="ING",
        composite_hash="test-hash",
        date=date(2026, 1, 1),
        description="Testbuchung",
        amount=Decimal("-10.00"),
    )
    db.add(transaction)
    db.flush()
    return transaction


# --- GET/POST/DELETE /tags ---------------------------------------------------


def test_create_tag(client: TestClient) -> None:
    response = client.post("/api/v1/tags", json={"name": "Wiederkehrend", "color": "#818cf8"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Wiederkehrend"
    assert body["color"] == "#818cf8"
    assert "id" in body


def test_create_tag_with_duplicate_name_returns_400(client: TestClient) -> None:
    client.post("/api/v1/tags", json={"name": "Wiederkehrend", "color": "#818cf8"})

    response = client.post("/api/v1/tags", json={"name": "Wiederkehrend", "color": "#000000"})

    assert response.status_code == 400
    assert "detail" in response.json()


def test_list_tags_includes_usage_count(
    client: TestClient, db: Session, fixtures_dir: Path
) -> None:
    upload(client, fixtures_dir / "ing_demo.csv")
    tag = Tag(name="Erstattungsfähig", color="#fbbf24")
    db.add(tag)
    db.flush()
    txns = db.scalars(select(Transaction)).all()[:2]
    for txn in txns:
        db.add(TransactionTag(transaction_id=txn.id, tag_id=tag.id))
    db.flush()
    other = Tag(name="Gemeinsame Ausgabe", color="#22d3ee")
    db.add(other)
    db.flush()

    response = client.get("/api/v1/tags")

    assert response.status_code == 200
    by_name = {t["name"]: t for t in response.json()}
    assert by_name["Erstattungsfähig"]["usage_count"] == 2
    assert by_name["Gemeinsame Ausgabe"]["usage_count"] == 0


def test_update_tag_renames_and_recolors(client: TestClient) -> None:
    tag_id = client.post("/api/v1/tags", json={"name": "Alt", "color": "#000000"}).json()["id"]

    response = client.patch(f"/api/v1/tags/{tag_id}", json={"name": "Neu", "color": "#22d3ee"})

    assert response.status_code == 200
    assert response.json()["name"] == "Neu"
    assert response.json()["color"] == "#22d3ee"


def test_update_tag_keeps_unsent_fields(client: TestClient) -> None:
    tag_id = client.post("/api/v1/tags", json={"name": "Alt", "color": "#22d3ee"}).json()["id"]

    response = client.patch(f"/api/v1/tags/{tag_id}", json={"name": "Neu"})

    assert response.status_code == 200
    assert response.json()["color"] == "#22d3ee"


def test_update_tag_preserves_transaction_assignments(client: TestClient, db: Session) -> None:
    txn = make_transaction(db)
    tag_id = client.post("/api/v1/tags", json={"name": "Alt", "color": "#818cf8"}).json()["id"]
    client.post(f"/api/v1/transactions/{txn.id}/tags", json={"tag_id": tag_id})

    client.patch(f"/api/v1/tags/{tag_id}", json={"name": "Neu"})

    by_name = {t["name"]: t for t in client.get("/api/v1/tags").json()}
    assert by_name["Neu"]["usage_count"] == 1


def test_update_tag_to_duplicate_name_returns_400(client: TestClient) -> None:
    client.post("/api/v1/tags", json={"name": "Wiederkehrend", "color": "#818cf8"})
    tag_id = client.post("/api/v1/tags", json={"name": "Temp", "color": "#000000"}).json()["id"]

    response = client.patch(f"/api/v1/tags/{tag_id}", json={"name": "Wiederkehrend"})

    assert response.status_code == 400
    assert "detail" in response.json()


def test_update_missing_tag_returns_404(client: TestClient) -> None:
    response = client.patch("/api/v1/tags/999999", json={"name": "Neu"})
    assert response.status_code == 404


def test_delete_tag(client: TestClient) -> None:
    tag_id = client.post("/api/v1/tags", json={"name": "Temp", "color": "#000000"}).json()["id"]

    response = client.delete(f"/api/v1/tags/{tag_id}")

    assert response.status_code == 204
    assert client.get("/api/v1/tags").json() == []


def test_delete_missing_tag_returns_404(client: TestClient) -> None:
    response = client.delete("/api/v1/tags/999999")
    assert response.status_code == 404


def test_delete_tag_cascades_transaction_tags(client: TestClient, db: Session) -> None:
    txn = make_transaction(db)
    tag = Tag(name="Wiederkehrend", color="#818cf8")
    db.add(tag)
    db.flush()
    db.add(TransactionTag(transaction_id=txn.id, tag_id=tag.id))
    db.flush()

    response = client.delete(f"/api/v1/tags/{tag.id}")

    assert response.status_code == 204
    remaining = db.scalars(
        select(TransactionTag).where(TransactionTag.tag_id == tag.id)
    ).all()
    assert remaining == []


# --- POST/DELETE /transactions/{id}/tags ------------------------------------


def test_add_tag_to_transaction(client: TestClient, db: Session) -> None:
    txn = make_transaction(db)
    tag_id = client.post("/api/v1/tags", json={"name": "Wiederkehrend", "color": "#818cf8"}).json()[
        "id"
    ]

    response = client.post(f"/api/v1/transactions/{txn.id}/tags", json={"tag_id": tag_id})

    assert response.status_code == 200
    assert [t["id"] for t in response.json()["tags"]] == [tag_id]


def test_add_tag_is_idempotent(client: TestClient, db: Session) -> None:
    txn = make_transaction(db)
    tag_id = client.post("/api/v1/tags", json={"name": "Wiederkehrend", "color": "#818cf8"}).json()[
        "id"
    ]
    client.post(f"/api/v1/transactions/{txn.id}/tags", json={"tag_id": tag_id})

    response = client.post(f"/api/v1/transactions/{txn.id}/tags", json={"tag_id": tag_id})

    assert response.status_code == 200
    assert [t["id"] for t in response.json()["tags"]] == [tag_id]


def test_add_tag_to_missing_transaction_returns_404(client: TestClient) -> None:
    tag_id = client.post("/api/v1/tags", json={"name": "Wiederkehrend", "color": "#818cf8"}).json()[
        "id"
    ]

    response = client.post("/api/v1/transactions/999999/tags", json={"tag_id": tag_id})

    assert response.status_code == 404


def test_add_missing_tag_to_transaction_returns_404(client: TestClient, db: Session) -> None:
    txn = make_transaction(db)

    response = client.post(f"/api/v1/transactions/{txn.id}/tags", json={"tag_id": 999999})

    assert response.status_code == 404


def test_remove_tag_from_transaction(client: TestClient, db: Session) -> None:
    txn = make_transaction(db)
    tag_id = client.post("/api/v1/tags", json={"name": "Wiederkehrend", "color": "#818cf8"}).json()[
        "id"
    ]
    client.post(f"/api/v1/transactions/{txn.id}/tags", json={"tag_id": tag_id})

    response = client.delete(f"/api/v1/transactions/{txn.id}/tags/{tag_id}")

    assert response.status_code == 200
    assert response.json()["tags"] == []


def test_remove_tag_not_attached_is_a_noop(client: TestClient, db: Session) -> None:
    txn = make_transaction(db)
    tag_id = client.post("/api/v1/tags", json={"name": "Wiederkehrend", "color": "#818cf8"}).json()[
        "id"
    ]

    response = client.delete(f"/api/v1/transactions/{txn.id}/tags/{tag_id}")

    assert response.status_code == 200
    assert response.json()["tags"] == []


def test_remove_tag_from_missing_transaction_returns_404(client: TestClient) -> None:
    response = client.delete("/api/v1/transactions/999999/tags/1")
    assert response.status_code == 404
