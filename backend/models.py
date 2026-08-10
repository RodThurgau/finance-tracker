from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from money import DecimalAmount


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    color: Mapped[str | None] = mapped_column(String, nullable=True)

    subcategories: Mapped[list["Subcategory"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class Subcategory(Base):
    __tablename__ = "subcategories"
    __table_args__ = (UniqueConstraint("category_id", "name", name="uq_subcategory_name_per_category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

    category: Mapped["Category"] = relationship(back_populates="subcategories")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    color: Mapped[str | None] = mapped_column(String, nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_transaction_transaction_id"),
        UniqueConstraint("composite_hash", name="uq_transaction_composite_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(String, nullable=True)
    composite_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    original_description: Mapped[str | None] = mapped_column(String, nullable=True)
    amount: Mapped[Decimal] = mapped_column(DecimalAmount, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="EUR")
    counter_account: Mapped[str | None] = mapped_column(String, nullable=True)
    transaction_type: Mapped[str | None] = mapped_column(String, nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("subcategories.id"), nullable=True)
    user_categorized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exclude_from_stats: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    category: Mapped["Category | None"] = relationship()
    subcategory: Mapped["Subcategory | None"] = relationship()
    tags: Mapped[list["Tag"]] = relationship(secondary="transaction_tags")


class TransactionTag(Base):
    __tablename__ = "transaction_tags"

    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), primary_key=True)


class CategoryRule(Base):
    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String, nullable=False)
    field: Mapped[str] = mapped_column(String, nullable=False, default="description")
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("subcategories.id"), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    category: Mapped["Category"] = relationship()
    subcategory: Mapped["Subcategory | None"] = relationship()
