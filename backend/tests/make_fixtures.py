"""Derive test fixture CSVs from the hand-written demo files.

The two demo files under ``tests/fixtures/`` are the only hand-written inputs;
everything under ``tests/fixtures/generated/`` is produced from them by this
script. Generation is deterministic and idempotent — nothing depends on the
clock, the filesystem order, or a random seed — so regenerating after an
unrelated change produces no diff.

Run with::

    uv run python tests/make_fixtures.py
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
GENERATED_DIR = FIXTURES_DIR / "generated"

# The demo files are hand-written and land here straight from a bank export, so
# tolerate either separator in the name and any extension casing (.csv / .CSV).
ING_DEMO_NAMES = ("ing_demo.csv", "ing-demo.csv")
PAYPAL_DEMO_NAMES = ("paypal_demo.csv", "paypal-demo.csv")

ING_DELIMITER = ";"
# ING marks the start of the real CSV with this column; everything above it is
# the metadata preamble.
ING_HEADER_FIRST_COLUMN = "Buchung"

# PayPal's German export: comma-separated, every field quoted, header on line 1,
# UTF-8 with a BOM. Column order is fixed by the export, so index by position.
PAYPAL_DELIMITER = ","
PAYPAL_HEADER_FIRST_COLUMN = "Datum"
PAYPAL_NAME = 11  # counterparty — the parser's description / original_description
PAYPAL_TRANSACTION_CODE = 9  # Transaktionscode — the dedup key
BOM = b"\xef\xbb\xbf"

# Fixed opening balance for the ``Saldo`` column of the extra-columns variant.
# Any constant works; it only has to be stable across runs.
ING_OPENING_BALANCE = Decimal("5000.00")


@dataclass(frozen=True)
class DemoFile:
    """A demo CSV split into its preamble, header row, and data rows."""

    preamble_lines: list[str]
    header_line: str
    data_lines: list[str]


def find_demo(names: tuple[str, ...]) -> Path | None:
    """Return the first demo file that exists, or None if none was provided.

    Matching is case-insensitive so a ``paypal_demo.CSV`` straight out of the
    PayPal export lands without renaming.
    """
    present = {path.name.lower(): path for path in sorted(FIXTURES_DIR.iterdir()) if path.is_file()}
    for name in names:
        path = present.get(name.lower())
        if path is not None:
            return path
    return None


def read_demo(path: Path, header_first_column: str, delimiter: str) -> DemoFile:
    """Split a demo file into preamble, header, and data rows.

    Decodes UTF-8 with a Latin-1 fallback, matching what ``preclean.py`` does,
    so a demo file saved in either encoding works here.
    """
    raw = path.read_bytes().lstrip(b"\xef\xbb\xbf")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    lines = text.replace("\r\n", "\n").split("\n")
    for index, line in enumerate(lines):
        # PayPal quotes every cell, ING quotes none — strip quotes before matching.
        if line.split(delimiter)[0].strip().strip('"') == header_first_column:
            preamble = lines[:index]
            data = [row for row in lines[index + 1 :] if row.strip()]
            return DemoFile(preamble_lines=preamble, header_line=line, data_lines=data)

    raise SystemExit(f"No header row starting with {header_first_column!r} in {path}")


def join(preamble: list[str], header: str, rows: list[str]) -> str:
    """Assemble a CSV file body from its three parts."""
    return "\n".join([*preamble, header, *rows]) + "\n"


def whole(demo: DemoFile) -> str:
    """The demo file as-is, normalized to LF line endings."""
    return join(demo.preamble_lines, demo.header_line, demo.data_lines)


def write(name: str, content: str | bytes, encoding: str = "utf-8") -> None:
    """Write a generated fixture, skipping the write when it is unchanged."""
    path = GENERATED_DIR / name
    data = content if isinstance(content, bytes) else content.encode(encoding)
    if path.exists() and path.read_bytes() == data:
        return
    path.write_bytes(data)


def split_row(line: str, delimiter: str) -> list[str]:
    """Parse one CSV line into its cells."""
    return next(csv.reader(io.StringIO(line), delimiter=delimiter))


def join_row(cells: list[str], delimiter: str, quote_all: bool = False) -> str:
    """Render cells back into one CSV line.

    ``quote_all`` reproduces PayPal's habit of quoting every field; ING quotes
    only what it has to.
    """
    buffer = io.StringIO()
    csv.writer(
        buffer,
        delimiter=delimiter,
        lineterminator="",
        quoting=csv.QUOTE_ALL if quote_all else csv.QUOTE_MINIMAL,
    ).writerow(cells)
    return buffer.getvalue()


def parse_ing_amount(raw: str) -> Decimal:
    """Convert an ING amount (``-1.234,56``) to a Decimal, via its string form."""
    return Decimal(raw.replace(".", "").replace(",", "."))


def format_ing_amount(value: Decimal) -> str:
    """Render a Decimal back into ING's ``-1.234,56`` notation."""
    sign = "-" if value < 0 else ""
    whole_part, _, fraction = f"{abs(value):.2f}".partition(".")
    grouped = f"{int(whole_part):,}".replace(",", ".")
    return f"{sign}{grouped},{fraction}"


# --- ING variants ----------------------------------------------------------


def generate_ing(demo: DemoFile) -> None:
    """Write every derived ING fixture."""
    body = whole(demo)

    # Same rows, re-encoded. The demo is Latin-1, byte-faithful to a real ING
    # export; ing_bom.csv is the UTF-8 side. The composite hash must come out
    # identical for all three, since hashing encodes to UTF-8 first.
    write("ing_latin1.csv", body, encoding="latin-1")
    write("ing_bom.csv", b"\xef\xbb\xbf" + body.encode("utf-8"))

    write("ing_no_preamble.csv", join([], demo.header_line, demo.data_lines))

    long_preamble = [
        "Umsatzanzeige;Datei erstellt am: 06.08.2026 22:39",
        "",
        "",
        "Hinweis;Dies ist ein Export mit zusätzlichen Kopfzeilen",
        "Erstellt von;Internetbanking",
        "Version;2.4.1",
        "",
        *demo.preamble_lines,
        "",
        "Filter;Keine",
        "",
    ]
    write("ing_long_preamble.csv", join(long_preamble, demo.header_line, demo.data_lines))

    write("ing_extra_columns.csv", ing_extra_columns(demo))

    # The first data row repeated verbatim: both copies hash identically, so
    # the second one must be skipped as a duplicate.
    duplicated = [demo.data_lines[0], demo.data_lines[0], *demo.data_lines[1:]]
    write("ing_duplicate_rows.csv", join(demo.preamble_lines, demo.header_line, duplicated))

    write("ing_identical_but_different_day.csv", ing_different_day(demo))
    write("ing_malformed_row.csv", ing_malformed(demo))
    write("ing_reimport_overlap.csv", ing_reimport_overlap(demo))


def ing_extra_columns(demo: DemoFile) -> str:
    """The demo plus trailing ``Saldo``/``Währung`` columns, which are ignored."""
    header = join_row(
        [*split_row(demo.header_line, ING_DELIMITER), "Saldo", "Währung"], ING_DELIMITER
    )

    # Rows are newest-first, so walk them in reverse to build a running balance.
    balances: list[str] = []
    balance = ING_OPENING_BALANCE
    for line in reversed(demo.data_lines):
        balance += parse_ing_amount(split_row(line, ING_DELIMITER)[5])
        balances.append(format_ing_amount(balance))
    balances.reverse()

    rows = [
        join_row([*split_row(line, ING_DELIMITER), saldo, "EUR"], ING_DELIMITER)
        for line, saldo in zip(demo.data_lines, balances)
    ]
    return join(demo.preamble_lines, header, rows)


def ing_different_day(demo: DemoFile) -> str:
    """The demo plus a copy of row one booked on a different day.

    Same purpose text and same amount, different ``Buchung`` — the hash differs,
    so both rows must be inserted.
    """
    cells = split_row(demo.data_lines[0], ING_DELIMITER)
    cells[0] = "29.07.2026"
    cells[1] = "29.07.2026"
    rows = [*demo.data_lines, join_row(cells, ING_DELIMITER)]
    return join(demo.preamble_lines, demo.header_line, rows)


def ing_malformed(demo: DemoFile) -> str:
    """The demo plus one unparseable date and one unparseable amount."""
    bad_date = split_row(demo.data_lines[0], ING_DELIMITER)
    bad_date[0] = "31.13.2026"
    bad_date[4] = "Zeile mit ungültigem Buchungsdatum"

    bad_amount = split_row(demo.data_lines[1], ING_DELIMITER)
    bad_amount[4] = "Zeile mit ungültigem Betrag"
    bad_amount[5] = "-,,"

    rows = [
        *demo.data_lines,
        join_row(bad_date, ING_DELIMITER),
        join_row(bad_amount, ING_DELIMITER),
    ]
    return join(demo.preamble_lines, demo.header_line, rows)


def ing_reimport_overlap(demo: DemoFile) -> str:
    """The demo rows plus two later ones, for testing skip-vs-insert."""
    new_rows = [
        "05.08.2026;05.08.2026;VISA DM DROGERIEMARKT;Lastschrift;"
        "NR XXXX 1234 CITYNAME DE KAUFUMSATZ 03.08 24.10 172651 "
        "ARN74396046210900007608612 Apple Pay;-24,10;EUR",
        "04.08.2026;04.08.2026;Deutsche Bahn AG;Kartenzahlung;"
        "Fahrkarte Hamburg - München, Buchungsnummer XZ4711;-129,90;EUR",
    ]
    return join(demo.preamble_lines, demo.header_line, [*new_rows, *demo.data_lines])


# --- PayPal variants -------------------------------------------------------


def generate_paypal(demo: DemoFile) -> None:
    """Write every derived PayPal fixture.

    The German export carries no ``Status`` column and unambiguous
    ``DD.MM.YYYY`` dates, so there is no pending-status or date-order fixture —
    see the PayPal section of CLAUDE.md.
    """
    # PayPal ships UTF-8 with a BOM; keep it so preclean's BOM strip stays exercised.
    write("paypal_reimport_overlap.csv", BOM + paypal_reimport_overlap(demo).encode("utf-8"))


def paypal_reimport_overlap(demo: DemoFile) -> str:
    """The demo rows with changed counterparty names, plus one new transaction.

    Transaktionscodes are unchanged, so every demo row must update in place and
    keep its category and tags; the trailing row is the only insert.
    """
    rows: list[str] = []
    for line in demo.data_lines:
        cells = split_row(line, PAYPAL_DELIMITER)
        name = cells[PAYPAL_NAME]
        cells[PAYPAL_NAME] = f"{name} (umbenannt)" if name else "Nachträglich ergänzter Name"
        rows.append(join_row(cells, PAYPAL_DELIMITER, quote_all=True))

    new_row = join_row(
        [
            "07.08.2026",
            "09:31:07",
            "Europe/Berlin",
            "PayPal Express-Zahlung",
            "EUR",
            "-19,99",
            "0,00",
            "-19,99",
            "0,00",
            "6KM40218TY9931845",
            "billing@example-shop.de",
            "Beispiel Onlineshop GmbH",
            "",
            "",
            "0,00",
            "0,00",
            "",
            "",
        ],
        PAYPAL_DELIMITER,
        quote_all=True,
    )
    return join(demo.preamble_lines, demo.header_line, [*rows, new_row])


# --- Non-CSV ---------------------------------------------------------------


def generate_not_a_csv() -> None:
    """A file with no header row anywhere, for the NoHeaderFound path."""
    text = (
        "Dies ist keine CSV-Datei.\n"
        "Es gibt keine Kopfzeile und keine Spaltennamen.\n"
        "\n"
        "Nur ein bisschen Text, damit der Import fehlschlagen kann.\n"
    )
    write("not_a_csv.txt", text)


def main() -> int:
    """Regenerate every derived fixture. Returns a process exit code."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    ing_demo = find_demo(ING_DEMO_NAMES)
    if ing_demo is None:
        raise SystemExit(f"Missing ING demo file: expected one of {ING_DEMO_NAMES} in {FIXTURES_DIR}")
    generate_ing(read_demo(ing_demo, ING_HEADER_FIRST_COLUMN, ING_DELIMITER))

    generate_not_a_csv()

    paypal_demo = find_demo(PAYPAL_DEMO_NAMES)
    if paypal_demo is None:
        raise SystemExit(
            f"Missing PayPal demo file: expected one of {PAYPAL_DEMO_NAMES} in {FIXTURES_DIR}"
        )
    generate_paypal(read_demo(paypal_demo, PAYPAL_HEADER_FIRST_COLUMN, PAYPAL_DELIMITER))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
