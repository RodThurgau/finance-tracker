"""Default categories and tags for a fresh database.

Seeding runs in the lifespan handler after migrations, and only when the
database is still empty — it is a starting point for a new install, not a set of
rows the app depends on. Everything here is user-editable afterwards, so nothing
in the codebase may look these up by name or id.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Category, Subcategory, Tag

# (name, color, subcategory names). German, matching the UI language.
SEED_CATEGORIES: list[tuple[str, str, list[str]]] = [
    ("Wohnen", "#38bdf8", ["Miete", "Nebenkosten", "Versicherung"]),
    ("Essen & Trinken", "#fb923c", ["Lebensmittel", "Restaurants", "Kaffee", "Lieferdienst"]),
    ("Transport", "#a78bfa", ["Öffentliche Verkehrsmittel", "Kraftstoff", "Autowerkstatt"]),
    ("Einkaufen", "#f472b6", ["Kleidung", "Elektronik", "Haushalt"]),
    ("Gesundheit", "#4ade80", ["Apotheke", "Arzt", "Fitnessstudio"]),
    ("Unterhaltung", "#facc15", ["Abonnements", "Ausgehen", "Hobbys"]),
    ("Finanzen", "#60a5fa", ["Gebühren", "Überweisungen", "Sparen"]),
    ("Einkommen", "#34d399", ["Gehalt", "Freiberuflich", "Rückerstattungen"]),
    ("Nicht kategorisiert", "#94a3b8", ["Sonstiges"]),
]

# (name, color)
SEED_TAGS: list[tuple[str, str]] = [
    ("Gemeinsame Ausgabe", "#22d3ee"),
    ("Für andere bezahlt", "#c084fc"),
    ("Erstattungsfähig", "#fbbf24"),
    ("Wiederkehrend", "#818cf8"),
]


@dataclass(frozen=True)
class SeedResult:
    """What seeding did, for the startup log."""

    categories: int
    subcategories: int
    tags: int

    @property
    def skipped(self) -> bool:
        """True when the database already held data and nothing was written."""
        return not (self.categories or self.subcategories or self.tags)


def is_empty(session: Session) -> bool:
    """True when neither categories nor tags exist yet.

    Deliberately coarse: a user who has deleted every category and tag gets the
    defaults back on the next start, which is the intended way to reset them.
    """
    has_category = session.scalar(select(Category.id).limit(1)) is not None
    has_tag = session.scalar(select(Tag.id).limit(1)) is not None
    return not (has_category or has_tag)


def seed_database(session: Session) -> SeedResult:
    """Insert the default categories and tags if the database is still empty.

    Commits on success. Returns a zero-count result when seeding was skipped, so
    calling this on every startup is safe.
    """
    if not is_empty(session):
        return SeedResult(categories=0, subcategories=0, tags=0)

    subcategory_count = 0
    for name, color, subcategory_names in SEED_CATEGORIES:
        category = Category(
            name=name,
            color=color,
            subcategories=[Subcategory(name=sub) for sub in subcategory_names],
        )
        subcategory_count += len(subcategory_names)
        session.add(category)

    for name, color in SEED_TAGS:
        session.add(Tag(name=name, color=color))

    session.commit()
    return SeedResult(
        categories=len(SEED_CATEGORIES),
        subcategories=subcategory_count,
        tags=len(SEED_TAGS),
    )
