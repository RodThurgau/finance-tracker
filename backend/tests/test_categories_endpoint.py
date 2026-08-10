"""Category and subcategory CRUD, including the delete-cascade rules from
CLAUDE.md's "Deleting a category" section.

The PLAN.md 2.3 checklist item that runs `/rules/apply` after deleting a
category is deferred: that endpoint belongs to 2.4 and doesn't exist yet.
This file covers everything else in 2.3, including the category-delete side
of that scenario (category_id/subcategory_id/user_categorized reset) without
the rules-apply step.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Category, Subcategory, Transaction


def make_transaction(
    db: Session,
    *,
    category_id: int | None = None,
    subcategory_id: int | None = None,
    user_categorized: bool = False,
    composite_hash: str = "test-hash",
) -> Transaction:
    transaction = Transaction(
        source="ING",
        composite_hash=composite_hash,
        date=date(2026, 1, 1),
        description="Testbuchung",
        amount=Decimal("-10.00"),
        category_id=category_id,
        subcategory_id=subcategory_id,
        user_categorized=user_categorized,
    )
    db.add(transaction)
    db.flush()
    return transaction


# --- GET/POST/PATCH/DELETE /categories --------------------------------------


def test_create_category(client: TestClient) -> None:
    response = client.post("/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Wohnen"
    assert body["color"] == "#38bdf8"
    assert body["subcategories"] == []


def test_create_category_with_duplicate_name_returns_400(client: TestClient) -> None:
    client.post("/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"})

    response = client.post("/api/v1/categories", json={"name": "Wohnen", "color": "#000000"})

    assert response.status_code == 400
    assert "detail" in response.json()


def test_list_categories_includes_nested_subcategories_and_counts(
    client: TestClient, db: Session
) -> None:
    category_id = client.post(
        "/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"}
    ).json()["id"]
    client.post(f"/api/v1/categories/{category_id}/subcategories", json={"name": "Miete"})
    make_transaction(db, category_id=category_id, composite_hash="h1")
    make_transaction(db, category_id=category_id, composite_hash="h2")
    other_id = client.post(
        "/api/v1/categories", json={"name": "Transport", "color": "#a78bfa"}
    ).json()["id"]

    response = client.get("/api/v1/categories")

    assert response.status_code == 200
    by_name = {c["name"]: c for c in response.json()}
    assert [s["name"] for s in by_name["Wohnen"]["subcategories"]] == ["Miete"]
    assert by_name["Wohnen"]["transaction_count"] == 2
    assert by_name["Transport"]["transaction_count"] == 0
    assert by_name["Transport"]["subcategories"] == []


def test_patch_renames_and_recolors_category(client: TestClient) -> None:
    category_id = client.post(
        "/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"}
    ).json()["id"]

    response = client.patch(
        f"/api/v1/categories/{category_id}", json={"name": "Miete & Wohnen", "color": "#000000"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Miete & Wohnen"
    assert body["color"] == "#000000"


def test_patch_partial_update_only_touches_given_field(client: TestClient) -> None:
    category_id = client.post(
        "/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"}
    ).json()["id"]

    response = client.patch(f"/api/v1/categories/{category_id}", json={"color": "#000000"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Wohnen"
    assert body["color"] == "#000000"


def test_patch_missing_category_returns_404(client: TestClient) -> None:
    response = client.patch("/api/v1/categories/999999", json={"name": "X"})
    assert response.status_code == 404


def test_patch_rename_to_existing_name_returns_400(client: TestClient) -> None:
    client.post("/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"})
    other_id = client.post(
        "/api/v1/categories", json={"name": "Transport", "color": "#a78bfa"}
    ).json()["id"]

    response = client.patch(f"/api/v1/categories/{other_id}", json={"name": "Wohnen"})

    assert response.status_code == 400


def test_delete_category_resets_affected_transactions(client: TestClient, db: Session) -> None:
    category_id = client.post(
        "/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"}
    ).json()["id"]
    subcategory_id = client.post(
        f"/api/v1/categories/{category_id}/subcategories", json={"name": "Miete"}
    ).json()["id"]
    txn = make_transaction(
        db, category_id=category_id, subcategory_id=subcategory_id, user_categorized=True
    )
    other_txn = make_transaction(db, composite_hash="unrelated")

    response = client.delete(f"/api/v1/categories/{category_id}")

    assert response.status_code == 204
    db.refresh(txn)
    assert txn.category_id is None
    assert txn.subcategory_id is None
    assert txn.user_categorized is False
    db.refresh(other_txn)
    assert other_txn.category_id is None  # untouched, was already None


def test_delete_category_cascades_its_subcategories(client: TestClient, db: Session) -> None:
    category_id = client.post(
        "/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"}
    ).json()["id"]
    subcategory_id = client.post(
        f"/api/v1/categories/{category_id}/subcategories", json={"name": "Miete"}
    ).json()["id"]

    response = client.delete(f"/api/v1/categories/{category_id}")

    assert response.status_code == 204
    assert db.get(Subcategory, subcategory_id) is None


def test_delete_missing_category_returns_404(client: TestClient) -> None:
    response = client.delete("/api/v1/categories/999999")
    assert response.status_code == 404


# --- POST /categories/{id}/subcategories, DELETE /subcategories/{id} -------


def test_create_subcategory(client: TestClient) -> None:
    category_id = client.post(
        "/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"}
    ).json()["id"]

    response = client.post(f"/api/v1/categories/{category_id}/subcategories", json={"name": "Miete"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Miete"
    assert body["category_id"] == category_id


def test_create_subcategory_under_missing_category_returns_404(client: TestClient) -> None:
    response = client.post("/api/v1/categories/999999/subcategories", json={"name": "Miete"})
    assert response.status_code == 404


def test_create_subcategory_duplicate_name_in_same_category_returns_400(
    client: TestClient,
) -> None:
    category_id = client.post(
        "/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"}
    ).json()["id"]
    client.post(f"/api/v1/categories/{category_id}/subcategories", json={"name": "Miete"})

    response = client.post(f"/api/v1/categories/{category_id}/subcategories", json={"name": "Miete"})

    assert response.status_code == 400


def test_create_subcategory_same_name_allowed_in_different_category(client: TestClient) -> None:
    a = client.post("/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"}).json()["id"]
    b = client.post("/api/v1/categories", json={"name": "Transport", "color": "#a78bfa"}).json()[
        "id"
    ]
    client.post(f"/api/v1/categories/{a}/subcategories", json={"name": "Sonstiges"})

    response = client.post(f"/api/v1/categories/{b}/subcategories", json={"name": "Sonstiges"})

    assert response.status_code == 201


def test_delete_subcategory_missing_returns_404(client: TestClient) -> None:
    response = client.delete("/api/v1/subcategories/999999")
    assert response.status_code == 404


def test_delete_subcategory_clears_subcategory_id_but_keeps_user_categorized_when_category_remains(
    client: TestClient, db: Session
) -> None:
    category_id = client.post(
        "/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"}
    ).json()["id"]
    subcategory_id = client.post(
        f"/api/v1/categories/{category_id}/subcategories", json={"name": "Miete"}
    ).json()["id"]
    txn = make_transaction(
        db, category_id=category_id, subcategory_id=subcategory_id, user_categorized=True
    )

    response = client.delete(f"/api/v1/subcategories/{subcategory_id}")

    assert response.status_code == 204
    db.refresh(txn)
    assert txn.subcategory_id is None
    assert txn.category_id == category_id
    assert txn.user_categorized is True  # category_id still set, so the flag is left alone


def test_delete_subcategory_clears_user_categorized_when_category_id_also_none(
    client: TestClient, db: Session
) -> None:
    category_id = client.post(
        "/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"}
    ).json()["id"]
    subcategory_id = client.post(
        f"/api/v1/categories/{category_id}/subcategories", json={"name": "Miete"}
    ).json()["id"]
    # category_id left None on purpose to exercise the "also NULL" clause.
    txn = make_transaction(db, category_id=None, subcategory_id=subcategory_id, user_categorized=True)

    response = client.delete(f"/api/v1/subcategories/{subcategory_id}")

    assert response.status_code == 204
    db.refresh(txn)
    assert txn.subcategory_id is None
    assert txn.category_id is None
    assert txn.user_categorized is False


def test_delete_subcategory_does_not_delete_its_category(client: TestClient, db: Session) -> None:
    category_id = client.post(
        "/api/v1/categories", json={"name": "Wohnen", "color": "#38bdf8"}
    ).json()["id"]
    subcategory_id = client.post(
        f"/api/v1/categories/{category_id}/subcategories", json={"name": "Miete"}
    ).json()["id"]

    response = client.delete(f"/api/v1/subcategories/{subcategory_id}")

    assert response.status_code == 204
    assert db.get(Category, category_id) is not None
