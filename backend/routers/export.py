"""GET /api/v1/export/csv — CSV export of filtered transactions.

Accepts the exact same filters as GET /transactions by reusing that router's
filter-building and sort-column logic directly (`apply_transaction_filters`,
`SORT_COLUMNS`), so "same filters as transaction list" (PLAN.md 2.6) can't
silently drift out of sync between the two endpoints. Pagination doesn't
apply here — export always returns every matching row.

`exclude_from_stats` is deliberately not forced in either direction here:
excluded rows are included in exports (CLAUDE.md — the flag only affects
stats), but the caller can still narrow with `?excluded=true/false` same as
on the transaction list, since that's one of the filters being reused as-is.

Internal transfers are the one filter that is *not* neutral by default: like
the transaction list, the export hides them unless asked otherwise
(`?internal=show`). They are duplicate representations of money counted
elsewhere, so including them would hand out a CSV whose column sums are wrong
— the opposite of what `exclude_from_stats` rows do, which are real money and
belong in the file.

The filename's date range is computed from the actual exported rows' min/max
`date`, not from the requested date_from/date_to values, so it always
reflects what's really in the file — including when no date filter was given
at all. An empty export falls back to today's date for both ends.
"""

from __future__ import annotations

import csv
import io
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models import Transaction
from routers.transactions import (
    SORT_COLUMNS,
    InternalFilter,
    SortBy,
    SortDir,
    SourceFilter,
    apply_transaction_filters,
)

router = APIRouter(prefix="/api/v1/export", tags=["export"])

CSV_COLUMNS = [
    "date",
    "description",
    "amount",
    "currency",
    "source",
    "category",
    "subcategory",
    "tags",
    "counter_account",
    "transaction_type",
]


def _row(transaction: Transaction) -> list[str]:
    return [
        transaction.date.isoformat(),
        transaction.description,
        str(transaction.amount),
        transaction.currency,
        transaction.source,
        transaction.category.name if transaction.category else "",
        transaction.subcategory.name if transaction.subcategory else "",
        ";".join(tag.name for tag in transaction.tags),
        transaction.counter_account or "",
        transaction.transaction_type or "",
    ]


@router.get("/csv")
def export_csv(
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
    internal: InternalFilter = "hide",
    sort_by: SortBy = "date",
    sort_dir: SortDir = "desc",
    db: Session = Depends(get_db),
) -> Response:
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
        internal=internal,
    )

    column = SORT_COLUMNS[sort_by]
    order = column.asc() if sort_dir == "asc" else column.desc()

    stmt = apply_transaction_filters(select(Transaction), **filters)
    stmt = stmt.options(
        selectinload(Transaction.category),
        selectinload(Transaction.subcategory),
        selectinload(Transaction.tags),
    ).order_by(order, Transaction.id.asc())
    transactions = list(db.scalars(stmt))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for transaction in transactions:
        writer.writerow(_row(transaction))

    if transactions:
        dates = [transaction.date for transaction in transactions]
        range_start, range_end = min(dates), max(dates)
    else:
        range_start = range_end = datetime.now().date()

    filename = f"finance_export_{range_start.isoformat()}_{range_end.isoformat()}.csv"

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
