from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer

from services.categorizer import RuleField


class AmountModel(BaseModel):
    """Base for schemas carrying a Decimal amount, serialized as a string."""

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("amount", when_used="always", check_fields=False)
    def serialize_amount(self, value: Decimal) -> str:
        return str(value)


class SubcategoryBase(BaseModel):
    name: str


class SubcategoryCreate(SubcategoryBase):
    pass


class Subcategory(SubcategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int


class CategoryBase(BaseModel):
    name: str
    color: str | None = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class Category(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subcategories: list[Subcategory] = []


class CategoryWithCount(Category):
    transaction_count: int


class TagBase(BaseModel):
    name: str
    color: str | None = None


class TagCreate(TagBase):
    pass


class Tag(TagBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TagWithCount(Tag):
    usage_count: int


class TagLink(BaseModel):
    tag_id: int


class TransactionBase(BaseModel):
    source: str
    transaction_id: str | None = None
    composite_hash: str | None = None
    date: date_type
    description: str
    original_description: str | None = None
    amount: Decimal
    currency: str = "EUR"
    counter_account: str | None = None
    transaction_type: str | None = None
    category_id: int | None = None
    subcategory_id: int | None = None
    user_categorized: bool = False
    exclude_from_stats: bool = False


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    category_id: int | None = None
    subcategory_id: int | None = None
    exclude_from_stats: bool | None = None


class Transaction(TransactionBase, AmountModel):
    id: int
    tags: list[Tag] = []


class TransactionListResponse(BaseModel):
    items: list[Transaction]
    total: int


class TransactionBulkUpdate(BaseModel):
    ids: list[int]
    category_id: int | None = None
    subcategory_id: int | None = None
    exclude_from_stats: bool | None = None


class BulkUpdateResult(BaseModel):
    updated: int


class CategoryRuleBase(BaseModel):
    keyword: str
    field: RuleField = RuleField.DESCRIPTION
    category_id: int
    subcategory_id: int | None = None
    priority: int = 0


class CategoryRuleCreate(CategoryRuleBase):
    pass


class CategoryRuleUpdate(BaseModel):
    keyword: str | None = None
    field: RuleField | None = None
    category_id: int | None = None
    subcategory_id: int | None = None
    priority: int | None = None


class CategoryRule(CategoryRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class CategoryRuleWithNames(CategoryRule):
    category_name: str
    subcategory_name: str | None = None


class RulesApplyResult(BaseModel):
    categorized: int


class CategorySpendEntry(BaseModel):
    category_id: int | None
    category_name: str | None
    total: Decimal

    @field_serializer("total")
    def serialize_total(self, value: Decimal) -> str:
        return str(value)


class MonthlySummaryEntry(BaseModel):
    month: str
    income: Decimal
    expenses: Decimal

    @field_serializer("income", "expenses")
    def serialize_amounts(self, value: Decimal) -> str:
        return str(value)


class MerchantSpendEntry(BaseModel):
    counter_account: str
    total: Decimal

    @field_serializer("total")
    def serialize_total(self, value: Decimal) -> str:
        return str(value)


class StatsSummary(BaseModel):
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal
    by_category: list[CategorySpendEntry]
    by_month: list[MonthlySummaryEntry]
    top_merchants: list[MerchantSpendEntry]

    @field_serializer("total_income", "total_expenses", "net")
    def serialize_totals(self, value: Decimal) -> str:
        return str(value)


class RowErrorSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row_number: int
    column: str
    value: str
    message: str


class ImportPreviewRow(AmountModel):
    """One parsed row shown before the user commits to importing."""

    date: date_type
    description: str
    amount: Decimal
    currency: str
    counter_account: str | None = None
    transaction_type: str | None = None


class ImportPreviewSchema(BaseModel):
    source: str
    preamble_lines: list[str]
    rows: list[ImportPreviewRow]
    total_rows: int
    errors: list[RowErrorSchema]


class SkippedRowSchema(AmountModel):
    row_number: int
    composite_hash: str
    date: date_type
    description: str
    amount: Decimal


class ImportSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    new: int
    updated: int
    skipped: int
    errors: list[RowErrorSchema]
    date_range: tuple[date_type, date_type] | None
    skipped_rows: list[SkippedRowSchema]
