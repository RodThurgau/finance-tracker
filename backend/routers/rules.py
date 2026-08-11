"""Categorization rules CRUD and manual re-apply.

The matching logic itself (field-scoped, case-insensitive substring, first
match under `priority DESC, id ASC`) lives in `services/categorizer.py` — this
router only owns the CRUD surface and the `/apply` re-run.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models import CategoryRule, Transaction
from schemas import CategoryRule as CategoryRuleSchema
from schemas import (
    CategoryRuleCreate,
    CategoryRuleCreateResult,
    CategoryRuleUpdate,
    CategoryRuleWithNames,
    RulesApplyResult,
)
from services.categorizer import apply_rule_to_uncategorized, categorize, load_rules

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


@router.get("", response_model=list[CategoryRuleWithNames])
def list_rules(db: Session = Depends(get_db)) -> list[CategoryRuleWithNames]:
    rules = db.scalars(
        select(CategoryRule)
        .options(selectinload(CategoryRule.category), selectinload(CategoryRule.subcategory))
        .order_by(CategoryRule.priority.desc(), CategoryRule.id.asc())
    ).all()
    # DELETE /categories/{id} cascades into category_rules, so this shouldn't
    # happen going forward — but category_id isn't DB-enforced (SQLite FKs are
    # off), so a rule left pointing at a missing category by some other path
    # is skipped here rather than 500ing the whole list.
    return [
        CategoryRuleWithNames(
            id=rule.id,
            keyword=rule.keyword,
            field=rule.field,
            category_id=rule.category_id,
            subcategory_id=rule.subcategory_id,
            priority=rule.priority,
            category_name=rule.category.name,
            subcategory_name=rule.subcategory.name if rule.subcategory else None,
        )
        for rule in rules
        if rule.category is not None
    ]


@router.post("", response_model=CategoryRuleCreateResult, status_code=201)
def create_rule(data: CategoryRuleCreate, db: Session = Depends(get_db)) -> CategoryRuleCreateResult:
    rule = CategoryRule(
        keyword=data.keyword,
        field=data.field,
        category_id=data.category_id,
        subcategory_id=data.subcategory_id,
        priority=data.priority,
    )
    db.add(rule)

    # Same commit as the insert, so a backfill failure rolls the rule back too.
    applied_count = apply_rule_to_uncategorized(db, rule) if data.apply_to_existing else 0

    db.commit()
    db.refresh(rule)
    return CategoryRuleCreateResult(
        id=rule.id,
        keyword=rule.keyword,
        field=rule.field,
        category_id=rule.category_id,
        subcategory_id=rule.subcategory_id,
        priority=rule.priority,
        applied_count=applied_count,
    )


@router.patch("/{rule_id}", response_model=CategoryRuleSchema)
def update_rule(
    rule_id: int, data: CategoryRuleUpdate, db: Session = Depends(get_db)
) -> CategoryRule:
    rule = db.get(CategoryRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    fields = data.model_fields_set
    if "keyword" in fields:
        rule.keyword = data.keyword
    if "field" in fields:
        rule.field = data.field
    if "category_id" in fields:
        rule.category_id = data.category_id
    if "subcategory_id" in fields:
        rule.subcategory_id = data.subcategory_id
    if "priority" in fields:
        rule.priority = data.priority

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)) -> None:
    rule = db.get(CategoryRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()


@router.post("/apply", response_model=RulesApplyResult)
def apply_rules(db: Session = Depends(get_db)) -> RulesApplyResult:
    """Re-run every rule against every transaction with `user_categorized == False`.

    Mirrors the auto-categorization gate used on import: rows the user has
    manually categorized are never touched, but rows already auto-categorized
    by an older rule are re-evaluated and may change category.
    """
    rules = load_rules(db)
    transactions = list(
        db.scalars(select(Transaction).where(Transaction.user_categorized.is_(False)))
    )
    newly_categorized = sum(1 for transaction in transactions if categorize(transaction, rules))
    db.commit()
    return RulesApplyResult(categorized=newly_categorized)
