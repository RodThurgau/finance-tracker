from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Integer
from sqlalchemy.types import TypeDecorator

CENTS = Decimal("0.01")


class DecimalAmount(TypeDecorator):
    """Decimal in Python, INTEGER cents in SQLite."""

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect) -> int | None:
        if value is None:
            return None
        quantized = Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)
        return int(quantized * 100)

    def process_result_value(self, value: int | None, dialect) -> Decimal | None:
        if value is None:
            return None
        return (Decimal(value) / 100).quantize(CENTS, rounding=ROUND_HALF_UP)
