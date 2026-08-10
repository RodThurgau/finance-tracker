# CLAUDE.md — Finance Tracker

## Project overview

A local-first personal finance tracker that ingests ING (DE) and PayPal CSV exports, normalizes them into a common schema, stores everything in SQLite, and serves a React UI for browsing, categorizing, tagging, and exporting transaction data.

This is a personal tool — single user, no auth, no cloud, no multi-tenancy.

## Stack

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy (ORM), Alembic (migrations), SQLite
- **Frontend:** React 18+ (Vite), Tailwind CSS, Recharts
- **Database:** SQLite single-file (`data/finance.db`)
- **Package management:** uv (backend), npm (frontend)

## Project structure

```
finance-tracker/
├── backend/
│   ├── main.py                  # FastAPI app, CORS, lifespan
│   ├── database.py              # SQLAlchemy engine, session, Base
│   ├── models.py                # ORM models
│   ├── money.py                 # DecimalAmount TypeDecorator
│   ├── schemas.py               # Pydantic request/response schemas
│   ├── backup.py                # Pre-migration DB snapshot
│   ├── routers/
│   │   ├── transactions.py      # CRUD, filtering, bulk update
│   │   ├── categories.py        # Category + subcategory management
│   │   ├── tags.py              # Tag CRUD
│   │   ├── imports.py           # CSV upload + upsert logic
│   │   ├── rules.py             # Categorization rules CRUD
│   │   └── export.py            # Filtered CSV export
│   ├── parsers/
│   │   ├── preclean.py          # Strip metadata preamble, locate header row
│   │   ├── detect.py            # Auto-detect source from header row
│   │   ├── ing.py               # ING DE CSV → common schema
│   │   └── paypal.py            # PayPal CSV → common schema
│   ├── services/
│   │   ├── categorizer.py       # Apply rules to transactions
│   │   └── upsert.py            # Upsert logic per source
│   ├── alembic/
│   │   ├── versions/
│   │   └── env.py
│   ├── alembic.ini
│   ├── tests/
│   │   ├── fixtures/            # Synthetic CSVs only — never real exports
│   │   │   ├── ing_demo.csv     # ← drop the hand-written demo file here
│   │   │   ├── paypal_demo.csv  # ← drop the hand-written demo file here
│   │   │   └── generated/       # Variants produced by make_fixtures.py
│   │   ├── make_fixtures.py     # Derives variants from the two demo files
│   │   ├── test_preclean.py
│   │   ├── test_parsers.py
│   │   └── test_upsert.py
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── Transactions.jsx
│   │   │   ├── Overview.jsx
│   │   │   ├── Categories.jsx
│   │   │   ├── Tags.jsx
│   │   │   └── ImportExport.jsx
│   │   ├── components/          # Reusable UI components
│   │   └── api/                 # Fetch wrappers for backend
│   ├── package.json
│   └── vite.config.js
├── data/
│   └── finance.db               # Created at first run
├── backups/                     # Timestamped DB snapshots (gitignored)
├── imports/                     # Optional: drop CSVs here
├── CLAUDE.md
├── PLAN.md
└── README.md
```

`.gitignore` must include `data/`, `backups/`, `imports/`, and any real bank export. Only synthetic fixtures are ever committed.

## Money representation

`amount` is a `Decimal` everywhere in application code. Never a `float`.

SQLite has no exact decimal type, and SQLAlchemy's plain `Numeric` round-trips through float on SQLite (and warns about it), which defeats the point. So amounts go through a `TypeDecorator` in `backend/money.py` (named to avoid shadowing Python's stdlib `types` module, which would otherwise break on import since `backend/` sits on `sys.path`):

- **Python side:** `Decimal`, quantized to 2 places (`ROUND_HALF_UP`).
- **SQLite side:** `INTEGER` cents. Integer storage keeps `ORDER BY amount`, `min_amount`/`max_amount` range filters, and `SUM()` exact and correct.

Rules:

- Parsers produce `Decimal`, built from the **string** in the CSV — never `float(...)`.
- Pydantic schemas declare `Decimal`. JSON-serialize amounts as **strings** so JavaScript's float parsing can't touch them.
- The frontend formats amounts for display (`Intl.NumberFormat`) and does no arithmetic on them. All aggregation happens server-side.
- Stats endpoints sum in integer cents and convert once, at serialization.

## Database schema

Six tables. All IDs are integers with autoincrement. Schema changes go through Alembic — see "Migrations".

### `categories`

| Column | Type    | Notes            |
|--------|---------|------------------|
| id     | INTEGER | PK               |
| name   | TEXT    | Unique, not null |
| color  | TEXT    | Hex color code   |

### `subcategories`

| Column      | Type    | Notes                     |
|-------------|---------|---------------------------|
| id          | INTEGER | PK                        |
| category_id | INTEGER | FK → categories.id        |
| name        | TEXT    | Unique within category    |

### `transactions`

| Column           | Type    | Notes                                        |
|------------------|---------|----------------------------------------------|
| id               | INTEGER | PK                                           |
| source           | TEXT    | "ING" or "PayPal"                            |
| transaction_id   | TEXT    | Nullable. PayPal's native ID                 |
| composite_hash   | TEXT    | Generated for ING rows. Indexed              |
| date             | DATE    | Transaction date (ING: `Buchung`)            |
| description      | TEXT    | Cleaned description                          |
| original_description | TEXT | Raw description field from CSV              |
| amount           | DECIMAL | Decimal(12,2) in Python, INTEGER cents in SQLite. Signed: negative = expense |
| currency         | TEXT    | Default "EUR"                                |
| counter_account  | TEXT    | Nullable. ING `Auftraggeber/Empfänger` / PayPal email |
| transaction_type | TEXT    | ING `Buchungstext` (e.g. "Lastschrift", "Kartenzahlung") / "PayPal" |
| category_id      | INTEGER | FK → categories.id. Nullable                 |
| subcategory_id   | INTEGER | FK → subcategories.id. Nullable              |
| user_categorized | BOOLEAN | True if user manually set category           |
| exclude_from_stats | BOOLEAN | Default False. Row is hidden from all aggregates |

Unique constraints:
- `transaction_id` (where not null) — PayPal dedup
- `composite_hash` (where not null) — ING dedup

**`exclude_from_stats`:** set by the user, never by the importer. A row with this flag still appears in the transaction list and in CSV exports; it is filtered out of every aggregate in `/stats/summary`. Intended for rows that would otherwise be double-counted or would distort totals — the ING debit that funds a PayPal purchase, transfers between your own accounts, and so on. It is orthogonal to `user_categorized` and to categories: excluding a row does not change its category, and recategorizing does not clear the flag.

### `tags`

| Column | Type    | Notes            |
|--------|---------|------------------|
| id     | INTEGER | PK               |
| name   | TEXT    | Unique, not null |
| color  | TEXT    | Hex color code   |

### `transaction_tags`

| Column         | Type    | Notes                 |
|----------------|---------|---------------------- |
| transaction_id | INTEGER | FK → transactions.id  |
| tag_id         | INTEGER | FK → tags.id          |

Composite PK on (transaction_id, tag_id).

### `category_rules`

| Column         | Type    | Notes                                        |
|----------------|---------|----------------------------------------------|
| id             | INTEGER | PK                                           |
| keyword        | TEXT    | Case-insensitive substring match             |
| field          | TEXT    | Which transaction field to match against. One of `description`, `counter_account`, `transaction_type`. Default `description` |
| category_id    | INTEGER | FK → categories.id                           |
| subcategory_id | INTEGER | FK → subcategories.id. Nullable              |
| priority       | INTEGER | Higher = matched first. Default 0            |

`field` is validated by a Pydantic enum on write. A rule whose `field` is NULL on an old row is treated as `description`. If the target field is NULL on a transaction, the rule simply does not match.

## Migrations

Alembic owns the schema. Tables are **not** created with `Base.metadata.create_all()` in application code.

- On startup: take a backup (below), then run `alembic upgrade head` programmatically. A fresh database gets built from migration `0001` like any other.
- Every model change ships with a migration in the same commit. Autogenerate is a starting point, not the answer — review the generated file, especially for SQLite's limited `ALTER TABLE` (Alembic's batch mode is required for column drops, type changes, and constraint changes).
- Never edit a migration that has already been applied to `data/finance.db`. Write a new one.

## Backups

The CSVs are re-downloadable; months of manual categorization are not.

- `backup.py` runs in the FastAPI lifespan handler **before** Alembic, on every startup.
- It copies `data/finance.db` to `backups/finance-YYYYMMDD-HHMMSS.db` using SQLite's backup API (or `VACUUM INTO`) so the snapshot is consistent even if a connection is open.
- Retention: keep the most recent 20 snapshots plus the first snapshot of each day for the last 30 days. Prune the rest.
- Startup aborts loudly if the backup fails. Do not migrate an unbacked database.
- Restore is a documented manual step in README: stop the server, copy a snapshot over `data/finance.db`, restart.

## CSV preclean

Both sources ship files that are not valid CSV from byte zero. ING DE exports begin with a metadata preamble (account holder, IBAN, export date range, sort order, blank lines) before the real header row. Preclean runs before detection and before parsing, and is the only place that touches raw bytes.

`preclean.py` responsibilities:

1. Read the file as bytes. Strip a UTF-8 BOM if present.
2. Decode: try UTF-8, fall back to Latin-1.
3. Scan lines from the top for the **header row** — the first line that contains all of a source's required column names. Everything above it is the preamble and is discarded.
4. Drop blank lines and any trailing blank/footer lines.
5. Return a `PrecleanResult`: `{ header_line: str, data_lines: list[str], delimiter: str, encoding: str, preamble_lines: list[str], header_line_number: int }`.
6. Raise a typed `NoHeaderFound` error if no candidate header appears in the first 40 lines. The import endpoint turns this into a 422 with the first few preamble lines echoed back, so a wrong file is obvious.

The preamble is not stored. It is returned only so the import preview can show what was skipped.

## CSV formats

### ING (Germany)

Semicolon-separated, UTF-8 or Latin-1, metadata preamble before the header. Header row:

```
Buchung;Wertstellungsdatum;Auftraggeber/Empfänger;Buchungstext;Verwendungszweck;Betrag;Währung
```

Detection requires all seven names to be present in the header row. Additional trailing columns (some exports add `Saldo`, `Währung` twice, etc.) are tolerated and ignored.

**Column types and mapping.** Every field is read as a string and converted explicitly. No type inference, ever.

| CSV column | Raw form | Parsed as | Target |
|------------|----------|-----------|--------|
| `Buchung` | `DD.MM.YYYY` | `date` | `transactions.date` |
| `Wertstellungsdatum` | `DD.MM.YYYY` | `date` | not stored (parsed only to validate the row) |
| `Auftraggeber/Empfänger` | text | `str` | `counter_account`, and prefix of `description` |
| `Buchungstext` | text | `str` | `transaction_type` |
| `Verwendungszweck` | text | `str` | `original_description`, and suffix of `description` |
| `Betrag` | `-1.234,56` | `Decimal` | `amount` |
| `Währung` | `EUR` | `str` | `currency` |

Notes:

- `Betrag` is **already signed** — a leading `-` means expense. There is no `Af Bij` equivalent; do not flip signs.
- `Betrag` uses `.` as thousands separator and `,` as decimal separator. Convert by removing `.` then replacing `,` with `.`, and pass the resulting **string** to `Decimal`.
- `description` is `f"{Auftraggeber/Empfänger} — {Verwendungszweck}"` with internal whitespace collapsed. Keeping the counterparty in `description` is what makes search and description-based rules useful; `original_description` stays the untouched `Verwendungszweck`.
- Rows where `Buchung` or `Betrag` fail to parse are collected as row-level errors, not silently dropped.

**Composite hash.** ING DE gives no transaction ID, so dedup is a hash. The definition below is frozen — changing any part of it turns every future import into a full re-insert of your entire history.

```
composite_hash = sha256(
    raw_Buchung + "|" + raw_Verwendungszweck + "|" + raw_Betrag
).hexdigest()
```

- `raw_*` means the **exact cell string as it appears in the CSV**, after the CSV reader strips enclosing quotes and nothing else. No trimming, no case folding, no whitespace collapsing, no date reformatting, no decimal normalization. Hash before any conversion, not after.
- Encode as UTF-8 before hashing, regardless of the file's source encoding, so a Latin-1 and a UTF-8 export of the same rows hash identically.
- Separator is the single pipe character `|`. Fixed forever.
- The hash inputs are deliberately not the same as the derived fields. `description` and `amount` may be reformatted freely; the hash will not move.

Tradeoff: two transactions with the same booking date, same purpose text, and same amount collide, and the second is skipped as a duplicate. This is accepted. The import summary reports it as "X potential duplicates skipped" and lists the skipped rows so a real collision is visible rather than silent.

### PayPal

Comma-separated, UTF-8. Preclean still runs (BOM, header location). Key columns:

```
"Date","Time","TimeZone","Name","Type","Status","Currency","Gross","Fee","Net","From Email Address","To Email Address","Transaction ID",...
```

**Column types and mapping.** Same rule: read as string, convert explicitly.

| CSV column | Raw form | Parsed as | Target |
|------------|----------|-----------|--------|
| `Date` | `DD/MM/YYYY` or `MM/DD/YYYY` | `date` | `transactions.date` |
| `Time`, `TimeZone` | text | — | ignored |
| `Name` | text | `str` | `description` / `original_description` |
| `Type` | text | `str` | `transaction_type` |
| `Status` | text | `str` | filter only — keep `Completed` |
| `Currency` | `EUR` | `str` | `currency` |
| `Gross` | `-12.50` | `Decimal` | `amount` |
| `From Email Address` / `To Email Address` | text | `str` | `counter_account` |
| `Transaction ID` | text | `str` | `transaction_id` |

- `Gross` is already signed and uses `.` as decimal separator. Convert the string directly with `Decimal`.
- Date order is detected from context (any day value > 12 in the file settles it).
- Rows not `Status == "Completed"` are dropped before upsert and counted in the summary.

## Upsert logic

### PayPal

Upsert on `transaction_id`:
1. If exists: update amount, description, and metadata. Preserve `category_id`, `subcategory_id`, and `user_categorized` when `user_categorized == True`. Never modify `exclude_from_stats`.
2. If not exists: insert, run categorization rules.

**Upsert never touches `transaction_tags` — not on insert, not on update, under any condition.** Tags are applied independently of categorization, so a tagged-but-uncategorized row has `user_categorized == False` and would otherwise lose its tags on the next import. Tags are user data and only the tag endpoints write to that table.

### ING

Upsert on `composite_hash`:
1. If hash exists: skip entirely (preserve all user edits).
2. If hash is new: insert, run categorization rules.
3. Never delete existing rows on reimport — only add new ones.

## Categorization rules

Rules are keyword-based, case-insensitive substring matches. Each rule declares which field it matches against via `field`: `description`, `counter_account`, or `transaction_type`. This exists because plenty of real rules are not description rules — a landlord is best matched on `counter_account`, and "every `Gehalt/Rente` row is Income" is a `transaction_type` rule.

Matching order: `ORDER BY priority DESC, id ASC`. The `id` tiebreak is required so that two rules with equal priority always resolve the same way. First match wins.

When a user manually recategorizes a transaction in the UI:
1. Set `user_categorized = True` on the transaction.
2. Optionally prompt: "Apply this as a rule for all future [keyword] transactions?" — the prompt lets the user pick which field the rule should match on, defaulting to `description`.
3. If yes, create a new rule. Do NOT retroactively recategorize existing transactions unless the user explicitly asks.

Auto-categorization only runs on newly imported transactions where `user_categorized == False`.

## Deleting a category

`DELETE /api/v1/categories/{id}` sets `category_id = NULL`, `subcategory_id = NULL`, **and `user_categorized = False`** on every affected transaction.

Resetting the flag is not optional. Auto-categorization skips rows where `user_categorized == True`, so an orphaned row that keeps its flag can never be picked up by any rule again — it sits in Uncategorized permanently and invisibly. Clearing the flag returns it to the rule engine's reach.

Subcategory deletion follows the same shape: `subcategory_id = NULL` on affected transactions, and `user_categorized = False` only if the transaction has no `category_id` left either.

## API conventions

- All endpoints under `/api/v1/`
- JSON request/response bodies
- Filtering via query parameters: `?category_id=3&tag_id=5&date_from=2024-01-01&date_to=2024-12-31&search=rewe`
- Pagination: `?page=1&page_size=50`
- Standard error shape: `{ "detail": "message" }`
- Amounts are strings in JSON, both directions. `min_amount` / `max_amount` query params parse as `Decimal`.
- CSV export returns `Content-Type: text/csv` with `Content-Disposition: attachment`

## Key endpoints

```
POST   /api/v1/import/csv              Upload + upsert CSV
GET    /api/v1/transactions             List (filtered, paginated, sorted)
PATCH  /api/v1/transactions/{id}        Update category, subcategory, exclude_from_stats
POST   /api/v1/transactions/{id}/tags   Add tag
DELETE /api/v1/transactions/{id}/tags/{tag_id}  Remove tag
PATCH  /api/v1/transactions/bulk        Bulk recategorize / bulk set exclude_from_stats

GET    /api/v1/categories               List with subcategories
POST   /api/v1/categories               Create category
POST   /api/v1/categories/{id}/subcategories  Create subcategory
PATCH  /api/v1/categories/{id}          Rename / recolor
DELETE /api/v1/categories/{id}          Delete (nullifies + clears user_categorized)

GET    /api/v1/tags                     List all
POST   /api/v1/tags                     Create tag
DELETE /api/v1/tags/{id}                Delete (removes from transactions)

GET    /api/v1/rules                    List rules
POST   /api/v1/rules                    Create rule
PATCH  /api/v1/rules/{id}               Update keyword, field, category, subcategory, priority
DELETE /api/v1/rules/{id}               Delete rule
POST   /api/v1/rules/apply              Re-run rules on uncategorized txns

GET    /api/v1/export/csv               Export filtered data
GET    /api/v1/stats/summary            Aggregated spending data for charts
```

`/stats/summary` filters `exclude_from_stats == False` on every aggregate it computes. No exceptions, no query parameter to override it.

## Frontend conventions

- Tailwind CSS for styling. Dark theme.
- All API calls go through wrapper functions in `src/api/`.
- Use React Query (TanStack Query) for server state.
- Recharts for visualizations.
- No browser-side storage — all state lives in the backend.
- Amounts arrive as strings. Format for display; never do arithmetic on them client-side.

## Development

```bash
# Backend
cd backend
uv sync
uv run alembic upgrade head          # also runs automatically on startup
uv run uvicorn main:app --reload --port 8000

# Tests
uv run pytest

# Regenerate derived fixtures after editing a demo CSV
uv run python tests/make_fixtures.py

# Frontend
cd frontend
npm install
npm run dev   # defaults to port 5173, proxied to backend
```

## Code style

- Python: type hints on all function signatures. Pydantic for validation. No bare `except`. Docstrings on service functions.
- JS/JSX: functional components only. Named exports for pages, default export for App. Destructure props.
- SQL: never use raw SQL strings in application code — always go through SQLAlchemy ORM.
- Money: `Decimal` only. A `float` anywhere near an amount is a bug.

## What not to do

- Don't add authentication. This is a single-user local app.
- Don't use `create_all()` — Alembic owns the schema.
- Don't edit an already-applied migration. Write a new one.
- Don't skip the startup backup.
- Don't change the composite hash definition.
- Don't call external APIs. All data comes from CSV files.
- Don't delete transactions on reimport. Only insert new ones.
- Don't auto-recategorize transactions where `user_categorized == True`.
- Don't let the importer write to `transaction_tags` or to `exclude_from_stats`.
- Don't commit real bank exports. Fixtures are synthetic.
- don't use pip or python -m venv directly — uv owns the environment and the lockfile
