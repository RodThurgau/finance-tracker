"""Identify which bank produced a CSV, from its header row alone.

The signatures here are also what `preclean.py` scans for when it looks for the
header row, so the two stay in step by construction: a file whose header
preclean can find is a file this module can identify.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from enum import StrEnum


class Source(StrEnum):
    """Value stored in `transactions.source`."""

    ING = "ING"
    PAYPAL = "PayPal"


class UnknownSource(Exception):
    """Raised when a header row matches no known signature."""

    def __init__(self, header_line: str) -> None:
        self.header_line = header_line
        super().__init__(f"Header row matches no known source: {header_line!r}")


@dataclass(frozen=True)
class SourceSignature:
    """The columns and delimiter that identify one bank's export."""

    source: Source
    delimiter: str
    required_columns: frozenset[str]


# Extra trailing columns are tolerated — required columns are a subset check,
# never an equality check. ING adds `Saldo`/`Währung` in some exports.
SIGNATURES: tuple[SourceSignature, ...] = (
    SourceSignature(
        source=Source.ING,
        delimiter=";",
        required_columns=frozenset(
            {
                "Buchung",
                "Wertstellungsdatum",
                "Auftraggeber/Empfänger",
                "Buchungstext",
                "Verwendungszweck",
                "Betrag",
                "Währung",
            }
        ),
    ),
    SourceSignature(
        source=Source.PAYPAL,
        delimiter=",",
        required_columns=frozenset({"Transaktionscode", "Brutto", "Datum", "Beschreibung"}),
    ),
)


def split_header(line: str, delimiter: str) -> list[str]:
    """Split a header row into column names, unquoted and stripped."""
    cells = next(csv.reader(io.StringIO(line), delimiter=delimiter), [])
    return [cell.strip() for cell in cells]


def matches(signature: SourceSignature, line: str) -> bool:
    """True when a line carries every column the signature requires."""
    return signature.required_columns <= set(split_header(line, signature.delimiter))


def match_signature(line: str) -> SourceSignature | None:
    """Return the signature a line satisfies, or None."""
    for signature in SIGNATURES:
        if matches(signature, line):
            return signature
    return None


def detect_source(header_line: str) -> Source:
    """Identify the source of a precleaned header row.

    Raises `UnknownSource` if no signature matches.
    """
    signature = match_signature(header_line)
    if signature is None:
        raise UnknownSource(header_line)
    return signature.source
