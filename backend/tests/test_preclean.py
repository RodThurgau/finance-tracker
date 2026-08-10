"""Preclean and source detection against the fixture CSVs."""

from __future__ import annotations

from pathlib import Path

import pytest

from parsers.detect import Source, UnknownSource, detect_source
from parsers.preclean import MAX_HEADER_SCAN_LINES, NoHeaderFound, preclean

ING_HEADER_COLUMNS = [
    "Buchung",
    "Wertstellungsdatum",
    "Auftraggeber/Empfänger",
    "Buchungstext",
    "Verwendungszweck",
    "Betrag",
    "Währung",
]


def run(path: Path):
    return preclean(path.read_bytes())


# --- ING -------------------------------------------------------------------


def test_demo_is_latin1_and_the_preamble_is_stripped(fixtures_dir: Path) -> None:
    result = run(fixtures_dir / "ing_demo.csv")

    assert result.encoding == "latin-1"
    assert result.delimiter == ";"
    assert result.header_line_number == 13
    assert result.header_line.split(";") == ING_HEADER_COLUMNS
    assert len(result.data_lines) == 7
    assert result.preamble_lines[0].startswith("Umsatzanzeige;")
    assert "Auftraggeber/Empfänger" not in "\n".join(result.preamble_lines)


def test_latin1_and_bom_variants_yield_identical_rows(generated_dir: Path) -> None:
    latin1 = run(generated_dir / "ing_latin1.csv")
    bom = run(generated_dir / "ing_bom.csv")

    assert latin1.encoding == "latin-1"
    assert bom.encoding == "utf-8"
    # Different bytes on disk, same text after decoding — umlauts included.
    assert latin1.header_line == bom.header_line
    assert latin1.data_lines == bom.data_lines
    assert "Möbelhaus Küchenblock GmbH" in bom.data_lines[2]


def test_no_preamble(generated_dir: Path) -> None:
    result = run(generated_dir / "ing_no_preamble.csv")

    assert result.header_line_number == 1
    assert result.preamble_lines == []
    assert len(result.data_lines) == 7


def test_long_preamble(generated_dir: Path) -> None:
    result = run(generated_dir / "ing_long_preamble.csv")

    assert result.header_line_number > 13
    assert result.header_line.split(";") == ING_HEADER_COLUMNS
    assert len(result.data_lines) == 7
    # Blank lines inside the preamble are kept for the import preview.
    assert "" in result.preamble_lines


def test_extra_columns_are_tolerated(generated_dir: Path) -> None:
    result = run(generated_dir / "ing_extra_columns.csv")

    assert detect_source(result.header_line) is Source.ING
    assert result.header_line.split(";")[-2:] == ["Saldo", "Währung"]
    assert len(result.data_lines) == 7


def test_blank_lines_between_rows_are_dropped() -> None:
    header = ";".join(ING_HEADER_COLUMNS)
    raw = f"Vorspann;egal\n\n{header}\n\nrow one\n\n\nrow two\n\n".encode()

    result = preclean(raw)

    assert result.data_lines == ["row one", "row two"]


# --- PayPal ----------------------------------------------------------------


def test_paypal_bom_is_stripped(fixtures_dir: Path) -> None:
    result = run(fixtures_dir / "paypal_demo.CSV")

    assert result.encoding == "utf-8"
    assert result.delimiter == ","
    assert result.header_line_number == 1
    assert result.preamble_lines == []
    assert len(result.data_lines) == 9
    # The BOM would otherwise ride along on the first column name.
    assert result.header_line.startswith('"Datum"')
    assert detect_source(result.header_line) is Source.PAYPAL


def test_paypal_generated_variant(generated_dir: Path) -> None:
    result = run(generated_dir / "paypal_reimport_overlap.csv")

    assert result.encoding == "utf-8"
    assert detect_source(result.header_line) is Source.PAYPAL
    assert len(result.data_lines) == 10


# --- Failure paths ---------------------------------------------------------


def test_not_a_csv_raises(generated_dir: Path) -> None:
    with pytest.raises(NoHeaderFound) as excinfo:
        run(generated_dir / "not_a_csv.txt")

    error = excinfo.value
    assert error.scanned_lines[0].startswith("Dies ist keine CSV-Datei")
    assert error.lines_scanned == len(error.scanned_lines)


def test_header_below_the_scan_window_is_not_found() -> None:
    header = ";".join(ING_HEADER_COLUMNS)
    buried = "\n".join(["Vorspann;egal"] * MAX_HEADER_SCAN_LINES + [header, "row one"])

    with pytest.raises(NoHeaderFound) as excinfo:
        preclean(buried.encode())

    assert excinfo.value.lines_scanned == MAX_HEADER_SCAN_LINES


def test_header_on_the_last_scanned_line_is_found() -> None:
    header = ";".join(ING_HEADER_COLUMNS)
    lines = ["Vorspann;egal"] * (MAX_HEADER_SCAN_LINES - 1) + [header, "row one"]

    result = preclean("\n".join(lines).encode())

    assert result.header_line_number == MAX_HEADER_SCAN_LINES
    assert result.data_lines == ["row one"]


def test_detect_source_rejects_an_unknown_header() -> None:
    with pytest.raises(UnknownSource):
        detect_source("foo;bar;baz")


def test_partial_ing_header_does_not_match() -> None:
    """Every required column must be present, not just some."""
    incomplete = ";".join(ING_HEADER_COLUMNS[:-1])

    with pytest.raises(NoHeaderFound):
        preclean(f"{incomplete}\nrow one\n".encode())
