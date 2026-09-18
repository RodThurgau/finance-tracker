"""Aggregates: the charts on the Übersicht, the analytics tables, the balance.

- `/stats/summary` — the Übersicht's chart data.
- `/stats/by-category` and `/stats/by-tag` — the analytics tables: money per
  category (with a subcategory level under it) and per tag, over a date range.
- `/stats/trend` — any one of those rows, month by month.
- `/stats/balance` — the anchored running balance.

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
- `total_income` and `total_expenses` are per-category-net: within each
  category, income offsets expenses before the two totals are computed.
  Rent that is partly reimbursed subtracts the reimbursement from expenses,
  not adding it to income; only categories that net positive (salary,
  savings) contribute to income.
- Top-merchant names are resolved through `merchant_mappings`: a LEFT JOIN
  with COALESCE gives each raw `counter_account` a display name that
  defaults to the raw value and is overridden by a mapping row.
- Months/categories with zero matching transactions are omitted rather than
  padded with zero entries — filling gaps for a continuous chart axis is a
  frontend concern.
"""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import Row, Select, case, func, or_, select
from sqlalchemy.orm import Session

from balance import sorted_anchors
from database import get_db
from models import Category, MerchantMapping, Subcategory, Tag, Transaction, TransactionTag
from schemas import (
    BalanceCheck,
    BalanceSummary,
    CategoryBreakdown,
    CategoryBreakdownEntry,
    CategorySpendEntry,
    MerchantSpendEntry,
    MonthlySummaryEntry,
    SpendBucket,
    StatsSummary,
    SubcategoryBreakdownEntry,
    TagBreakdown,
    TagBreakdownEntry,
    TrendPoint,
    TrendSeries,
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


def _bucket_columns() -> tuple:
    """The four aggregate columns behind every `SpendBucket` on this router.

    `case` without an `else_` yields NULL on the other side of the split, and
    `SUM` skips NULLs — so a bucket with no income at all sums to NULL, which
    `_bucket_fields` turns into an exact 0.00. Writing it as `else_=0` instead
    would push a plain integer literal through the `DecimalAmount` column type,
    which stores euros as integer cents: the untyped 0 would be read back as
    0 *cents* mixed in among cent-encoded amounts. Same reason the sums
    themselves stay in SQL — they run over the INTEGER cents column and are
    decoded to `Decimal` once, on the way out.
    """
    return (
        func.sum(case((Transaction.amount > 0, Transaction.amount))).label("income"),
        func.sum(case((Transaction.amount < 0, Transaction.amount))).label("expenses"),
        func.sum(Transaction.amount).label("net"),
        func.count().label("transaction_count"),
    )


def _bucket_fields(row: Row) -> dict[str, Decimal | int]:
    """`_bucket_columns()` off one result row, as constructor keywords."""
    return {
        "income": row.income or ZERO,
        "expenses": row.expenses or ZERO,
        "net": row.net or ZERO,
        "transaction_count": row.transaction_count,
    }


def _totals(
    db: Session, date_from: date_type | None, date_to: date_type | None
) -> SpendBucket:
    """Every countable row in the range, as one bucket."""
    row = db.execute(_in_range(select(*_bucket_columns()), date_from, date_to)).one()
    return SpendBucket(**_bucket_fields(row))


@router.get("/summary", response_model=StatsSummary)
def stats_summary(
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    db: Session = Depends(get_db),
) -> StatsSummary:
    # Per-category netting: within each category, income offsets expenses.
    # A rent category with -7500 expenses and +3300 reimbursement nets to -4200
    # and contributes that to expenses, not +3300 to income. The result: only
    # income that is not a reimbursement against spending in the same category
    # shows as income (salary, savings returns), and expenses show what they
    # actually cost after reimbursements.
    cat_net_col = func.sum(Transaction.amount).label("cat_net")
    cat_net_subq = (
        _in_range(
            select(Transaction.category_id, cat_net_col).group_by(Transaction.category_id),
            date_from,
            date_to,
        )
    ).subquery()

    total_income = (
        db.scalar(
            select(func.sum(cat_net_subq.c.cat_net)).where(cat_net_subq.c.cat_net > 0)
        )
        or ZERO
    )
    total_expenses = (
        db.scalar(
            select(func.sum(cat_net_subq.c.cat_net)).where(cat_net_subq.c.cat_net < 0)
        )
        or ZERO
    )
    net = total_income + total_expenses

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

    resolved_name = func.coalesce(MerchantMapping.display_name, Transaction.counter_account)
    merchant_rows = db.execute(
        _in_range(
            select(
                Transaction.counter_account,
                resolved_name.label("display_name"),
                func.sum(Transaction.amount),
            )
            .outerjoin(MerchantMapping, MerchantMapping.raw_name == Transaction.counter_account)
            .where(Transaction.amount < 0, Transaction.counter_account.is_not(None))
            .group_by(Transaction.counter_account),
            date_from,
            date_to,
        )
        .order_by(func.sum(Transaction.amount).asc())
        .limit(TOP_MERCHANTS_LIMIT)
    ).all()
    top_merchants = [
        MerchantSpendEntry(counter_account=ca, display_name=dn, total=total)
        for ca, dn, total in merchant_rows
    ]

    return StatsSummary(
        total_income=total_income,
        total_expenses=total_expenses,
        net=net,
        by_category=by_category,
        by_month=by_month,
        top_merchants=top_merchants,
    )


@router.get("/by-category", response_model=CategoryBreakdown)
def stats_by_category(
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    db: Session = Depends(get_db),
) -> CategoryBreakdown:
    """Money per category, each broken down one level further per subcategory.

    Deliberately **not** the same figure as `/stats/summary`'s `by_category`.
    That one feeds a pie chart, which cannot mix slice signs, so it is
    expense-shaped: categories netting to zero or above are dropped and unfiled
    income is left out. This is a ledger table instead — every countable row in
    the range lands in exactly one category bucket and exactly one subcategory
    bucket beneath it, so the entries add up to `totals` and a category that
    earned money is a row like any other. Nothing is dropped for having the
    wrong sign; that would be a table quietly failing to account for money.

    Two grouped queries rather than one plus summing in Python: every figure
    then comes straight out of SQLite's integer-cents arithmetic, and the
    per-category row cannot drift from the subcategory rows under it.
    """
    category_rows = db.execute(
        _in_range(
            select(Transaction.category_id, Category.name, Category.color, *_bucket_columns())
            .outerjoin(Category, Category.id == Transaction.category_id)
            .group_by(Transaction.category_id, Category.name, Category.color),
            date_from,
            date_to,
        ).order_by(func.sum(Transaction.amount).asc(), Category.name.asc())
    ).all()

    subcategory_rows = db.execute(
        _in_range(
            select(
                Transaction.category_id,
                Transaction.subcategory_id,
                Subcategory.name,
                *_bucket_columns(),
            )
            .outerjoin(Subcategory, Subcategory.id == Transaction.subcategory_id)
            .group_by(Transaction.category_id, Transaction.subcategory_id, Subcategory.name),
            date_from,
            date_to,
        ).order_by(func.sum(Transaction.amount).asc(), Subcategory.name.asc())
    ).all()

    children: dict[int | None, list[SubcategoryBreakdownEntry]] = {}
    for row in subcategory_rows:
        children.setdefault(row.category_id, []).append(
            SubcategoryBreakdownEntry(
                subcategory_id=row.subcategory_id,
                subcategory_name=row.name,
                **_bucket_fields(row),
            )
        )

    entries = [
        CategoryBreakdownEntry(
            category_id=row.category_id,
            category_name=row.name,
            color=row.color,
            subcategories=children.get(row.category_id, []),
            **_bucket_fields(row),
        )
        for row in category_rows
    ]
    return CategoryBreakdown(entries=entries, totals=_totals(db, date_from, date_to))


@router.get("/by-tag", response_model=TagBreakdown)
def stats_by_tag(
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    db: Session = Depends(get_db),
) -> TagBreakdown:
    """Money per tag, plus the untagged rows as their own entry.

    Tags are many-to-many, so unlike the category breakdown these entries
    overlap: a transaction carrying `Urlaub` and `Erstattung` is counted in
    full under both. The schema says so and the UI repeats it, because a table
    of figures that does not add up needs to say why on its face.

    The untagged bucket rides along as `tag_id=None` — without it the one part
    of the ledger tags say nothing about would be invisible on this page.
    """
    tag_rows = db.execute(
        _in_range(
            select(Tag.id, Tag.name, Tag.color, *_bucket_columns())
            .select_from(Transaction)
            .join(TransactionTag, TransactionTag.transaction_id == Transaction.id)
            .join(Tag, Tag.id == TransactionTag.tag_id)
            .group_by(Tag.id, Tag.name, Tag.color),
            date_from,
            date_to,
        )
    ).all()
    entries = [
        TagBreakdownEntry(tag_id=row.id, tag_name=row.name, color=row.color, **_bucket_fields(row))
        for row in tag_rows
    ]

    untagged = db.execute(
        _in_range(select(*_bucket_columns()).where(~Transaction.tags.any()), date_from, date_to)
    ).one()
    if untagged.transaction_count:
        entries.append(TagBreakdownEntry(tag_id=None, tag_name=None, **_bucket_fields(untagged)))

    # Sorted here rather than in SQL because the untagged bucket comes from a
    # second query and still has to land in the right place. Comparing Decimals
    # is exact; no arithmetic happens on this side.
    entries.sort(key=lambda entry: (entry.net, entry.tag_name or ""))
    return TagBreakdown(entries=entries, totals=_totals(db, date_from, date_to))


def _bucket_filter(
    stmt: Select,
    *,
    category_id: int | None,
    subcategory_id: int | None,
    uncategorized: bool | None,
    no_subcategory: bool | None,
    tag_id: int | None,
    untagged: bool | None,
) -> Select:
    """Narrow a statement to one row of a breakdown table.

    Every parameter is spelled and behaves exactly like its counterpart on
    `GET /transactions`, so the same object can address the trend endpoint and
    the transaction list — which is what makes "show me this row's history" and
    "show me this row's transactions" the same click with two destinations.
    """
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if subcategory_id is not None:
        stmt = stmt.where(Transaction.subcategory_id == subcategory_id)
    if uncategorized is not None:
        stmt = stmt.where(
            Transaction.category_id.is_(None)
            if uncategorized
            else Transaction.category_id.is_not(None)
        )
    if no_subcategory is not None:
        stmt = stmt.where(
            Transaction.subcategory_id.is_(None)
            if no_subcategory
            else Transaction.subcategory_id.is_not(None)
        )
    if tag_id is not None:
        stmt = stmt.where(Transaction.tags.any(Tag.id == tag_id))
    if untagged is not None:
        stmt = stmt.where(~Transaction.tags.any() if untagged else Transaction.tags.any())
    return stmt


@router.get("/trend", response_model=TrendSeries)
def stats_trend(
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    category_id: int | None = None,
    subcategory_id: int | None = None,
    uncategorized: bool | None = None,
    no_subcategory: bool | None = None,
    tag_id: int | None = None,
    untagged: bool | None = None,
    db: Session = Depends(get_db),
) -> TrendSeries:
    """One category, subcategory or tag, month by month.

    With no filter at all this is the whole ledger by month, which is what the
    analytics pages show before a row is picked. `totals` covers the same rows
    as `points` and is what the header states, so a month-by-month table and
    the figure above it can never disagree.
    """
    filters = dict(
        category_id=category_id,
        subcategory_id=subcategory_id,
        uncategorized=uncategorized,
        no_subcategory=no_subcategory,
        tag_id=tag_id,
        untagged=untagged,
    )
    month_column = func.strftime("%Y-%m", Transaction.date).label("month")
    rows = db.execute(
        _bucket_filter(
            _in_range(select(month_column, *_bucket_columns()), date_from, date_to), **filters
        )
        .group_by(month_column)
        .order_by(month_column.asc())
    ).all()

    totals_row = db.execute(
        _bucket_filter(_in_range(select(*_bucket_columns()), date_from, date_to), **filters)
    ).one()

    return TrendSeries(
        points=[TrendPoint(month=row.month, **_bucket_fields(row)) for row in rows],
        totals=SpendBucket(**_bucket_fields(totals_row)),
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
