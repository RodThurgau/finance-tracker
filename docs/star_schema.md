# Star Schema — Power BI Model

SQL views over the application tables, created by migration `0004`. They present
the transactional data as a classic star schema so Power BI (or any ODBC/JDBC
tool) can connect directly to `data/finance.db` and find a clean relational
model.

The views are **read-only** and do not affect the application. They are
maintained by Alembic alongside the tables they sit on top of.

## Schema diagram

```
                        ┌──────────────────┐
                        │    DimCategory    │
                        ├──────────────────┤
                        │ CategoryKey  (PK)│
                        │ CategoryName     │
                        │ Color            │
                        └────────┬─────────┘
                                 │
┌──────────────────┐    ┌────────┴─────────┐    ┌──────────────────┐
│  DimSubcategory  │    │  FactTransaction │    │     DimDate      │
├──────────────────┤    ├──────────────────┤    ├──────────────────┤
│SubcategoryKey(PK)│◄───┤ TransactionKey PK│───►│ DateKey      (PK)│
│ SubcategoryName  │    │ DateKey       FK │    │ FullDate         │
│ CategoryKey   FK │    │ CategoryKey   FK │    │ Year             │
│ CategoryName     │    │ SubcategoryKey FK│    │ MonthNumber      │
└──────────────────┘    │ VendorKey     FK │    │ MonthName        │
                        │ Amount  (EUR)    │    │ Quarter          │
┌──────────────────┐    │ Currency         │    │ QuarterName      │
│    DimVendor     │    │ Source           │    │ DayOfWeek        │
├──────────────────┤    │ TransactionType  │    │ DayName          │
│ VendorKey    (PK)│◄───┤ Description      │    │ DayOfYear        │
│ RawName          │    │ OriginalDescr.   │    │ WeekOfYear       │
│ DisplayName      │    │ IsExcludedFrom…  │    │ YearMonth        │
└──────────────────┘    │ IsUserCategorized│    └──────────────────┘
                        │ IsInternalTransf.│
┌──────────────────┐    └────────┬─────────┘    ┌──────────────────┐
│     DimTag       │             │              │BridgeTransaction │
├──────────────────┤             │              │       Tag        │
│ TagKey       (PK)│◄────────────┼──────────────├──────────────────┤
│ TagName          │             └─────────────►│ TransactionKey FK│
│ Color            │                            │ TagKey         FK│
└──────────────────┘                            └──────────────────┘
```

## View definitions

### FactTransaction

The central fact table. One row per transaction.

| Column               | Type    | Source                                                     |
|----------------------|---------|------------------------------------------------------------|
| TransactionKey       | INTEGER | `transactions.id`                                          |
| DateKey              | DATE    | `transactions.date` → joins to `DimDate.DateKey`           |
| CategoryKey          | INTEGER | `transactions.category_id` → joins to `DimCategory`        |
| SubcategoryKey       | INTEGER | `transactions.subcategory_id` → joins to `DimSubcategory`  |
| VendorKey            | TEXT    | `transactions.counter_account` → joins to `DimVendor`      |
| Amount               | REAL    | Euros (stored cents ÷ 100), rounded to 2 decimals          |
| Currency             | TEXT    | Always `EUR` for now                                       |
| Source               | TEXT    | `ING` or `PayPal`                                          |
| TransactionType      | TEXT    | ING `Buchungstext` / PayPal `Beschreibung`                 |
| Description          | TEXT    | Cleaned description                                        |
| OriginalDescription  | TEXT    | Raw description from the CSV                               |
| IsExcludedFromStats  | BOOLEAN | User-set flag to hide from all aggregates                  |
| IsUserCategorized    | BOOLEAN | `True` if the user manually assigned the category          |
| IsInternalTransfer   | BOOLEAN | Computed: the PayPal/ING funding legs (see CLAUDE.md)      |

**Amount** is in euros, not integer cents. The underlying column stores cents;
the view divides by 100 so Power BI gets a usable number without manual
transformation. `ROUND(CAST(amount AS REAL) / 100.0, 2)`.

**IsInternalTransfer** mirrors the logic in `services/internal_transfers.py`:
ING rows whose `counter_account` contains `paypal` (case-insensitive), and
PayPal rows whose `transaction_type` is `Bankgutschrift auf PayPal-Konto`.
Filter these out in Power BI the same way the app does.

### DimCategory

| Column       | Type    | Notes              |
|--------------|---------|--------------------|
| CategoryKey  | INTEGER | PK, from `categories.id` |
| CategoryName | TEXT    | Unique             |
| Color        | TEXT    | Hex color code     |

### DimSubcategory

| Column          | Type    | Notes                              |
|-----------------|---------|------------------------------------|
| SubcategoryKey  | INTEGER | PK, from `subcategories.id`        |
| SubcategoryName | TEXT    |                                    |
| CategoryKey     | INTEGER | FK → `DimCategory.CategoryKey`     |
| CategoryName    | TEXT    | Denormalized for slicer convenience|

### DimDate

Derived from `DISTINCT transactions.date`. Only dates with at least one
transaction appear. Power BI can extend this with a DAX calendar table if a
complete date range is needed.

| Column      | Type    | Notes                                    |
|-------------|---------|------------------------------------------|
| DateKey     | DATE    | PK, the transaction date                 |
| FullDate    | DATE    | Same value, aliased for clarity          |
| Year        | INTEGER | e.g. 2026                                |
| MonthNumber | INTEGER | 1–12                                     |
| MonthName   | TEXT    | German: Januar, Februar, …               |
| Quarter     | INTEGER | 1–4                                      |
| QuarterName | TEXT    | Q1–Q4                                    |
| DayOfWeek   | INTEGER | 0 = Sonntag, 6 = Samstag                 |
| DayName     | TEXT    | German: Montag, Dienstag, …              |
| DayOfYear   | INTEGER | 1–366                                    |
| WeekOfYear  | INTEGER | ISO week number                          |
| YearMonth   | TEXT    | `YYYY-MM`, sorts correctly as text       |

### DimVendor

Derived from `DISTINCT transactions.counter_account`, joined to
`merchant_mappings` for the display name.

| Column      | Type | Notes                                            |
|-------------|------|--------------------------------------------------|
| VendorKey   | TEXT | PK, the raw `counter_account` value              |
| RawName     | TEXT | Same as VendorKey                                |
| DisplayName | TEXT | `merchant_mappings.display_name`, or RawName     |

### DimTag

| Column  | Type    | Notes                 |
|---------|---------|-----------------------|
| TagKey  | INTEGER | PK, from `tags.id`    |
| TagName | TEXT    | Unique                |
| Color   | TEXT    | Hex color code        |

### BridgeTransactionTag

Many-to-many bridge between `FactTransaction` and `DimTag`.

| Column         | Type    | Notes                                  |
|----------------|---------|----------------------------------------|
| TransactionKey | INTEGER | FK → `FactTransaction.TransactionKey`  |
| TagKey         | INTEGER | FK → `DimTag.TagKey`                   |

## Connecting Power BI

1. Install an ODBC driver for SQLite (e.g. the one from
   [ch-werner.de](http://www.ch-werner.de/sqliteodbc/)).
2. In Power BI Desktop: Get Data → ODBC → point at `data/finance.db`.
3. Select the views (`DimCategory`, `DimDate`, `DimVendor`, `DimTag`,
   `DimSubcategory`, `FactTransaction`, `BridgeTransactionTag`).
4. In the model view, verify the relationships:
   - `FactTransaction.DateKey` → `DimDate.DateKey`
   - `FactTransaction.CategoryKey` → `DimCategory.CategoryKey`
   - `FactTransaction.SubcategoryKey` → `DimSubcategory.SubcategoryKey`
   - `FactTransaction.VendorKey` → `DimVendor.VendorKey`
   - `BridgeTransactionTag.TransactionKey` → `FactTransaction.TransactionKey`
   - `BridgeTransactionTag.TagKey` → `DimTag.TagKey`
5. Add a filter on `IsInternalTransfer = 0` and `IsExcludedFromStats = 0` to
   match the app's default aggregation.

## Recommended DAX measures

```dax
Total Expenses = CALCULATE(SUM(FactTransaction[Amount]), FactTransaction[Amount] < 0)
Total Income   = CALCULATE(SUM(FactTransaction[Amount]), FactTransaction[Amount] > 0)
Net            = SUM(FactTransaction[Amount])
```
