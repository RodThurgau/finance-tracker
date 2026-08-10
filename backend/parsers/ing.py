"""ING (Germany) CSV → the common transaction schema.

Every field is read as a string and converted explicitly. No type inference.
"""

from __future__ import annotations

import csv
import hashlib
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

COL_BUCHUNG = "Buchung"
COL_WERTSTELLUNG = "Wertstellungsdatum"
COL_COUNTERPARTY = "Auftraggeber/Empfänger"
COL_BUCHUNGSTEXT = "Buchungstext"
COL_PURPOSE = "Verwendungszweck"
COL_BETRAG = "Betrag"
COL_CURRENCY = "Währung"

DESCRIPTION_SEPARATOR = " — "

# --- FROZEN ----------------------------------------------------------------
# The composite hash is ING's only dedup key, and changing any part of it turns
# every future import into a full re-insert of the entire history. The separator
# is a single pipe, the encoding is UTF-8 regardless of the file's encoding, and
# the inputs are the raw cell strings exactly as the CSV reader yields them —
# no trimming, case folding, whitespace collapsing, or reformatting.
# Do not change this function. Ever.
HASH_SEPARATOR = "|"


def composite_hash(raw_buchung: str, raw_verwendungszweck: str, raw_betrag: str) -> str:
    """Return ING's dedup hash for one row. FROZEN — see the note above."""
    joined = HASH_SEPARATOR.join((raw_buchung, raw_verwendungszweck, raw_betrag))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


# --- end FROZEN ------------------------------------------------------------


def parse(precleaned: PrecleanResult) -> ParseResult:
    """Convert precleaned ING rows into TransactionCreate models.

    Rows whose date or amount will not parse are collected as `RowError`s rather
    than dropped, so a bad row is visible in the import summary.
    """
    result = ParseResult()
    reader = csv.DictReader(
        io.StringIO("\n".join(precleaned.data_lines)),
        fieldnames=next(csv.reader(io.StringIO(precleaned.header_line), delimiter=";")),
        delimiter=";",
    )

    for row_number, row in enumerate(reader, start=1):
        raw_buchung = row.get(COL_BUCHUNG) or ""
        raw_purpose = row.get(COL_PURPOSE) or ""
        raw_betrag = row.get(COL_BETRAG) or ""

        try:
            booking_date = parse_german_date(raw_buchung)
        except ValueError as exc:
            result.errors.append(
                RowError(
                    row_number=row_number,
                    column=COL_BUCHUNG,
                    value=raw_buchung,
                    message=str(exc),
                )
            )
            continue

        # Parsed to validate the row; the value itself is not stored.
        raw_value_date = row.get(COL_WERTSTELLUNG) or ""
        try:
            parse_german_date(raw_value_date)
        except ValueError as exc:
            result.errors.append(
                RowError(
                    row_number=row_number,
                    column=COL_WERTSTELLUNG,
                    value=raw_value_date,
                    message=str(exc),
                )
            )
            continue

        try:
            amount = parse_german_amount(raw_betrag)
        except ValueError as exc:
            result.errors.append(
                RowError(
                    row_number=row_number,
                    column=COL_BETRAG,
                    value=raw_betrag,
                    message=str(exc),
                )
            )
            continue

        counterparty = (row.get(COL_COUNTERPARTY) or "").strip()
        description = collapse_whitespace(
            f"{counterparty}{DESCRIPTION_SEPARATOR}{raw_purpose}"
        )

        result.transactions.append(
            TransactionCreate(
                source=Source.ING.value,
                composite_hash=composite_hash(raw_buchung, raw_purpose, raw_betrag),
                date=booking_date,
                description=description,
                original_description=raw_purpose,
                amount=amount,
                currency=(row.get(COL_CURRENCY) or "").strip(),
                counter_account=counterparty or None,
                transaction_type=(row.get(COL_BUCHUNGSTEXT) or "").strip() or None,
            )
        )

    return result
