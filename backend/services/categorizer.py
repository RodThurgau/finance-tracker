"""Apply keyword rules to transactions.

Rules are case-insensitive substring matches. Each rule declares which field it
matches against, because plenty of real rules are not description rules — a
landlord is best matched on `counter_account`, and "every Gehalt/Rente row is
Income" is a `transaction_type` rule.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import CategoryRule, Transaction


class RuleField(StrEnum):
    """Transaction field a rule may match against."""

    DESCRIPTION = "description"
    COUNTER_ACCOUNT = "counter_account"
    TRANSACTION_TYPE = "transaction_type"


DEFAULT_FIELD = RuleField.DESCRIPTION


def load_rules(session: Session) -> list[CategoryRule]:
    """Return all rules in match order.

    `priority DESC, id ASC` — the id tiebreak is required so two rules with
    equal priority always resolve the same way.
    """
    return list(
        session.scalars(
            select(CategoryRule).order_by(CategoryRule.priority.desc(), CategoryRule.id.asc())
        )
    )


def target_value(transaction: Transaction, rule: CategoryRule) -> str | None:
    """Return the transaction field this rule matches against.

    A rule whose `field` is NULL on an old row is treated as `description`.
    """
    return getattr(transaction, rule.field or DEFAULT_FIELD, None)


def find_match(transaction: Transaction, rules: list[CategoryRule]) -> CategoryRule | None:
    """Return the first rule matching the transaction, or None.

    Rules must already be in match order. A NULL target field never matches.
    """
    for rule in rules:
        value = target_value(transaction, rule)
        if value is None:
            continue
        if rule.keyword.casefold() in value.casefold():
            return rule
    return None


def categorize(transaction: Transaction, rules: list[CategoryRule]) -> bool:
    """Set category and subcategory on a transaction from the first matching rule.

    Never touches `user_categorized` — auto-categorization is not a user
    decision — and never touches a transaction the user has categorized.
    Returns True when a rule was applied.
    """
    if transaction.user_categorized:
        return False

    rule = find_match(transaction, rules)
    if rule is None:
        return False

    transaction.category_id = rule.category_id
    transaction.subcategory_id = rule.subcategory_id
    return True


def apply_rule_to_uncategorized(session: Session, rule: CategoryRule) -> int:
    """Backfill one freshly created (or edited) rule onto existing rows it matches.

    Deliberately narrower than a full `/rules/apply` re-run: only rows with
    `category_id IS NULL` are touched, not every row with `user_categorized ==
    False`. A row that already carries a category — even one a different rule
    assigned automatically — is left alone; this fills blanks, it does not
    relitigate an existing categorization. `user_categorized == False` is kept
    as a second guard because clearing a category via the UI's "Nicht
    zugeordnet" option sets `user_categorized = True` while leaving
    `category_id` NULL, and that deliberate choice must not be overwritten.

    Returns the number of rows updated.
    """
    transactions = session.scalars(
        select(Transaction).where(
            Transaction.category_id.is_(None),
            Transaction.user_categorized.is_(False),
        )
    )
    applied = 0
    for transaction in transactions:
        value = target_value(transaction, rule)
        if value is None:
            continue
        if rule.keyword.casefold() in value.casefold():
            transaction.category_id = rule.category_id
            transaction.subcategory_id = rule.subcategory_id
            applied += 1
    return applied
