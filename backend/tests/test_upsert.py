"""Upsert behaviour: dedup, preservation of user data, and import summaries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Category, CategoryRule, Tag, Transaction, TransactionTag
from parsers import ing, paypal
from parsers.detect import Source
from parsers.preclean import preclean
from services.upsert import upsert


def import_file(session: Session, path: Path):
    """Run the whole pipeline for one file, as the import endpoint will."""
    precleaned = preclean(path.read_bytes())
    if precleaned.delimiter == ";":
        return upsert(session, Source.ING, ing.parse(precleaned))
    return upsert(session, Source.PAYPAL, paypal.parse(precleaned))


def count_transactions(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Transaction))


def make_category(session: Session, name: str = "Testkategorie") -> Category:
    category = Category(name=name, color="#ffffff")
    session.add(category)
    session.flush()
    return category


# --- ING -------------------------------------------------------------------


def test_ing_first_import_inserts_every_row(db: Session, fixtures_dir: Path) -> None:
    summary = import_file(db, fixtures_dir / "ing_demo.csv")

    assert (summary.new, summary.updated, summary.skipped) == (7, 0, 0)
    assert summary.source == "ING"
    assert summary.errors == []
    assert summary.date_range == (date(2026, 7, 1), date(2026, 7, 31))
    assert count_transactions(db) == 7


def test_ing_duplicate_row_in_one_file_is_skipped(db: Session, generated_dir: Path) -> None:
    summary = import_file(db, generated_dir / "ing_duplicate_rows.csv")

    assert summary.new == 7
    assert summary.skipped == 1
    assert count_transactions(db) == 7
    assert [row.row_number for row in summary.skipped_rows] == [2]
    assert summary.skipped_rows[0].amount == Decimal("-15.26")


def test_ing_identical_rows_on_different_days_both_insert(
    db: Session, generated_dir: Path
) -> None:
    summary = import_file(db, generated_dir / "ing_identical_but_different_day.csv")

    assert summary.new == 8
    assert summary.skipped == 0


def test_ing_reimport_inserts_only_new_rows(
    db: Session, fixtures_dir: Path, generated_dir: Path
) -> None:
    import_file(db, fixtures_dir / "ing_demo.csv")

    summary = import_file(db, generated_dir / "ing_reimport_overlap.csv")

    assert summary.new == 2
    assert summary.skipped == 7
    assert count_transactions(db) == 9


def test_ing_reimport_preserves_user_edits(db: Session, fixtures_dir: Path) -> None:
    import_file(db, fixtures_dir / "ing_demo.csv")
    category = make_category(db)
    transaction = db.scalars(select(Transaction)).first()
    transaction.category_id = category.id
    transaction.user_categorized = True
    transaction.exclude_from_stats = True
    transaction.description = "Von Hand geändert"
    db.flush()

    import_file(db, fixtures_dir / "ing_demo.csv")

    db.refresh(transaction)
    assert transaction.category_id == category.id
    assert transaction.user_categorized is True
    assert transaction.exclude_from_stats is True
    assert transaction.description == "Von Hand geändert"


def test_ing_malformed_rows_land_in_the_summary(db: Session, generated_dir: Path) -> None:
    summary = import_file(db, generated_dir / "ing_malformed_row.csv")

    assert summary.new == 7
    assert [(e.row_number, e.column) for e in summary.errors] == [(8, "Buchung"), (9, "Betrag")]


# --- PayPal ----------------------------------------------------------------


def test_paypal_first_import_inserts_every_row(db: Session, fixtures_dir: Path) -> None:
    summary = import_file(db, fixtures_dir / "paypal_demo.CSV")

    assert (summary.new, summary.updated, summary.skipped) == (9, 0, 0)
    assert summary.source == "PayPal"
    assert summary.date_range == (date(2026, 8, 1), date(2026, 8, 6))
    assert count_transactions(db) == 9


def test_paypal_reimport_updates_metadata_in_place(
    db: Session, fixtures_dir: Path, generated_dir: Path
) -> None:
    import_file(db, fixtures_dir / "paypal_demo.CSV")

    summary = import_file(db, generated_dir / "paypal_reimport_overlap.csv")

    assert summary.updated == 9
    assert summary.new == 1
    assert count_transactions(db) == 10
    updated = db.scalars(
        select(Transaction).where(Transaction.transaction_id == "5KJ72910MC844213X")
    ).one()
    assert updated.description == "Fitnessclub Nordlicht GmbH (umbenannt)"


def test_paypal_reimport_preserves_categorization(
    db: Session, fixtures_dir: Path, generated_dir: Path
) -> None:
    import_file(db, fixtures_dir / "paypal_demo.CSV")
    category = make_category(db)
    transaction = db.scalars(
        select(Transaction).where(Transaction.transaction_id == "5KJ72910MC844213X")
    ).one()
    transaction.category_id = category.id
    transaction.user_categorized = True
    transaction.exclude_from_stats = True
    db.flush()

    import_file(db, generated_dir / "paypal_reimport_overlap.csv")

    db.refresh(transaction)
    assert transaction.category_id == category.id
    assert transaction.user_categorized is True
    assert transaction.exclude_from_stats is True
    # Metadata still refreshed around the preserved fields.
    assert transaction.description == "Fitnessclub Nordlicht GmbH (umbenannt)"


def test_paypal_reimport_keeps_tags(
    db: Session, fixtures_dir: Path, generated_dir: Path
) -> None:
    """A tagged but uncategorized row must not lose its tags on reimport."""
    import_file(db, fixtures_dir / "paypal_demo.CSV")
    tag = Tag(name="Erstattungsfähig", color="#fbbf24")
    db.add(tag)
    db.flush()
    transaction = db.scalars(
        select(Transaction).where(Transaction.transaction_id == "5KJ72910MC844213X")
    ).one()
    db.add(TransactionTag(transaction_id=transaction.id, tag_id=tag.id))
    db.flush()

    import_file(db, generated_dir / "paypal_reimport_overlap.csv")

    db.refresh(transaction)
    assert transaction.user_categorized is False
    assert [t.name for t in transaction.tags] == ["Erstattungsfähig"]


def test_ing_reimport_keeps_tags(db: Session, fixtures_dir: Path) -> None:
    import_file(db, fixtures_dir / "ing_demo.csv")
    tag = Tag(name="Wiederkehrend", color="#818cf8")
    db.add(tag)
    db.flush()
    transaction = db.scalars(select(Transaction)).first()
    db.add(TransactionTag(transaction_id=transaction.id, tag_id=tag.id))
    db.flush()

    import_file(db, fixtures_dir / "ing_demo.csv")

    db.refresh(transaction)
    assert [t.name for t in transaction.tags] == ["Wiederkehrend"]


# --- Categorization on insert ----------------------------------------------


def test_new_rows_run_through_the_categorizer(db: Session, fixtures_dir: Path) -> None:
    category = make_category(db, "Einkommen")
    db.add(
        CategoryRule(
            keyword="gehalt/rente", field="transaction_type", category_id=category.id, priority=0
        )
    )
    db.flush()

    import_file(db, fixtures_dir / "ing_demo.csv")

    salary = db.scalars(
        select(Transaction).where(Transaction.transaction_type == "Gehalt/Rente")
    ).one()
    assert salary.category_id == category.id
    # Auto-categorization is not a user decision.
    assert salary.user_categorized is False


def test_existing_rows_do_not_run_through_the_categorizer(
    db: Session, fixtures_dir: Path, generated_dir: Path
) -> None:
    import_file(db, fixtures_dir / "paypal_demo.CSV")
    category = make_category(db, "Gesundheit")
    # Matches both the rows already held and the one this import adds.
    db.add(CategoryRule(keyword="GmbH", field="description", category_id=category.id))
    db.flush()

    import_file(db, generated_dir / "paypal_reimport_overlap.csv")

    held = db.scalars(
        select(Transaction).where(Transaction.transaction_id == "5KJ72910MC844213X")
    ).one()
    inserted = db.scalars(
        select(Transaction).where(Transaction.transaction_id == "6KM40218TY9931845")
    ).one()
    assert "GmbH" in held.description and held.category_id is None
    assert inserted.category_id == category.id


def test_import_never_writes_exclude_from_stats(db: Session, fixtures_dir: Path) -> None:
    import_file(db, fixtures_dir / "ing_demo.csv")

    excluded = db.scalars(
        select(func.count()).select_from(Transaction).where(Transaction.exclude_from_stats)
    ).one()
    assert excluded == 0
