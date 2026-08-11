"""Categorization rules CRUD and POST /api/v1/rules/apply."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Category, CategoryRule, Transaction


def make_transaction(
    db: Session,
    *,
    description: str = "",
    composite_hash: str = "hash",
    category_id: int | None = None,
    user_categorized: bool = False,
) -> Transaction:
    transaction = Transaction(
        source="ING",
        composite_hash=composite_hash,
        date=date(2026, 1, 1),
        description=description,
        amount=Decimal("-1.00"),
        category_id=category_id,
        user_categorized=user_categorized,
    )
    db.add(transaction)
    db.flush()
    return transaction


def make_category(client: TestClient, name: str = "Testkategorie") -> int:
    return client.post("/api/v1/categories", json={"name": name, "color": "#38bdf8"}).json()["id"]


# --- CRUD --------------------------------------------------------------------


def test_create_rule(client: TestClient) -> None:
    category_id = make_category(client)

    response = client.post(
        "/api/v1/rules",
        json={"keyword": "rewe", "field": "description", "category_id": category_id, "priority": 5},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["keyword"] == "rewe"
    assert body["field"] == "description"
    assert body["priority"] == 5


def test_create_rule_defaults_field_to_description(client: TestClient) -> None:
    category_id = make_category(client)

    response = client.post(
        "/api/v1/rules", json={"keyword": "rewe", "category_id": category_id}
    )

    assert response.status_code == 201
    assert response.json()["field"] == "description"


def test_create_rule_rejects_invalid_field(client: TestClient) -> None:
    category_id = make_category(client)

    response = client.post(
        "/api/v1/rules",
        json={"keyword": "rewe", "field": "not_a_real_field", "category_id": category_id},
    )

    assert response.status_code == 422


def test_list_rules_includes_names_and_match_order(client: TestClient) -> None:
    category_id = make_category(client, "Einkommen")
    subcategory_id = client.post(
        f"/api/v1/categories/{category_id}/subcategories", json={"name": "Gehalt"}
    ).json()["id"]
    client.post(
        "/api/v1/rules",
        json={
            "keyword": "gehalt",
            "field": "transaction_type",
            "category_id": category_id,
            "subcategory_id": subcategory_id,
            "priority": 0,
        },
    )
    client.post(
        "/api/v1/rules",
        json={"keyword": "bonus", "field": "description", "category_id": category_id, "priority": 10},
    )

    response = client.get("/api/v1/rules")

    assert response.status_code == 200
    body = response.json()
    # priority 10 sorts ahead of priority 0
    assert body[0]["keyword"] == "bonus"
    assert body[0]["category_name"] == "Einkommen"
    assert body[0]["subcategory_name"] is None
    assert body[1]["keyword"] == "gehalt"
    assert body[1]["category_name"] == "Einkommen"
    assert body[1]["subcategory_name"] == "Gehalt"


def test_patch_rule_partial_update(client: TestClient) -> None:
    category_id = make_category(client)
    rule_id = client.post(
        "/api/v1/rules", json={"keyword": "rewe", "category_id": category_id}
    ).json()["id"]

    response = client.patch(f"/api/v1/rules/{rule_id}", json={"priority": 7})

    assert response.status_code == 200
    body = response.json()
    assert body["priority"] == 7
    assert body["keyword"] == "rewe"


def test_patch_rule_field(client: TestClient) -> None:
    category_id = make_category(client)
    rule_id = client.post(
        "/api/v1/rules", json={"keyword": "rewe", "category_id": category_id}
    ).json()["id"]

    response = client.patch(f"/api/v1/rules/{rule_id}", json={"field": "counter_account"})

    assert response.status_code == 200
    assert response.json()["field"] == "counter_account"


def test_patch_rule_rejects_invalid_field(client: TestClient) -> None:
    category_id = make_category(client)
    rule_id = client.post(
        "/api/v1/rules", json={"keyword": "rewe", "category_id": category_id}
    ).json()["id"]

    response = client.patch(f"/api/v1/rules/{rule_id}", json={"field": "nope"})

    assert response.status_code == 422


def test_patch_missing_rule_returns_404(client: TestClient) -> None:
    response = client.patch("/api/v1/rules/999999", json={"priority": 1})
    assert response.status_code == 404


def test_delete_rule(client: TestClient) -> None:
    category_id = make_category(client)
    rule_id = client.post(
        "/api/v1/rules", json={"keyword": "rewe", "category_id": category_id}
    ).json()["id"]

    response = client.delete(f"/api/v1/rules/{rule_id}")

    assert response.status_code == 204
    assert client.get("/api/v1/rules").json() == []


def test_delete_missing_rule_returns_404(client: TestClient) -> None:
    response = client.delete("/api/v1/rules/999999")
    assert response.status_code == 404


# --- POST /rules: apply_to_existing ------------------------------------------


def test_create_rule_with_apply_to_existing_backfills_blank_rows_only(
    client: TestClient, db: Session
) -> None:
    category_id = make_category(client)
    other_category_id = make_category(client, "Andere")

    blank = make_transaction(db, description="Rewe Markt", composite_hash="a")
    already_categorized = make_transaction(
        db, description="Rewe Extra", composite_hash="b", category_id=other_category_id
    )
    user_cleared = make_transaction(
        db, description="Rewe Nord", composite_hash="c", user_categorized=True
    )
    non_matching = make_transaction(db, description="Aldi Markt", composite_hash="d")

    response = client.post(
        "/api/v1/rules",
        json={"keyword": "rewe", "category_id": category_id, "apply_to_existing": True},
    )

    assert response.status_code == 201
    assert response.json()["applied_count"] == 1
    db.refresh(blank)
    db.refresh(already_categorized)
    db.refresh(user_cleared)
    db.refresh(non_matching)
    assert blank.category_id == category_id
    # Already has a category — even auto-assigned — so it's left alone.
    assert already_categorized.category_id == other_category_id
    # user_categorized == True means the blank was a deliberate choice.
    assert user_cleared.category_id is None
    assert non_matching.category_id is None


def test_create_rule_without_apply_to_existing_touches_nothing(
    client: TestClient, db: Session
) -> None:
    category_id = make_category(client)
    txn = make_transaction(db, description="Rewe Markt", composite_hash="a")

    response = client.post("/api/v1/rules", json={"keyword": "rewe", "category_id": category_id})

    assert response.status_code == 201
    assert response.json()["applied_count"] == 0
    db.refresh(txn)
    assert txn.category_id is None


# --- POST /rules/apply --------------------------------------------------------


def test_apply_categorizes_uncategorized_transactions(
    client: TestClient, db: Session
) -> None:
    category_id = make_category(client)
    client.post("/api/v1/rules", json={"keyword": "rewe", "category_id": category_id})
    matching = make_transaction(db, description="Rewe Markt", composite_hash="a")
    non_matching = make_transaction(db, description="Aldi Markt", composite_hash="b")

    response = client.post("/api/v1/rules/apply")

    assert response.status_code == 200
    assert response.json()["categorized"] == 1
    db.refresh(matching)
    db.refresh(non_matching)
    assert matching.category_id == category_id
    assert non_matching.category_id is None


def test_apply_never_touches_user_categorized_rows(client: TestClient, db: Session) -> None:
    category_id = make_category(client)
    other_category_id = make_category(client, "Andere")
    client.post("/api/v1/rules", json={"keyword": "rewe", "category_id": category_id})
    txn = make_transaction(
        db,
        description="Rewe Markt",
        composite_hash="a",
        category_id=other_category_id,
        user_categorized=True,
    )

    response = client.post("/api/v1/rules/apply")

    assert response.status_code == 200
    assert response.json()["categorized"] == 0
    db.refresh(txn)
    assert txn.category_id == other_category_id


def test_apply_after_category_delete_recategorizes(client: TestClient, db: Session) -> None:
    """The PLAN.md 2.3 scenario, unblocked now that /rules/apply exists:
    create category -> categorize a transaction -> delete the category ->
    run /rules/apply -> the transaction gets recategorized."""
    old_category_id = make_category(client, "Alt")
    new_category_id = make_category(client, "Neu")
    client.post("/api/v1/rules", json={"keyword": "rewe", "category_id": new_category_id})
    txn = make_transaction(
        db,
        description="Rewe Markt",
        composite_hash="a",
        category_id=old_category_id,
        user_categorized=True,
    )

    client.delete(f"/api/v1/categories/{old_category_id}")
    db.refresh(txn)
    assert txn.category_id is None
    assert txn.user_categorized is False

    response = client.post("/api/v1/rules/apply")

    assert response.status_code == 200
    assert response.json()["categorized"] == 1
    db.refresh(txn)
    assert txn.category_id == new_category_id


# --- category deletion cascading into rules ----------------------------------


def test_delete_category_cascades_rules_pointing_to_it(client: TestClient) -> None:
    category_id = make_category(client)
    rule_id = client.post(
        "/api/v1/rules", json={"keyword": "rewe", "category_id": category_id}
    ).json()["id"]

    response = client.delete(f"/api/v1/categories/{category_id}")

    assert response.status_code == 204
    remaining = client.get("/api/v1/rules").json()
    assert rule_id not in [r["id"] for r in remaining]


def test_delete_category_leaves_other_rules_alone(client: TestClient) -> None:
    keep_category_id = make_category(client, "Bleibt")
    delete_category_id = make_category(client, "Wird geloescht")
    keep_rule_id = client.post(
        "/api/v1/rules", json={"keyword": "miete", "category_id": keep_category_id}
    ).json()["id"]
    client.post("/api/v1/rules", json={"keyword": "rewe", "category_id": delete_category_id})

    client.delete(f"/api/v1/categories/{delete_category_id}")

    remaining = client.get("/api/v1/rules").json()
    assert [r["id"] for r in remaining] == [keep_rule_id]


def test_list_rules_skips_an_orphaned_rule_instead_of_500ing(
    client: TestClient, db: Session
) -> None:
    """Defense in depth: category_id isn't DB-enforced (SQLite FKs are off), so
    a rule can in principle end up pointing at a missing category through some
    path other than DELETE /categories/{id} (which now cascades). The list
    endpoint should skip it rather than crash on the missing category name."""
    category = Category(name="Temporaer", color="#000000")
    db.add(category)
    db.flush()
    good_rule = CategoryRule(keyword="miete", field="description", category_id=category.id)
    db.add(good_rule)
    db.flush()
    orphan_rule = CategoryRule(keyword="rewe", field="description", category_id=category.id)
    db.add(orphan_rule)
    db.flush()
    db.delete(category)
    db.flush()  # bypasses the router's cascade — simulates pre-existing bad data

    response = client.get("/api/v1/rules")

    assert response.status_code == 200
    assert response.json() == []
