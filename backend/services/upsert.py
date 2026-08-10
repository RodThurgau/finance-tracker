"""Write parsed rows into the database, per-source.

Two rules hold for both sources, without exception:

- Upsert never writes `transaction_tags`. Tags are applied independently of
  categorization, so a tagged-but-uncategorized row would otherwise lose its
  tags on the next import.
- Upsert never writes `exclude_from_stats`. The flag is user-owned.

Nothing here deletes. A reimport only ever adds or updates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Transaction
from parsers.common import ParseResult, RowError
from parsers.detect import Source
from schemas import TransactionCreate
from services.categorizer import categorize, load_rules


@dataclass(frozen=True)
class SkippedRow:
    """An ING row dropped as a duplicate, listed so a real hash collision shows."""

    row_number: int
    composite_hash: str
    date: date_type
    description: str
    amount: Decimal


@dataclass
class ImportSummary:
    """What one import did."""

    source: str
    new: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[RowError] = field(default_factory=list)
    date_range: tuple[date_type, date_type] | None = None
    skipped_rows: list[SkippedRow] = field(default_factory=list)


def date_range_of(transactions: list[TransactionCreate]) -> tuple[date_type, date_type] | None:
    """Earliest and latest booking date across parsed rows, or None if empty."""
    if not transactions:
        return None
    dates = [transaction.date for transaction in transactions]
    return min(dates), max(dates)


def to_model(data: TransactionCreate) -> Transaction:
    """Build a Transaction ORM row from a parsed row.

    `exclude_from_stats` is left at its column default and never set from
    imported data.
    """
    return Transaction(
        source=data.source,
        transaction_id=data.transaction_id,
        composite_hash=data.composite_hash,
        date=data.date,
        description=data.description,
        original_description=data.original_description,
        amount=data.amount,
        currency=data.currency,
        counter_account=data.counter_account,
        transaction_type=data.transaction_type,
    )


def upsert_ing(session: Session, parsed: ParseResult) -> ImportSummary:
    """Insert ING rows whose composite hash is new; skip the rest.

    An existing hash is skipped entirely, preserving every user edit on that
    row. Duplicates *within* the same file are skipped too, so a file listing a
    row twice inserts it once.
    """
    summary = ImportSummary(
        source=Source.ING.value,
        errors=list(parsed.errors),
        date_range=date_range_of(parsed.transactions),
    )
    if not parsed.transactions:
        return summary

    hashes = {transaction.composite_hash for transaction in parsed.transactions}
    seen = set(
        session.scalars(
            select(Transaction.composite_hash).where(Transaction.composite_hash.in_(hashes))
        )
    )
    rules = load_rules(session)

    for row_number, data in enumerate(parsed.transactions, start=1):
        if data.composite_hash in seen:
            summary.skipped += 1
            summary.skipped_rows.append(
                SkippedRow(
                    row_number=row_number,
                    composite_hash=data.composite_hash,
                    date=data.date,
                    description=data.description,
                    amount=data.amount,
                )
            )
            continue

        transaction = to_model(data)
        categorize(transaction, rules)
        session.add(transaction)
        seen.add(data.composite_hash)
        summary.new += 1

    session.flush()
    return summary


def upsert_paypal(session: Session, parsed: ParseResult) -> ImportSummary:
    """Insert PayPal rows with a new transaction id; update the ones already held.

    An update refreshes amount, description, and metadata. Category,
    subcategory, `user_categorized`, `exclude_from_stats`, and tags are left
    exactly as they are — existing rows do not run through the categorizer.
    """
    summary = ImportSummary(
        source=Source.PAYPAL.value,
        errors=list(parsed.errors),
        date_range=date_range_of(parsed.transactions),
    )
    if not parsed.transactions:
        return summary

    ids = {t.transaction_id for t in parsed.transactions if t.transaction_id is not None}
    existing = {
        transaction.transaction_id: transaction
        for transaction in session.scalars(
            select(Transaction).where(Transaction.transaction_id.in_(ids))
        )
    }
    rules = load_rules(session)

    for data in parsed.transactions:
        held = existing.get(data.transaction_id) if data.transaction_id is not None else None
        if held is not None:
            held.date = data.date
            held.description = data.description
            held.original_description = data.original_description
            held.amount = data.amount
            held.currency = data.currency
            held.counter_account = data.counter_account
            held.transaction_type = data.transaction_type
            summary.updated += 1
            continue

        transaction = to_model(data)
        categorize(transaction, rules)
        session.add(transaction)
        if data.transaction_id is not None:
            existing[data.transaction_id] = transaction
        summary.new += 1

    session.flush()
    return summary


def upsert(session: Session, source: Source, parsed: ParseResult) -> ImportSummary:
    """Dispatch to the right upsert for the detected source.

    Flushes but does not commit — the caller owns the transaction boundary.
    """
    if source is Source.ING:
        return upsert_ing(session, parsed)
    return upsert_paypal(session, parsed)
