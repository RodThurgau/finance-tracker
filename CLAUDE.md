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
│   ├── seed.py                  # Default categories/tags for an empty database
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
│   │   │   ├── ing_demo.csv     # ← drop the hand-written demo file here (Latin-1, as ING ships it)
│   │   │   ├── paypal_demo.CSV  # ← drop the hand-written demo file here (UTF-8 + BOM, German export)
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
| counter_account  | TEXT    | Nullable. ING `Auftraggeber/Empfänger` / PayPal `Absender E-Mail-Adresse` |
| transaction_type | TEXT    | ING `Buchungstext` (e.g. "Lastschrift", "Kartenzahlung") / PayPal `Beschreibung` (e.g. "Handyzahlung") |
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

- On startup: take a backup (below), then run `alembic upgrade head` programmatically, then seed (below). A fresh database gets built from migration `0001` like any other.
- The programmatic run sets `config.attributes["configure_logger"] = False`, and `env.py` honors it. Otherwise Alembic's `fileConfig()` would reset the root logger to WARNING and disable every logger the app had already created. The Alembic CLI still configures logging normally.
- Every model change ships with a migration in the same commit. Autogenerate is a starting point, not the answer — review the generated file, especially for SQLite's limited `ALTER TABLE` (Alembic's batch mode is required for column drops, type changes, and constraint changes).
- Never edit a migration that has already been applied to `data/finance.db`. Write a new one.

## Backups

The CSVs are re-downloadable; months of manual categorization are not.

- `backup.py` runs in the FastAPI lifespan handler **before** Alembic, on every startup.
- It copies `data/finance.db` to `backups/finance-YYYYMMDD-HHMMSS.db` using SQLite's backup API (or `VACUUM INTO`) so the snapshot is consistent even if a connection is open.
- Retention: keep the most recent 20 snapshots plus the first snapshot of each day for the last 30 days. Prune the rest.
- Startup aborts loudly if the backup fails. Do not migrate an unbacked database.
- Restore is a documented manual step in README: stop the server, copy a snapshot over `data/finance.db`, restart.

## Seed data

`seed.py` runs in the lifespan handler after migrations and writes the default German categories, subcategories, and tags — but only when the database holds no categories and no tags. On every later startup it is a no-op.

The check is deliberately coarse: deleting every category and tag is the documented way to reset the defaults, and they come back on the next start. The seeded rows are an opening position, not fixtures the app depends on — they are renameable and deletable like any other, so **nothing in the codebase may look a category or tag up by name or id.**

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

**German-locale export only.** The account language decides the column names, and this app targets the German export — the one in `tests/fixtures/paypal_demo.CSV`. An English export has different column names and will fail detection rather than mis-import. If the account language ever changes, that is a spec change here, not a parser guess.

Comma-separated, UTF-8 **with BOM**, every field quoted, header on line 1 (no preamble). Preclean still runs — it strips the BOM and locates the header. Columns, in export order:

```
"Datum","Uhrzeit","Zeitzone","Beschreibung","Währung","Brutto","Entgelt","Netto","Guthaben","Transaktionscode","Absender E-Mail-Adresse","Name","Name der Bank","Bankkonto","Versand- und Bearbeitungsgebühr","Umsatzsteuer","Rechnungsnummer","Zugehöriger Transaktionscode"
```

**Column types and mapping.** Same rule: read as string, convert explicitly.

| CSV column | Raw form | Parsed as | Target |
|------------|----------|-----------|--------|
| `Datum` | `DD.MM.YYYY` | `date` | `transactions.date` |
| `Uhrzeit`, `Zeitzone` | text | — | ignored |
| `Beschreibung` | text | `str` | `transaction_type` (e.g. "Handyzahlung", "PayPal Express-Zahlung") |
| `Name` | text | `str` | `description` / `original_description` |
| `Währung` | `EUR` | `str` | `currency` |
| `Brutto` | `-9,90` | `Decimal` | `amount` |
| `Entgelt`, `Netto`, `Guthaben` | `-9,90` | — | ignored — `Guthaben` is a running balance, not a transaction |
| `Absender E-Mail-Adresse` | text | `str` | `counter_account` |
| `Transaktionscode` | text | `str` | `transaction_id` |
| `Name der Bank`, `Bankkonto`, `Versand- und Bearbeitungsgebühr`, `Umsatzsteuer`, `Rechnungsnummer`, `Zugehöriger Transaktionscode` | text | — | ignored |

- `Brutto` is already signed and uses German notation — `.` thousands, `,` decimal, same as ING's `Betrag`. Normalize the **string** the same way and pass it to `Decimal`. Never `float`.
- `Datum` is `DD.MM.YYYY` and unambiguous. There is no date-order detection — parse it strictly and report a row-level error if it fails.
- **There is no `Status` column.** Everything in the export is already booked, so there is no status filter and no dropped-row count for it.
- `Name` is empty on PayPal's own bookkeeping rows (bank credits, authorization holds). Those rows still import; `description` falls back to `Beschreibung` when `Name` is blank.
- Every card/express purchase is normally followed by a `Bankgutschrift auf PayPal-Konto` row of the opposite sign that funds it, linked by `Zugehöriger Transaktionscode`. **The importer still does not touch these** — no netting, no auto-exclusion, nothing written to the row. They import as ordinary rows and are filtered at *query* time instead; see "Internal transfers".

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

## Internal transfers

A single PayPal purchase reaches the database three times:

| Source | Row | Amount |
|--------|-----|--------|
| PayPal | the purchase itself, e.g. `Intelligent Apps GmbH` | −37,50 |
| PayPal | `Bankgutschrift auf PayPal-Konto`, which funds it | +37,50 |
| ING | `PayPal Europe S.a.r.l. et Cie S.C.A`, which funds *that* | −37,50 |

Only the first is a real expense. The other two — the **internal transfers** — are money moving between the user's own accounts to settle it. Both are dropped from the transaction list, the export, and every aggregate, leaving exactly one copy of the amount: the PayPal row, which names the real merchant where the ING row only ever says "PayPal Europe".

**The two legs are dropped together or not at all.** Dropping one leaves the totals wrong in the other direction. That is why there is a single definition in `services/internal_transfers.py` — `is_internal_transfer()`, a SQL predicate — rather than a filter re-spelled at each call site.

The definition:

- ING rows whose `counter_account` contains `paypal`, case-insensitive. A substring rather than the full legal name, because ING's spelling of `S.C.A.` varies between exports.
- PayPal rows whose `transaction_type` is `Bankgutschrift auf PayPal-Konto`, case-insensitive. Stable, since the German-locale export is the only one supported.

**This is derived, never stored.** Nothing is written to the row, so re-tuning the match takes effect immediately with no migration and no rows left carrying a stale flag. It is deliberately *not* `exclude_from_stats`, which is user-owned, importer-untouchable, and by design does not affect the transaction list.

Where it applies:

- `GET /transactions` and `GET /export/csv`: hidden by default. `?internal=show` includes them, `?internal=only` shows nothing else. This is the one filter that is **not** neutral when unset.
- `/stats/summary`: dropped unconditionally, like `exclude_from_stats`. No override parameter.

`internal=only` is not a convenience — it is the audit view. Without it a mis-tuned match would hide rows with no way to discover what went missing.

**The known gap:** an ING→PayPal debit whose PayPal counterpart was never imported is hidden while nothing else accounts for it, so that money silently leaves the totals. This bites whenever the two CSVs cover different date ranges — import both sources over the same period. `internal=only` is how you check.

Not covered: PayPal authorization holds (`Einbehaltung für offene Autorisierung` and its `Rückbuchung allgemeiner Einbehaltung`) also net to zero, but are not funding legs and are not filtered.

## Account balance

A CSV export records movements, never a balance — nothing in the data says how much is actually in the account. So the balance is **anchored**: real figures read off the bank at the end of a named day, listed in `backend/balance.py`.

```
current balance = latest anchor + sum(transactions after that anchor's date)
```

An anchor is an **end-of-day** figure: rows dated on the anchor day are already inside it and are never added again.

**Anchors are the consistency check.** Add one each time the balance is reconciled against the bank. `/stats/balance` then reports, for every consecutive pair, the balance the ledger *predicts* against the one actually observed. A non-zero `drift` means the imported data between those dates is incomplete or double-counted, and the Übersicht surfaces it on the Kontostand card instead of showing a number that quietly lies. `implied_opening_balance` is the same idea pointed backwards: what the account must have held before the earliest recorded movement.

Append anchors, never edit a past one — an anchor adjusted to make a drift disappear destroys the only evidence that something was wrong.

The balance sums exactly the rows `/stats/summary` aggregates (`_countable` in `routers/stats.py`): no `exclude_from_stats` rows, no internal transfers. Dropping the funding legs is safe because a PayPal purchase and the ING debit settling it are the same money — and if that pairing ever breaks, the next anchor's drift is what surfaces it.

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
- `tag_id` is repeatable and ORs: `?tag_id=1&tag_id=2` returns rows carrying *either* tag. A single `tag_id` behaves as it always did.
- `untagged` is the tag-side counterpart to `uncategorized`: `true` returns rows with no tags at all, `false` returns rows carrying at least one, unset does not filter. Passing it together with `tag_id` is contradictory and correctly returns nothing.
- `internal` (`hide` | `show` | `only`, default `hide`) is the one filter that does **not** default to neutral — internal transfers are hidden unless asked for. See "Internal transfers".
- Pagination: `?page=1&page_size=50`
- Standard error shape: `{ "detail": "message" }`
- Amounts are strings in JSON, both directions. `min_amount` / `max_amount` query params parse as `Decimal`.
- CSV export returns `Content-Type: text/csv` with `Content-Disposition: attachment`

## Key endpoints

```
POST   /api/v1/import/preview          Preclean + detect + parse only — no DB write; source, discarded preamble, first 5 rows, row errors
POST   /api/v1/import/csv              Upload + upsert CSV
GET    /api/v1/transactions             List (filtered, paginated, sorted). Hides internal transfers unless `internal=show|only`
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
PATCH  /api/v1/tags/{id}                Rename / recolor (assignments are keyed by id and survive both)
DELETE /api/v1/tags/{id}                Delete (removes from transactions)

GET    /api/v1/rules                    List rules
POST   /api/v1/rules                    Create rule. Optional `apply_to_existing: bool` (default false) backfills existing rows this rule matches, scoped to `category_id IS NULL` only — never a row that already carries a category, auto-assigned or not. Response adds `applied_count`.
PATCH  /api/v1/rules/{id}               Update keyword, field, category, subcategory, priority
DELETE /api/v1/rules/{id}               Delete rule
POST   /api/v1/rules/apply              Re-run rules on uncategorized txns

GET    /api/v1/export/csv               Export filtered data. Same `internal` default as the list
GET    /api/v1/stats/summary            Aggregated spending data for charts
GET    /api/v1/stats/balance            Anchored running balance + per-anchor drift check
```

`/stats/summary` filters `exclude_from_stats == False` and drops internal transfers on every aggregate it computes. No exceptions, no query parameter to override either.

## Frontend conventions

- Tailwind CSS for styling. Dark theme.
- All API calls go through wrapper functions in `src/api/`.
- Use React Query (TanStack Query) for server state.
- Recharts for visualizations.
- No browser-side storage — all state lives in the backend.
- Amounts arrive as strings. Format for display; never do arithmetic on them client-side.
- **UI language: German.** All labels, navigation, buttons, form fields, toasts, empty states, and confirmation copy are in German. Dates display as `YYYY.MM.DD` (sorts correctly as plain text; use `Intl.DateTimeFormat('sv-SE')` or a manual `date.toISOString().slice(0, 10).replaceAll('-', '.')`-style formatter — not `de-DE`, which gives `DD.MM.YYYY`); amounts via `Intl.NumberFormat('de-DE')` (already required above). Default seed categories/tags are German (see 1.4 in PLAN.md) — component copy should match that register. Code itself (variable names, comments, commit messages) stays English; this applies to user-facing strings only.

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

## Changelog

`CHANGELOG.md` is the running record of what changed and what is still open. Keep it current — it ships in the same commit as the change it describes, not afterwards.

- **Every change gets an entry.** Behavior, endpoints, schema, UI, build/tooling config. A change that is invisible in the changelog is a change nobody can find later.
- **Newest first.** `Open` holds observations and todos that are not implemented yet; `Unreleased` holds finished work not yet cut into a release. Move an item from `Open` to `Unreleased` when it lands — don't delete it.
- **Write down the "why", not just the "what".** The reason for a change is the part that isn't recoverable from the diff.
- **Record the decisions an entry depends on**, including the ones still open, and name any rule in this file that the change contradicts — a spec change gets made here in the same commit, never left implied.
- Entries are English, like the rest of the docs and the code. Only user-facing UI strings are German.

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
- Don't land a change without a `CHANGELOG.md` entry in the same commit.
