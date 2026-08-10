"""GET /api/v1/stats/summary — aggregated spending data for charts.

Every aggregate filters `exclude_from_stats == False`, with no override
parameter (CLAUDE.md: "No exceptions, no query parameter to override it").
Per PLAN.md 2.5 the endpoint "accepts same date filters as transactions" —
that means date_from/date_to only, not the full transaction filter set.

Sums go through `func.sum(Transaction.amount)`, which SQLAlchemy runs against
the underlying INTEGER-cents column (via the `DecimalAmount` TypeDecorator)
and decodes back to `Decimal` exactly once per aggregate row, satisfying
"computed in integer cents, converted to Decimal once at serialization"
without any manual cents arithmetic here.

Design decisions not spelled out in PLAN.md, made and documented rather than
guessed silently:
- Amounts keep their natural sign throughout (expenses negative, matching
  every other signed amount in the app) rather than being flipped positive.
- "Spending by category" and "top merchants" are expense-only breakdowns
  (amount < 0) — Phase 4.1 draws the income/expense split out separately for
  the *monthly* chart ("income vs expenses stacked"), implying the category
  and merchant breakdowns are expense-focused by contrast.
- "Spending by category" includes an uncategorized bucket (category_id/name
  = None) so its total reconciles with total_expenses; a transaction with no
  counter_account is excluded from "top merchants" since there's no merchant
  identity to group it under.
- Months/categories with zero matching transactions are omitted rather than
  padded with zero entries — filling gaps for a continuous chart axis is a
  frontend concern.
"""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from database import get_db
from models import Category, Transaction
from schemas import CategorySpendEntry, MerchantSpendEntry, MonthlySummaryEntry, StatsSummary

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])

TOP_MERCHANTS_LIMIT = 10
ZERO = Decimal("0.00")


def _in_range(stmt: Select, date_from: date_type | None, date_to: date_type | None) -> Select:
    stmt = stmt.where(Transaction.exclude_from_stats.is_(False))
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)
    return stmt


@router.get("/summary", response_model=StatsSummary)
def stats_summary(
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    db: Session = Depends(get_db),
) -> StatsSummary:
    total_income = (
        db.scalar(_in_range(select(func.sum(Transaction.amount)), date_from, date_to).where(Transaction.amount > 0))
        or ZERO
    )
    total_expenses = (
        db.scalar(_in_range(select(func.sum(Transaction.amount)), date_from, date_to).where(Transaction.amount < 0))
        or ZERO
    )
    net = db.scalar(_in_range(select(func.sum(Transaction.amount)), date_from, date_to)) or ZERO

    category_rows = db.execute(
        _in_range(
            select(Transaction.category_id, Category.name, func.sum(Transaction.amount))
            .outerjoin(Category, Category.id == Transaction.category_id)
            .where(Transaction.amount < 0)
            .group_by(Transaction.category_id, Category.name),
            date_from,
            date_to,
        ).order_by(func.sum(Transaction.amount).asc())
    ).all()
    by_category = [
        CategorySpendEntry(category_id=category_id, category_name=category_name, total=total)
        for category_id, category_name, total in category_rows
    ]

    month_column = func.strftime("%Y-%m", Transaction.date)
    income_by_month = dict(
        db.execute(
            _in_range(
                select(month_column, func.sum(Transaction.amount)).where(Transaction.amount > 0),
                date_from,
                date_to,
            ).group_by(month_column)
        ).all()
    )
    expenses_by_month = dict(
        db.execute(
            _in_range(
                select(month_column, func.sum(Transaction.amount)).where(Transaction.amount < 0),
                date_from,
                date_to,
            ).group_by(month_column)
        ).all()
    )
    months = sorted(set(income_by_month) | set(expenses_by_month))
    by_month = [
        MonthlySummaryEntry(
            month=month,
            income=income_by_month.get(month, ZERO),
            expenses=expenses_by_month.get(month, ZERO),
        )
        for month in months
    ]

    merchant_rows = db.execute(
        _in_range(
            select(Transaction.counter_account, func.sum(Transaction.amount))
            .where(Transaction.amount < 0, Transaction.counter_account.is_not(None))
            .group_by(Transaction.counter_account),
            date_from,
            date_to,
        )
        .order_by(func.sum(Transaction.amount).asc())
        .limit(TOP_MERCHANTS_LIMIT)
    ).all()
    top_merchants = [
        MerchantSpendEntry(counter_account=counter_account, total=total)
        for counter_account, total in merchant_rows
    ]

    return StatsSummary(
        total_income=total_income,
        total_expenses=total_expenses,
        net=net,
        by_category=by_category,
        by_month=by_month,
        top_merchants=top_merchants,
    )
