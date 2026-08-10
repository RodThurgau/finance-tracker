"""PayPal (German export) CSV → the common transaction schema.

Every field is read as a string and converted explicitly. No type inference.
The German export carries no `Status` column, so no rows are filtered out here.
"""

from __future__ import annotations

import csv
import io

from parsers.common import (
    ParseResult,
    RowError,
    collapse_whitespace,
    parse_german_amount,
    parse_german_date,
)
from parsers.detect import Source
from parsers.preclean import PrecleanResult
from schemas import TransactionCreate

COL_DATUM = "Datum"
COL_BESCHREIBUNG = "Beschreibung"
COL_CURRENCY = "Währung"
COL_BRUTTO = "Brutto"
COL_CODE = "Transaktionscode"
COL_SENDER_EMAIL = "Absender E-Mail-Adresse"
COL_NAME = "Name"


def parse(precleaned: PrecleanResult) -> ParseResult:
    """Convert precleaned PayPal rows into TransactionCreate models.

    Rows whose date or amount will not parse are collected as `RowError`s rather
    than dropped, so a bad row is visible in the import summary.
    """
    result = ParseResult()
    reader = csv.DictReader(
        io.StringIO("\n".join(precleaned.data_lines)),
        fieldnames=next(csv.reader(io.StringIO(precleaned.header_line), delimiter=",")),
        delimiter=",",
    )

    for row_number, row in enumerate(reader, start=1):
        raw_datum = row.get(COL_DATUM) or ""
        raw_brutto = row.get(COL_BRUTTO) or ""

        try:
            booking_date = parse_german_date(raw_datum)
        except ValueError as exc:
            result.errors.append(
                RowError(
                    row_number=row_number,
                    column=COL_DATUM,
                    value=raw_datum,
                    message=str(exc),
                )
            )
            continue

        try:
            amount = parse_german_amount(raw_brutto)
        except ValueError as exc:
            result.errors.append(
                RowError(
                    row_number=row_number,
                    column=COL_BRUTTO,
                    value=raw_brutto,
                    message=str(exc),
                )
            )
            continue

        name = collapse_whitespace(row.get(COL_NAME) or "")
        booking_text = collapse_whitespace(row.get(COL_BESCHREIBUNG) or "")
        # PayPal's own bookkeeping rows (bank credits, authorization holds) carry
        # no counterparty name, so the booking text stands in as the description.
        description = name or booking_text

        result.transactions.append(
            TransactionCreate(
                source=Source.PAYPAL.value,
                transaction_id=(row.get(COL_CODE) or "").strip() or None,
                date=booking_date,
                description=description,
                original_description=name or None,
                amount=amount,
                currency=(row.get(COL_CURRENCY) or "").strip(),
                counter_account=(row.get(COL_SENDER_EMAIL) or "").strip() or None,
                transaction_type=booking_text or None,
            )
        )

    return result
