"""Transaction listing, filtering, and updates."""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models import Tag, Transaction
from schemas import BulkUpdateResult, Transaction as TransactionSchema
from schemas import TransactionBulkUpdate, TransactionListResponse, TransactionUpdate

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])

SortBy = Literal["date", "amount", "description"]
SortDir = Literal["asc", "desc"]
SourceFilter = Literal["ING", "PayPal"]

# Public (no leading underscore): reused as-is by routers/export.py so
# GET /export/csv can accept "the same filters as transaction list" without
# duplicating — and risking drifting from — this logic.
SORT_COLUMNS = {
    "date": Transaction.date,
    "amount": Transaction.amount,
    "description": Transaction.description,
}


def apply_transaction_filters(
    stmt: Select,
    *,
    category_id: int | None,
    subcategory_id: int | None,
    tag_id: list[int] | None,
    untagged: bool | None,
    source: str | None,
    date_from: date_type | None,
    date_to: date_type | None,
    search: str | None,
    min_amount: Decimal | None,
    max_amount: Decimal | None,
    uncategorized: bool | None,
    excluded: bool | None,
) -> Select:
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if subcategory_id is not None:
        stmt = stmt.where(Transaction.subcategory_id == subcategory_id)
    # Repeatable parameter, OR semantics: ?tag_id=1&tag_id=2 matches rows
    # carrying either tag. A single ?tag_id=1 behaves exactly as before.
    if tag_id:
        stmt = stmt.where(Transaction.tags.any(Tag.id.in_(tag_id)))
    # Mirrors `uncategorized`: True keeps rows with no tags at all, False keeps
    # rows carrying at least one. Combining it with tag_id is contradictory and
    # correctly yields nothing.
    if untagged is not None:
        stmt = stmt.where(~Transaction.tags.any() if untagged else Transaction.tags.any())
    if source is not None:
        stmt = stmt.where(Transaction.source == source)
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)
    if search:
        stmt = stmt.where(Transaction.description.ilike(f"%{search}%"))
    if min_amount is not None:
        stmt = stmt.where(Transaction.amount >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(Transaction.amount <= max_amount)
    if uncategorized is not None:
        stmt = stmt.where(
            Transaction.category_id.is_(None)
            if uncategorized
            else Transaction.category_id.is_not(None)
        )
    if excluded is not None:
        stmt = stmt.where(Transaction.exclude_from_stats == excluded)
    return stmt


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    category_id: int | None = None,
    subcategory_id: int | None = None,
    tag_id: list[int] | None = Query(None),
    untagged: bool | None = None,
    source: SourceFilter | None = None,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    search: str | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    uncategorized: bool | None = None,
    excluded: bool | None = None,
    sort_by: SortBy = "date",
    sort_dir: SortDir = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    filters = dict(
        category_id=category_id,
        subcategory_id=subcategory_id,
        tag_id=tag_id,
        untagged=untagged,
        source=source,
        date_from=date_from,
        date_to=date_to,
        search=search,
        min_amount=min_amount,
        max_amount=max_amount,
        uncategorized=uncategorized,
        excluded=excluded,
    )

    total = (
        db.scalar(apply_transaction_filters(select(func.count()).select_from(Transaction), **filters))
        or 0
    )

    column = SORT_COLUMNS[sort_by]
    order = column.asc() if sort_dir == "asc" else column.desc()

    stmt = apply_transaction_filters(select(Transaction), **filters)
    stmt = (
        stmt.options(selectinload(Transaction.tags))
        .order_by(order, Transaction.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = list(db.scalars(stmt))
    return TransactionListResponse(items=items, total=total)


# Registered ahead of "/{transaction_id}" for readability; Starlette's int
# converter regex already keeps "bulk" from matching that route.
@router.patch("/bulk", response_model=BulkUpdateResult)
def bulk_update_transactions(
    update: TransactionBulkUpdate,
    db: Session = Depends(get_db),
) -> BulkUpdateResult:
    if not update.ids:
        return BulkUpdateResult(updated=0)

    fields = update.model_fields_set
    categorizing = "category_id" in fields or "subcategory_id" in fields

    transactions = list(db.scalars(select(Transaction).where(Transaction.id.in_(update.ids))))
    for transaction in transactions:
        if categorizing:
            if "category_id" in fields:
                transaction.category_id = update.category_id
            if "subcategory_id" in fields:
                transaction.subcategory_id = update.subcategory_id
            transaction.user_categorized = True
        if "exclude_from_stats" in fields:
            transaction.exclude_from_stats = update.exclude_from_stats

    db.commit()
    return BulkUpdateResult(updated=len(transactions))


@router.patch("/{transaction_id}", response_model=TransactionSchema)
def update_transaction(
    transaction_id: int,
    update: TransactionUpdate,
    db: Session = Depends(get_db),
) -> Transaction:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    fields = update.model_fields_set
    if "category_id" in fields or "subcategory_id" in fields:
        if "category_id" in fields:
            transaction.category_id = update.category_id
        if "subcategory_id" in fields:
            transaction.subcategory_id = update.subcategory_id
        transaction.user_categorized = True
    if "exclude_from_stats" in fields:
        transaction.exclude_from_stats = update.exclude_from_stats

    db.commit()
    db.refresh(transaction)
    return transaction
