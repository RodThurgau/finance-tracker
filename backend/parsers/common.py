"""Conversions and result types shared by both parsers.

Both sources are German exports, so dates (`DD.MM.YYYY`) and amounts
(`-1.234,56`) arrive in the same notation and must convert identically. The
conversions live here so the two parsers cannot drift apart on money handling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from schemas import TransactionCreate

WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class RowError:
    """One row that could not be parsed, kept instead of being dropped."""

    row_number: int  # 1-based position among the data rows, header excluded
    column: str
    value: str
    message: str


@dataclass
class ParseResult:
    """Everything a parser produces: the good rows and the bad ones."""

    transactions: list[TransactionCreate] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)


def collapse_whitespace(text: str) -> str:
    """Collapse runs of whitespace to single spaces and trim the ends."""
    return WHITESPACE.sub(" ", text).strip()


def parse_german_date(raw: str) -> date:
    """Convert `DD.MM.YYYY` to a date. Raises ValueError on anything else."""
    return datetime.strptime(raw.strip(), "%d.%m.%Y").date()


def parse_german_amount(raw: str) -> Decimal:
    """Convert `-1.234,56` to a Decimal, via its string form.

    `.` is the thousands separator and `,` the decimal separator. The cleaned
    **string** goes to Decimal — never float, at any point.
    """
    cleaned = raw.strip().replace(".", "").replace(",", ".")
    if not cleaned:
        raise ValueError("empty amount")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"not a valid amount: {raw!r}") from exc
