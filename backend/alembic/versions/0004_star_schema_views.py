"""star schema views for Power BI

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-06

SQL views that present the transactional data as a classic star schema —
FactTransaction at the center, surrounded by DimCategory, DimSubcategory,
DimDate, DimVendor, DimTag, and a BridgeTransactionTag for the many-to-many.
PascalCase column names throughout, amounts in euros (not integer cents), and
an IsInternalTransfer flag computed from the same logic as
`services/internal_transfers.py`.

These are read-only views over the existing tables. The application does not
use them; they exist so Power BI (or any other analytics tool) can connect to
the SQLite file and find a clean relational model ready to go.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIM_CATEGORY = """\
CREATE VIEW DimCategory AS
SELECT
    id          AS CategoryKey,
    name        AS CategoryName,
    color       AS Color
FROM categories
"""

DIM_SUBCATEGORY = """\
CREATE VIEW DimSubcategory AS
SELECT
    s.id          AS SubcategoryKey,
    s.name        AS SubcategoryName,
    s.category_id AS CategoryKey,
    c.name        AS CategoryName
FROM subcategories s
LEFT JOIN categories c ON c.id = s.category_id
"""

DIM_TAG = """\
CREATE VIEW DimTag AS
SELECT
    id    AS TagKey,
    name  AS TagName,
    color AS Color
FROM tags
"""

DIM_DATE = """\
CREATE VIEW DimDate AS
SELECT DISTINCT
    date AS DateKey,
    date AS FullDate,
    CAST(strftime('%Y', date) AS INTEGER) AS Year,
    CAST(strftime('%m', date) AS INTEGER) AS MonthNumber,
    CASE CAST(strftime('%m', date) AS INTEGER)
        WHEN 1  THEN 'Januar'    WHEN 2  THEN 'Februar'
        WHEN 3  THEN 'März'      WHEN 4  THEN 'April'
        WHEN 5  THEN 'Mai'       WHEN 6  THEN 'Juni'
        WHEN 7  THEN 'Juli'      WHEN 8  THEN 'August'
        WHEN 9  THEN 'September' WHEN 10 THEN 'Oktober'
        WHEN 11 THEN 'November'  WHEN 12 THEN 'Dezember'
    END AS MonthName,
    CAST((CAST(strftime('%m', date) AS INTEGER) + 2) / 3 AS INTEGER) AS Quarter,
    'Q' || CAST((CAST(strftime('%m', date) AS INTEGER) + 2) / 3 AS INTEGER) AS QuarterName,
    CAST(strftime('%w', date) AS INTEGER) AS DayOfWeek,
    CASE CAST(strftime('%w', date) AS INTEGER)
        WHEN 0 THEN 'Sonntag'     WHEN 1 THEN 'Montag'
        WHEN 2 THEN 'Dienstag'    WHEN 3 THEN 'Mittwoch'
        WHEN 4 THEN 'Donnerstag'  WHEN 5 THEN 'Freitag'
        WHEN 6 THEN 'Samstag'
    END AS DayName,
    CAST(strftime('%j', date) AS INTEGER) AS DayOfYear,
    CAST(strftime('%W', date) AS INTEGER) AS WeekOfYear,
    strftime('%Y-%m', date) AS YearMonth
FROM transactions
"""

DIM_VENDOR = """\
CREATE VIEW DimVendor AS
SELECT DISTINCT
    t.counter_account                          AS VendorKey,
    t.counter_account                          AS RawName,
    COALESCE(m.display_name, t.counter_account) AS DisplayName
FROM transactions t
LEFT JOIN merchant_mappings m ON m.raw_name = t.counter_account
WHERE t.counter_account IS NOT NULL
"""

FACT_TRANSACTION = """\
CREATE VIEW FactTransaction AS
SELECT
    t.id                    AS TransactionKey,
    t.date                  AS DateKey,
    t.category_id           AS CategoryKey,
    t.subcategory_id        AS SubcategoryKey,
    t.counter_account       AS VendorKey,
    ROUND(CAST(t.amount AS REAL) / 100.0, 2) AS Amount,
    t.currency              AS Currency,
    t.source                AS Source,
    t.transaction_type      AS TransactionType,
    t.description           AS Description,
    t.original_description  AS OriginalDescription,
    t.exclude_from_stats    AS IsExcludedFromStats,
    t.user_categorized      AS IsUserCategorized,
    CASE
        WHEN (t.source = 'ING'
              AND t.counter_account IS NOT NULL
              AND LOWER(t.counter_account) LIKE '%paypal%')
          OR (t.source = 'PayPal'
              AND t.transaction_type IS NOT NULL
              AND LOWER(t.transaction_type) = LOWER('Bankgutschrift auf PayPal-Konto'))
        THEN 1 ELSE 0
    END AS IsInternalTransfer
FROM transactions t
"""

BRIDGE_TRANSACTION_TAG = """\
CREATE VIEW BridgeTransactionTag AS
SELECT
    transaction_id AS TransactionKey,
    tag_id         AS TagKey
FROM transaction_tags
"""

VIEWS = [
    "DimCategory",
    "DimSubcategory",
    "DimTag",
    "DimDate",
    "DimVendor",
    "FactTransaction",
    "BridgeTransactionTag",
]


def upgrade() -> None:
    for sql in [
        DIM_CATEGORY,
        DIM_SUBCATEGORY,
        DIM_TAG,
        DIM_DATE,
        DIM_VENDOR,
        FACT_TRANSACTION,
        BRIDGE_TRANSACTION_TAG,
    ]:
        op.execute(sql)


def downgrade() -> None:
    for name in reversed(VIEWS):
        op.execute(f"DROP VIEW IF EXISTS {name}")
