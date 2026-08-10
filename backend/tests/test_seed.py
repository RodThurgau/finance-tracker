"""Seeding runs once, on an empty database, and never twice."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Category, Subcategory, Tag
from seed import SEED_CATEGORIES, SEED_TAGS, is_empty, seed_database


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_seeds_an_empty_database(db: Session) -> None:
    result = seed_database(db)

    assert not result.skipped
    assert count(db, Category) == len(SEED_CATEGORIES)
    assert count(db, Tag) == len(SEED_TAGS)
    assert count(db, Subcategory) == sum(len(subs) for _, _, subs in SEED_CATEGORIES)


def test_categories_keep_their_subcategories(db: Session) -> None:
    seed_database(db)

    wohnen = db.scalar(select(Category).where(Category.name == "Wohnen"))
    assert wohnen is not None
    assert [sub.name for sub in wohnen.subcategories] == ["Miete", "Nebenkosten", "Versicherung"]
    assert wohnen.color == "#38bdf8"


def test_second_run_is_a_no_op(db: Session) -> None:
    seed_database(db)

    result = seed_database(db)

    assert result.skipped
    assert count(db, Category) == len(SEED_CATEGORIES)
    assert count(db, Tag) == len(SEED_TAGS)


def test_a_database_with_only_tags_is_not_empty(db: Session) -> None:
    db.add(Tag(name="Eigener Tag", color="#ffffff"))
    db.flush()

    assert not is_empty(db)
    assert seed_database(db).skipped
    assert count(db, Category) == 0


def test_seed_names_are_unique(db: Session) -> None:
    category_names = [name for name, _, _ in SEED_CATEGORIES]
    tag_names = [name for name, _ in SEED_TAGS]

    assert len(set(category_names)) == len(category_names)
    assert len(set(tag_names)) == len(tag_names)
