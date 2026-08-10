from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer


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


class Category(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subcategories: list[Subcategory] = []


class TagBase(BaseModel):
    name: str
    color: str | None = None


class TagCreate(TagBase):
    pass


class Tag(TagBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


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


class CategoryRuleBase(BaseModel):
    keyword: str
    field: str = "description"
    category_id: int
    subcategory_id: int | None = None
    priority: int = 0


class CategoryRuleCreate(CategoryRuleBase):
    pass


class CategoryRule(CategoryRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
