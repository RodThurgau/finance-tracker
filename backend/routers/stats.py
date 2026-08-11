"""GET /api/v1/stats/summary — aggregated spending data for charts.

Every aggregate filters `exclude_from_stats == False` and drops internal
transfers (services/internal_transfers.py), with no override parameter for
either (CLAUDE.md: "No exceptions, no query parameter to override it").
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
- "Spending by category" is **net**: income filed under a category cancels
  spending in the same one, so rent that is partly reimbursed reports what it
  actually cost. Categories netting to zero or above are omitted — they are
  not spending, and the pie chart they feed cannot mix slice signs. This is
  the one place income and expenses are combined; `total_expenses` stays the
  gross sum of negative amounts, so the two deliberately do **not** reconcile.
  "Top merchants" stays expense-only (amount < 0).
- The uncategorized bucket (category_id/name = None) is the exception and
  stays expense-only. Netting means "a reimbursement against a budget", and
  the unfiled bucket is not a budget — its income is typically an
  uncategorized salary, unrelated to its spending, and netting the two would
  cancel them off and drop the bucket from the chart exactly while it is
  still unfiled and most needs attention.
- A transaction with no counter_account is excluded from "top merchants",
  since there's no merchant identity to group it under.
- Months/categories with zero matching transactions are omitted rather than
  padded with zero entries — filling gaps for a continuous chart axis is a
  frontend concern.
"""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from balance import sorted_anchors
from database import get_db
from models import Category, Transaction
from schemas import (
    BalanceCheck,
    BalanceSummary,
    CategorySpendEntry,
    MerchantSpendEntry,
    MonthlySummaryEntry,
    StatsSummary,
)
from services.internal_transfers import is_internal_transfer

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])

TOP_MERCHANTS_LIMIT = 10
ZERO = Decimal("0.00")


def _countable(stmt: Select) -> Select:
    """The rows every figure on this router is computed from.

    `/stats/balance` reuses it so the running balance is built from exactly the
    same set as the aggregates — otherwise the two would disagree and neither
    could be used to check the other.
    """
    stmt = stmt.where(Transaction.exclude_from_stats.is_(False))
    # Internal transfers are dropped with no way to override, same as
    # `exclude_from_stats` — counting a PayPal purchase's funding legs
    # alongside the purchase would double- and triple-count it.
    return stmt.where(~is_internal_transfer())


def _in_range(stmt: Select, date_from: date_type | None, date_to: date_type | None) -> Select:
    stmt = _countable(stmt)
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

    # Net, not gross: income filed under a category cancels spending in the same
    # one, so rent that is partly paid back reports what it actually cost.
    #
    # Rows with no category are the exception and stay expense-only. Netting
    # means "a reimbursement against a budget", and the unfiled bucket is not a
    # budget — it is a grab-bag whose income (an uncategorized salary) has no
    # relationship to its spending. Netting it would cancel the two off against
    # each other and drop the bucket from the chart entirely, hiding real
    # spending precisely while it is still unfiled and most needs attention.
    # `having` drops anything at or above zero: a category that earned more than
    # it cost is not spending, and a pie chart cannot draw a negative slice
    # alongside positive ones.
    category_rows = db.execute(
        _in_range(
            select(Transaction.category_id, Category.name, func.sum(Transaction.amount))
            .outerjoin(Category, Category.id == Transaction.category_id)
            # Keep the row if it carries a category (either sign, so income
            # nets), or if it is an expense. That drops exactly one thing:
            # income with no category.
            .where(or_(Transaction.category_id.is_not(None), Transaction.amount < 0))
            .group_by(Transaction.category_id, Category.name),
            date_from,
            date_to,
        )
        .having(func.sum(Transaction.amount) < 0)
        .order_by(func.sum(Transaction.amount).asc())
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


@router.get("/balance", response_model=BalanceSummary)
def stats_balance(db: Session = Depends(get_db)) -> BalanceSummary:
    """Running account balance, anchored to hand-verified figures in `balance.py`.

    A CSV export records movements, never a balance, so the absolute figure has
    to come from outside the ledger. Everything here is that anchor plus the
    movements around it.
    """

    def movement_sum(after: date_type | None = None, through: date_type | None = None) -> Decimal:
        stmt = _countable(select(func.sum(Transaction.amount)))
        if after is not None:
            stmt = stmt.where(Transaction.date > after)
        if through is not None:
            stmt = stmt.where(Transaction.date <= through)
        return db.scalar(stmt) or ZERO

    anchors = sorted_anchors()
    latest = anchors[-1]

    current_balance = latest.balance + movement_sum(after=latest.on)

    last_date = db.scalar(_countable(select(func.max(Transaction.date))))
    first_date = db.scalar(_countable(select(func.min(Transaction.date))))

    # What the account must have held before the first recorded movement. Only
    # meaningful when the ledger actually reaches back past the anchor.
    implied_opening = (
        latest.balance - movement_sum(through=latest.on) if first_date is not None else None
    )

    # Each anchor predicted from the one before it. Empty until a second anchor
    # is added — that is when the ledger starts checking itself.
    checks = []
    for previous, current in zip(anchors, anchors[1:]):
        expected = previous.balance + movement_sum(after=previous.on, through=current.on)
        checks.append(
            BalanceCheck(
                on=current.on,
                expected=expected,
                actual=current.balance,
                drift=current.balance - expected,
            )
        )

    return BalanceSummary(
        anchor_date=latest.on,
        anchor_balance=latest.balance,
        current_balance=current_balance,
        as_of=last_date if last_date and last_date > latest.on else latest.on,
        opening_date=first_date,
        implied_opening_balance=implied_opening,
        checks=checks,
    )
