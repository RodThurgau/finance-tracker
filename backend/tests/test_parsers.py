"""Parser behaviour for both sources, plus the frozen composite hash."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from parsers import ing, paypal
from parsers.ing import composite_hash
from parsers.preclean import preclean


def parse_ing(path: Path):
    return ing.parse(preclean(path.read_bytes()))


def parse_paypal(path: Path):
    return paypal.parse(preclean(path.read_bytes()))


# --- Composite hash --------------------------------------------------------


def test_composite_hash_regression() -> None:
    """Pinned input → pinned digest.

    If this fails, the hash definition moved and every future ING import would
    re-insert the entire history. Fix the code, never this expectation.
    """
    assert composite_hash(
        "31.07.2026", "NR XXXX 1234 CITYNAME DE KAUFUMSATZ 29.07 15.26", "-15,26"
    ) == "ded74e5314833555a44383980ec73ece7b6a724ecf08f83597c4c4811f7700ed"


def test_composite_hash_regression_with_umlauts_and_separators() -> None:
    assert composite_hash(
        "30.07.2026", "Küchenzeile — Anzahlung", "-1.234,56"
    ) == "3622bd730da1974828c923725d6ee7f450539c8efdff05a952997938eb863b9d"


def test_hashes_are_stable_across_encodings(generated_dir: Path) -> None:
    """The same rows in Latin-1 and in UTF-8 must dedup against each other."""
    latin1 = parse_ing(generated_dir / "ing_latin1.csv")
    bom = parse_ing(generated_dir / "ing_bom.csv")

    hashes = [transaction.composite_hash for transaction in latin1.transactions]
    assert hashes == [transaction.composite_hash for transaction in bom.transactions]
    assert len(set(hashes)) == len(hashes)


def test_hash_ignores_derived_field_formatting(fixtures_dir: Path) -> None:
    """The hash comes from raw cells, so reformatting `description` is free."""
    result = parse_ing(fixtures_dir / "ing_demo.csv")
    first = result.transactions[0]

    assert first.composite_hash == composite_hash(
        "31.07.2026",
        "NR XXXX 1234 CITYNAME DE KAUFUMSATZ 29.07 15.26 172651 "
        "ARN74396046210900007608505 Apple Pay",
        "-15,26",
    )


def test_duplicate_rows_hash_identically(generated_dir: Path) -> None:
    result = parse_ing(generated_dir / "ing_duplicate_rows.csv")

    assert result.transactions[0].composite_hash == result.transactions[1].composite_hash


def test_same_row_on_a_different_day_hashes_differently(generated_dir: Path) -> None:
    result = parse_ing(generated_dir / "ing_identical_but_different_day.csv")
    hashes = [transaction.composite_hash for transaction in result.transactions]

    assert len(set(hashes)) == len(hashes)


# --- ING parser ------------------------------------------------------------


def test_ing_demo_parses_every_row(fixtures_dir: Path) -> None:
    result = parse_ing(fixtures_dir / "ing_demo.csv")

    assert len(result.transactions) == 7
    assert result.errors == []
    assert all(transaction.source == "ING" for transaction in result.transactions)
    assert all(transaction.transaction_id is None for transaction in result.transactions)


def test_ing_column_mapping(fixtures_dir: Path) -> None:
    result = parse_ing(fixtures_dir / "ing_demo.csv")
    first = result.transactions[0]

    assert first.date == date(2026, 7, 31)
    assert first.counter_account == "VISA BUDNIKOWSKY"
    assert first.transaction_type == "Lastschrift"
    assert first.currency == "EUR"
    assert first.original_description.startswith("NR XXXX 1234")
    assert first.description.startswith("VISA BUDNIKOWSKY — NR XXXX 1234")


def test_ing_amounts_are_exact_decimals(fixtures_dir: Path) -> None:
    amounts = [t.amount for t in parse_ing(fixtures_dir / "ing_demo.csv").transactions]

    assert all(isinstance(amount, Decimal) for amount in amounts)
    assert amounts == [
        Decimal("-15.26"),
        Decimal("-3.99"),
        Decimal("-1234.56"),  # thousands separator stripped, sign preserved
        Decimal("-89.00"),
        Decimal("-10.99"),
        Decimal("19.99"),
        Decimal("2450.00"),
    ]


def test_ing_signs_are_not_flipped(fixtures_dir: Path) -> None:
    result = parse_ing(fixtures_dir / "ing_demo.csv")
    by_type = {t.transaction_type: t.amount for t in result.transactions}

    assert by_type["Gehalt/Rente"] == Decimal("2450.00")
    assert by_type["Gutschrift"] == Decimal("19.99")
    assert by_type["Überweisung"] == Decimal("-1234.56")


def test_ing_description_collapses_whitespace(generated_dir: Path) -> None:
    result = parse_ing(generated_dir / "ing_extra_columns.csv")

    assert all("  " not in t.description for t in result.transactions)
    assert all(t.description == t.description.strip() for t in result.transactions)


def test_ing_extra_columns_do_not_disturb_the_mapping(generated_dir: Path) -> None:
    with_extra = parse_ing(generated_dir / "ing_extra_columns.csv").transactions
    plain = parse_ing(generated_dir / "ing_no_preamble.csv").transactions

    assert [t.amount for t in with_extra] == [t.amount for t in plain]
    assert [t.composite_hash for t in with_extra] == [t.composite_hash for t in plain]
    assert all(t.currency == "EUR" for t in with_extra)


def test_ing_malformed_rows_are_collected_not_dropped(generated_dir: Path) -> None:
    result = parse_ing(generated_dir / "ing_malformed_row.csv")

    assert len(result.transactions) == 7
    assert [(e.row_number, e.column) for e in result.errors] == [
        (8, "Buchung"),
        (9, "Betrag"),
    ]
    assert result.errors[0].value == "31.13.2026"
    assert result.errors[1].value == "-,,"


# --- PayPal parser ---------------------------------------------------------


def test_paypal_demo_parses_every_row(fixtures_dir: Path) -> None:
    result = parse_paypal(fixtures_dir / "paypal_demo.CSV")

    assert len(result.transactions) == 9
    assert result.errors == []
    assert all(t.source == "PayPal" for t in result.transactions)
    assert all(t.composite_hash is None for t in result.transactions)


def test_paypal_column_mapping(fixtures_dir: Path) -> None:
    first = parse_paypal(fixtures_dir / "paypal_demo.CSV").transactions[0]

    assert first.date == date(2026, 8, 1)
    assert first.transaction_id == "5KJ72910MC844213X"
    assert first.amount == Decimal("-12.90")
    assert first.currency == "EUR"
    assert first.counter_account == "billing@nordlicht-fitness.example"
    assert first.transaction_type == "Zahlung im Einzugsverfahren mit Zahlungsrechnung"
    assert first.description == "Fitnessclub Nordlicht GmbH"
    assert first.original_description == "Fitnessclub Nordlicht GmbH"


def test_paypal_blank_name_falls_back_to_beschreibung(fixtures_dir: Path) -> None:
    result = parse_paypal(fixtures_dir / "paypal_demo.CSV")
    credit = result.transactions[2]

    assert credit.description == "Bankgutschrift auf PayPal-Konto"
    assert credit.original_description is None
    assert credit.counter_account is None


def test_paypal_amounts_are_exact_decimals(fixtures_dir: Path) -> None:
    amounts = [t.amount for t in parse_paypal(fixtures_dir / "paypal_demo.CSV").transactions]

    assert all(isinstance(amount, Decimal) for amount in amounts)
    assert amounts == [
        Decimal("-12.90"),
        Decimal("-7.25"),
        Decimal("7.25"),
        Decimal("-42.00"),
        Decimal("42.00"),
        Decimal("-5.50"),
        Decimal("-31.50"),
        Decimal("5.50"),
        Decimal("31.50"),
    ]


def test_paypal_transaction_ids_are_unique(fixtures_dir: Path) -> None:
    ids = [t.transaction_id for t in parse_paypal(fixtures_dir / "paypal_demo.CSV").transactions]

    assert len(set(ids)) == len(ids)


def test_paypal_reimport_variant_keeps_ids_and_changes_names(
    fixtures_dir: Path, generated_dir: Path
) -> None:
    original = parse_paypal(fixtures_dir / "paypal_demo.CSV").transactions
    overlap = parse_paypal(generated_dir / "paypal_reimport_overlap.csv").transactions

    assert [t.transaction_id for t in overlap][: len(original)] == [
        t.transaction_id for t in original
    ]
    assert overlap[0].description != original[0].description
