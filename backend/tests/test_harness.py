"""Checks on the test harness itself: migrated schema and generated fixtures."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.orm import Session

import make_fixtures

EXPECTED_TABLES = {
    "categories",
    "subcategories",
    "transactions",
    "tags",
    "transaction_tags",
    "category_rules",
}

EXPECTED_ING_FIXTURES = [
    "ing_latin1.csv",
    "ing_bom.csv",
    "ing_no_preamble.csv",
    "ing_long_preamble.csv",
    "ing_extra_columns.csv",
    "ing_duplicate_rows.csv",
    "ing_identical_but_different_day.csv",
    "ing_malformed_row.csv",
    "ing_reimport_overlap.csv",
    "not_a_csv.txt",
]

EXPECTED_PAYPAL_FIXTURES = ["paypal_reimport_overlap.csv"]


def test_migrations_create_every_table(db: Session) -> None:
    tables = set(inspect(db.get_bind()).get_table_names())
    assert EXPECTED_TABLES <= tables


def test_tests_run_against_a_throwaway_database(db: Session) -> None:
    url = str(db.get_bind().engine.url)
    assert "finance-tracker-tests-" in url


def test_generated_fixtures_exist(generated_dir: Path) -> None:
    expected = [*EXPECTED_ING_FIXTURES, *EXPECTED_PAYPAL_FIXTURES]
    missing = [name for name in expected if not (generated_dir / name).exists()]
    assert not missing


def test_paypal_overlap_keeps_every_transaction_code(
    fixtures_dir: Path, generated_dir: Path
) -> None:
    """Reimport overlap must update in place, so the codes may not drift."""
    demo = make_fixtures.read_demo(
        make_fixtures.find_demo(make_fixtures.PAYPAL_DEMO_NAMES),
        make_fixtures.PAYPAL_HEADER_FIRST_COLUMN,
        make_fixtures.PAYPAL_DELIMITER,
    )
    overlap = make_fixtures.read_demo(
        generated_dir / "paypal_reimport_overlap.csv",
        make_fixtures.PAYPAL_HEADER_FIRST_COLUMN,
        make_fixtures.PAYPAL_DELIMITER,
    )

    def codes(rows: list[str]) -> list[str]:
        column = make_fixtures.PAYPAL_TRANSACTION_CODE
        return [
            make_fixtures.split_row(row, make_fixtures.PAYPAL_DELIMITER)[column] for row in rows
        ]

    demo_codes = codes(demo.data_lines)
    overlap_codes = codes(overlap.data_lines)
    assert overlap_codes[: len(demo_codes)] == demo_codes
    assert len(overlap_codes) == len(demo_codes) + 1


def test_generation_is_idempotent(generated_dir: Path) -> None:
    before = {p.name: p.read_bytes() for p in sorted(generated_dir.iterdir())}
    make_fixtures.main()
    after = {p.name: p.read_bytes() for p in sorted(generated_dir.iterdir())}
    assert before == after


def test_encoding_variants_hold_the_same_rows(generated_dir: Path) -> None:
    latin1 = (generated_dir / "ing_latin1.csv").read_bytes().decode("latin-1")
    bom = (generated_dir / "ing_bom.csv").read_bytes()
    assert bom.startswith(b"\xef\xbb\xbf")
    assert bom[3:].decode("utf-8") == latin1
