"""Unit tests for the rule-matching engine in services/categorizer.py.

Endpoint-level coverage for rules CRUD and /rules/apply lives in
test_rules_endpoint.py; these tests exercise the matching logic directly.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from models import Category, CategoryRule, Transaction
from services.categorizer import categorize, find_match, load_rules


def make_category(db: Session, name: str = "Testkategorie") -> Category:
    category = Category(name=name, color="#ffffff")
    db.add(category)
    db.flush()
    return category


def make_transaction(
    db: Session,
    *,
    description: str = "",
    counter_account: str | None = None,
    transaction_type: str | None = None,
    composite_hash: str = "hash",
) -> Transaction:
    transaction = Transaction(
        source="ING",
        composite_hash=composite_hash,
        date=date(2026, 1, 1),
        description=description,
        counter_account=counter_account,
        transaction_type=transaction_type,
        amount=Decimal("-1.00"),
    )
    db.add(transaction)
    db.flush()
    return transaction


def test_counter_account_rule_matches_where_description_rule_would_not(db: Session) -> None:
    category = make_category(db)
    rule = CategoryRule(keyword="Vermieter GmbH", field="counter_account", category_id=category.id)
    db.add(rule)
    db.flush()
    transaction = make_transaction(db, description="Miete Januar", counter_account="Vermieter GmbH")

    matched = find_match(transaction, load_rules(db))

    assert matched is rule
    # The keyword only appears in counter_account — a description-field rule
    # with the same keyword would not have matched this row.
    assert "Vermieter GmbH" not in transaction.description


def test_transaction_type_rule_matches_where_description_rule_would_not(db: Session) -> None:
    category = make_category(db)
    rule = CategoryRule(keyword="Gehalt/Rente", field="transaction_type", category_id=category.id)
    db.add(rule)
    db.flush()
    transaction = make_transaction(db, description="Firma XY", transaction_type="Gehalt/Rente")

    matched = find_match(transaction, load_rules(db))

    assert matched is rule
    assert "Gehalt/Rente" not in transaction.description


def test_equal_priority_rules_resolve_deterministically_by_id(db: Session) -> None:
    category = make_category(db)
    first = CategoryRule(keyword="re", field="description", category_id=category.id, priority=0)
    db.add(first)
    db.flush()
    second = CategoryRule(keyword="rewe", field="description", category_id=category.id, priority=0)
    db.add(second)
    db.flush()
    assert first.id < second.id
    transaction = make_transaction(db, description="Rewe Markt")

    matched = find_match(transaction, load_rules(db))

    assert matched.id == first.id


def test_higher_priority_wins_regardless_of_id(db: Session) -> None:
    category = make_category(db)
    low = CategoryRule(keyword="rewe", field="description", category_id=category.id, priority=0)
    db.add(low)
    db.flush()
    high = CategoryRule(keyword="re", field="description", category_id=category.id, priority=10)
    db.add(high)
    db.flush()
    transaction = make_transaction(db, description="Rewe Markt")

    matched = find_match(transaction, load_rules(db))

    assert matched.id == high.id


def test_null_target_field_never_matches(db: Session) -> None:
    category = make_category(db)
    rule = CategoryRule(keyword="anything", field="counter_account", category_id=category.id)
    db.add(rule)
    db.flush()
    transaction = make_transaction(db, description="anything here", counter_account=None)

    assert find_match(transaction, load_rules(db)) is None


def test_categorize_never_touches_user_categorized_rows(db: Session) -> None:
    category = make_category(db)
    rule = CategoryRule(keyword="rewe", field="description", category_id=category.id)
    db.add(rule)
    db.flush()
    transaction = make_transaction(db, description="Rewe Markt")
    transaction.user_categorized = True
    db.flush()

    changed = categorize(transaction, load_rules(db))

    assert changed is False
    assert transaction.category_id is None
