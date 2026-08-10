"""GET/PATCH /api/v1/transactions — filtering, sorting, pagination, and updates."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Category, Tag, Transaction, TransactionTag


def upload(client: TestClient, path: Path, content_type: str = "text/csv"):
    with path.open("rb") as handle:
        return client.post(
            "/api/v1/import/csv",
            files={"file": (path.name, handle, content_type)},
        )


def import_both(client: TestClient, fixtures_dir: Path) -> None:
    upload(client, fixtures_dir / "ing_demo.csv")
    upload(client, fixtures_dir / "paypal_demo.CSV")


def make_category(db: Session, name: str = "Testkategorie") -> Category:
    category = Category(name=name, color="#ffffff")
    db.add(category)
    db.flush()
    return category


# --- GET /transactions: listing, filtering, sorting, pagination ------------


def test_list_returns_all_transactions_with_total(client: TestClient, fixtures_dir: Path) -> None:
    import_both(client, fixtures_dir)

    response = client.get("/api/v1/transactions")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 16
    assert len(body["items"]) == 16
    assert isinstance(body["items"][0]["amount"], str)


def test_list_filters_by_source(client: TestClient, fixtures_dir: Path) -> None:
    import_both(client, fixtures_dir)

    response = client.get("/api/v1/transactions", params={"source": "ING"})

    body = response.json()
    assert body["total"] == 7
    assert all(t["source"] == "ING" for t in body["items"])


def test_list_paginates(client: TestClient, fixtures_dir: Path) -> None:
    import_both(client, fixtures_dir)

    first = client.get("/api/v1/transactions", params={"page": 1, "page_size": 5}).json()
    second = client.get("/api/v1/transactions", params={"page": 2, "page_size": 5}).json()

    assert first["total"] == second["total"] == 16
    assert len(first["items"]) == 5
    assert len(second["items"]) == 5
    assert {t["id"] for t in first["items"]}.isdisjoint({t["id"] for t in second["items"]})


def test_list_sorts_by_amount(client: TestClient, fixtures_dir: Path) -> None:
    import_both(client, fixtures_dir)

    asc = client.get(
        "/api/v1/transactions", params={"sort_by": "amount", "sort_dir": "asc"}
    ).json()
    desc = client.get(
        "/api/v1/transactions", params={"sort_by": "amount", "sort_dir": "desc"}
    ).json()

    amounts_asc = [float(t["amount"]) for t in asc["items"]]
    amounts_desc = [float(t["amount"]) for t in desc["items"]]
    assert amounts_asc == sorted(amounts_asc)
    assert amounts_desc == sorted(amounts_desc, reverse=True)


def test_list_rejects_unknown_sort_by(client: TestClient) -> None:
    response = client.get("/api/v1/transactions", params={"sort_by": "not_a_field"})
    assert response.status_code == 422


def test_list_filters_by_date_range(client: TestClient, fixtures_dir: Path) -> None:
    import_both(client, fixtures_dir)

    response = client.get(
        "/api/v1/transactions",
        params={"date_from": "2026-08-01", "date_to": "2026-08-31"},
    )

    body = response.json()
    assert body["total"] == 9  # every PayPal demo row falls in August; ING rows are all July
    assert all(t["date"] >= "2026-08-01" for t in body["items"])


def test_list_searches_description_substring(client: TestClient, fixtures_dir: Path) -> None:
    import_both(client, fixtures_dir)
    all_items = client.get("/api/v1/transactions").json()["items"]
    target = next(t for t in all_items if len(t["description"]) >= 4)
    needle = target["description"][:4]

    response = client.get("/api/v1/transactions", params={"search": needle})

    body = response.json()
    assert body["total"] >= 1
    assert all(needle.casefold() in t["description"].casefold() for t in body["items"])


def test_list_filters_by_amount_range(client: TestClient, fixtures_dir: Path) -> None:
    import_both(client, fixtures_dir)

    response = client.get(
        "/api/v1/transactions", params={"min_amount": "-20", "max_amount": "0"}
    )

    body = response.json()
    assert body["total"] > 0
    for t in body["items"]:
        assert -20 <= float(t["amount"]) <= 0


def test_list_uncategorized_filter(client: TestClient, db: Session, fixtures_dir: Path) -> None:
    import_both(client, fixtures_dir)
    category = make_category(db)
    txn = db.scalars(select(Transaction)).first()
    txn.category_id = category.id
    txn.user_categorized = True
    db.flush()

    uncategorized = client.get("/api/v1/transactions", params={"uncategorized": True}).json()
    categorized = client.get("/api/v1/transactions", params={"uncategorized": False}).json()

    assert uncategorized["total"] == 15
    assert categorized["total"] == 1
    assert categorized["items"][0]["id"] == txn.id


def test_list_excluded_filter_defaults_to_showing_all(
    client: TestClient, db: Session, fixtures_dir: Path
) -> None:
    import_both(client, fixtures_dir)
    txn = db.scalars(select(Transaction)).first()
    txn.exclude_from_stats = True
    db.flush()

    unset = client.get("/api/v1/transactions").json()
    only_excluded = client.get("/api/v1/transactions", params={"excluded": True}).json()
    only_included = client.get("/api/v1/transactions", params={"excluded": False}).json()

    assert unset["total"] == 16
    assert only_excluded["total"] == 1
    assert only_excluded["items"][0]["id"] == txn.id
    assert only_included["total"] == 15


def test_list_filters_by_tag(client: TestClient, db: Session, fixtures_dir: Path) -> None:
    import_both(client, fixtures_dir)
    tag = Tag(name="Wiederkehrend", color="#818cf8")
    db.add(tag)
    db.flush()
    txn = db.scalars(select(Transaction)).first()
    db.add(TransactionTag(transaction_id=txn.id, tag_id=tag.id))
    db.flush()

    response = client.get("/api/v1/transactions", params={"tag_id": tag.id})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == txn.id


def tag_transactions(db: Session, *pairs: tuple[str, int]) -> dict[str, Tag]:
    """Create the named tags and pin each to the transaction at the given index."""
    transactions = list(db.scalars(select(Transaction).order_by(Transaction.id)))
    tags: dict[str, Tag] = {}
    for name, index in pairs:
        tag = tags.get(name)
        if tag is None:
            tag = Tag(name=name, color="#818cf8")
            db.add(tag)
            db.flush()
            tags[name] = tag
        db.add(TransactionTag(transaction_id=transactions[index].id, tag_id=tag.id))
    db.flush()
    return tags


def test_list_filters_by_several_tags_with_or_semantics(
    client: TestClient, db: Session, fixtures_dir: Path
) -> None:
    import_both(client, fixtures_dir)
    tags = tag_transactions(db, ("Erstattungsfähig", 0), ("Wiederkehrend", 1))

    response = client.get(
        "/api/v1/transactions",
        params={"tag_id": [tags["Erstattungsfähig"].id, tags["Wiederkehrend"].id]},
    )

    # A row carrying *either* tag qualifies — not only rows carrying both.
    assert response.json()["total"] == 2


def test_list_filters_untagged(client: TestClient, db: Session, fixtures_dir: Path) -> None:
    import_both(client, fixtures_dir)
    tag_transactions(db, ("Wiederkehrend", 0))

    untagged = client.get("/api/v1/transactions", params={"untagged": "true"}).json()
    tagged = client.get("/api/v1/transactions", params={"untagged": "false"}).json()

    assert untagged["total"] == 15
    assert tagged["total"] == 1
    assert all(t["tags"] == [] for t in untagged["items"])


def test_list_untagged_and_tag_id_together_match_nothing(
    client: TestClient, db: Session, fixtures_dir: Path
) -> None:
    import_both(client, fixtures_dir)
    tags = tag_transactions(db, ("Wiederkehrend", 0))

    response = client.get(
        "/api/v1/transactions",
        params={"untagged": "true", "tag_id": tags["Wiederkehrend"].id},
    )

    assert response.json()["total"] == 0


# --- PATCH /transactions/{id} -----------------------------------------------


def test_patch_sets_category_and_user_categorized(
    client: TestClient, db: Session, fixtures_dir: Path
) -> None:
    import_both(client, fixtures_dir)
    category = make_category(db)
    txn_id = db.scalars(select(Transaction)).first().id

    response = client.patch(f"/api/v1/transactions/{txn_id}", json={"category_id": category.id})

    assert response.status_code == 200
    body = response.json()
    assert body["category_id"] == category.id
    assert body["user_categorized"] is True


def test_patch_clearing_category_still_sets_user_categorized(
    client: TestClient, db: Session, fixtures_dir: Path
) -> None:
    """An explicit `category_id: null` is a real update (clearing), not a no-op."""
    import_both(client, fixtures_dir)
    category = make_category(db)
    txn = db.scalars(select(Transaction)).first()
    txn.category_id = category.id
    txn.user_categorized = True
    db.flush()

    response = client.patch(f"/api/v1/transactions/{txn.id}", json={"category_id": None})

    assert response.status_code == 200
    body = response.json()
    assert body["category_id"] is None
    assert body["user_categorized"] is True


def test_patch_exclude_from_stats_does_not_touch_user_categorized(
    client: TestClient, db: Session, fixtures_dir: Path
) -> None:
    import_both(client, fixtures_dir)
    txn_id = db.scalars(select(Transaction)).first().id

    response = client.patch(f"/api/v1/transactions/{txn_id}", json={"exclude_from_stats": True})

    assert response.status_code == 200
    body = response.json()
    assert body["exclude_from_stats"] is True
    assert body["user_categorized"] is False


def test_patch_missing_transaction_returns_404(client: TestClient) -> None:
    response = client.patch("/api/v1/transactions/999999", json={"exclude_from_stats": True})
    assert response.status_code == 404


# --- PATCH /transactions/bulk ------------------------------------------------


def test_bulk_update_applies_to_all_ids(
    client: TestClient, db: Session, fixtures_dir: Path
) -> None:
    import_both(client, fixtures_dir)
    category = make_category(db)
    ids = [t.id for t in db.scalars(select(Transaction)).all()[:3]]

    response = client.patch(
        "/api/v1/transactions/bulk",
        json={"ids": ids, "category_id": category.id, "exclude_from_stats": True},
    )

    assert response.status_code == 200
    assert response.json()["updated"] == 3
    for txn_id in ids:
        txn = db.get(Transaction, txn_id)
        db.refresh(txn)
        assert txn.category_id == category.id
        assert txn.user_categorized is True
        assert txn.exclude_from_stats is True


def test_bulk_update_leaves_untouched_fields_alone(
    client: TestClient, db: Session, fixtures_dir: Path
) -> None:
    import_both(client, fixtures_dir)
    ids = [t.id for t in db.scalars(select(Transaction)).all()[:2]]

    response = client.patch(
        "/api/v1/transactions/bulk", json={"ids": ids, "exclude_from_stats": True}
    )

    assert response.status_code == 200
    for txn_id in ids:
        txn = db.get(Transaction, txn_id)
        db.refresh(txn)
        assert txn.exclude_from_stats is True
        assert txn.category_id is None
        assert txn.user_categorized is False


def test_bulk_update_with_empty_ids_is_a_noop(client: TestClient) -> None:
    response = client.patch("/api/v1/transactions/bulk", json={"ids": []})
    assert response.status_code == 200
    assert response.json()["updated"] == 0
