# Changelog

What changed, newest first. Every change gets an entry — see "Changelog" in [CLAUDE.md](CLAUDE.md).

---

## Open

Ideas, todos and observations that are **not implemented yet** — the inbox for
anything noticed away from the keyboard. Add a bullet and stop there: no
"why", no polish, no structure required. A half-sentence that only makes sense
to you is worth more here than a note you didn't bother to write. Date it if
the timing matters.

When an item lands, move it into `Unreleased` and write it up properly there —
move, don't delete, so the trail from idea to change stays intact.

- I want the Merchant field to also be controlled by rules which I can set. And i want to be able to have this field map to certain Categories as well. So i want to be able to have the mapping of paypal@ikea to IKEA -> wohnen. So setting Vendor to ikea also sets to wohnen if that one has not been manually overridden beforehand
These rules should be editable as well 
---

## Unreleased

### Added

- **Star schema views for Power BI** — seven SQL views (migration `0004`) that
  present the data as a classic star schema: `FactTransaction` at the center,
  `DimCategory`, `DimSubcategory`, `DimDate`, `DimVendor`, `DimTag` around it,
  and `BridgeTransactionTag` for the many-to-many tag relationship. PascalCase
  column names throughout. From `Open`: "Add a relational View SQL Model in the
  db. I want this as a Star Schema with DimSubcategory, DimCategory, DimDate,
  DimVendor, DimTag. I want to use this model in Power Bi."

  These are read-only views over the existing tables — the application does not
  use them. They exist so Power BI (or any ODBC tool) can connect to
  `data/finance.db` and find a clean relational model. `FactTransaction.Amount`
  is in euros (the stored integer cents ÷ 100), and `IsInternalTransfer` is a
  computed flag mirroring `services/internal_transfers.py` so Power BI can
  filter them the same way the app does. `DimDate` uses German month/day names.
  `DimVendor` resolves display names through `merchant_mappings`.

  Model documentation with a diagram and Power BI setup instructions is in
  `docs/star_schema.md`. CLAUDE.md carries a summary table and a pointer to the
  full doc.

- **Merchant name mappings** — a `merchant_mappings` table that overrides the
  display name for a `counter_account` value. The raw name stays on the
  transaction row; the mapping is resolved at query time via COALESCE, so
  adding or changing one takes effect immediately with no backfill. The Top 10
  Händler chart on the Übersicht shows the mapped name, and each merchant has a
  pencil button to set a display name inline. From `Open`: "I want to Store
  the Händler info but want the ability of a calculated name Field, which is
  the same as the regular Unless I add mappings to this."

  New table `merchant_mappings` (migration `0003`), new endpoints under
  `/api/v1/merchants/`, new `display_name` field on the `MerchantSpendEntry`
  schema.

- **Per-category-net income and expenses on the Übersicht** — the Einnahmen and
  Ausgaben cards now net income against expenses within each category before
  computing the headline totals. Rent that is partly reimbursed subtracts the
  reimbursement from expenses rather than adding it to income, so income shows
  only categories that net positive (salary, savings returns) and expenses
  shows actual cost after reimbursements. The overall Saldo is unchanged — it
  is mathematically the same sum either way. From `Open`: "SOme expenses such
  as rent are offset by income in rent. In the overview subtract this overlap
  from income and expenses … Basically offset income and expenses in the same
  category."

  The computation uses a subquery that groups by `category_id`, sums each
  category's transactions, then splits the positive-net and negative-net
  buckets into the two headline figures. No schema change; no new endpoint —
  only the SQL behind `total_income`/`total_expenses` in `/stats/summary`
  changed.

- **Auswertungen tab** (`/auswertungen`) — a top-level tab with two sub-tabs,
  Kategorien and Tags, both over one shared date range. From `Open`: "Add
  analytics top page / Tab with subtabs outlined in the next points", "Add page
  to analytics tab overview page of money by cataegory, not graphics … expand
  option … further expansion the drill down … page filter for time range … a
  specific category or subcategory … on a monthly basis with a trend", and "Add
  Page to analytics tab where one can analyze money per tags. Also add time
  range filter".

  New endpoints: `GET /stats/by-category`, `GET /stats/by-tag`,
  `GET /stats/trend`. All three go through `_countable`, so they count exactly
  the rows the Übersicht and the anchored balance do — an analytics page
  reporting a different ledger than the rest of the app would be worse than no
  page.

  *Figures, not charts.* The Übersicht already draws the pie; the ask here was
  the table behind it. Every row carries income, expenses **and** net rather
  than one figure: `/stats/summary`'s `by_category` is shaped for a pie chart,
  which cannot mix slice signs, so it nets income against spending and then
  drops anything at or above zero — a fully reimbursed category vanishes and
  unfiled income is left out entirely. That is right for a chart and wrong for
  a table, so this one keeps every row and splits the two halves out. A
  category whose spending is largely paid back reads nothing like one with no
  income at all, and a single net figure hides which is which.

  *Three levels, one table.* Category → subcategory → the transactions
  themselves, each expanded in place rather than by replacing the page: the
  point of drilling down is comparing a part against the whole it came from,
  and a drill-down that navigates away takes that away. The subcategory rows
  sum exactly to their parent (they come from a second `GROUP BY` over the same
  filtered set, not from summing in Python), and the category rows sum to the
  `Gesamt` row.

  *A row addresses itself with transaction-list filter names.* Each row builds
  one `params` object — `category_id`, `subcategory_id`, `uncategorized`,
  `no_subcategory`, `tag_id`, `untagged` — and hands the same object to
  `/stats/trend`, to `/transactions` for the drill-down, and to the link into
  the Transaktionen page. One spelling for all three, so "this row's history",
  "this row's transactions" and "open this row over there" cannot end up
  describing different rows.

  *Tag rows overlap, and say so.* A transaction carrying two tags counts in
  full under both, so unlike the category table the rows do not add up to the
  range's totals. `totals` on `/stats/by-tag` is every countable row — a
  reference point, not a sum of the entries — the tag table has no `Gesamt`
  row, and the page states the overlap above the table. A table of figures that
  does not add up has to say why on its face. The untagged rows ride along as
  their own entry (`tag_id: null`), since otherwise the part of the ledger tags
  say nothing about would be invisible on the page.

  *The monthly trend is colorless on purpose.* Every other trend arrow in the
  app is green or red, but that mapping assumes you know whether more is
  better — true for a salary, false for groceries — and this panel points at
  whichever row was clicked. It states direction and percent and leaves the
  reading to whoever picked the row. The percent compares magnitudes, since for
  a spending row both months are negative and "moved toward zero" is not what
  anyone means by a smaller month.

  Supporting changes:

  - `GET /transactions` and `GET /export/csv` gained `no_subcategory`
    (`true` = rows with no subcategory, `false` = rows with one, unset = no
    filter) — the subcategory-side counterpart to `uncategorized`. Without it
    the "Ohne Unterkategorie" bucket was the one row in the table whose
    transactions could not be listed: there is no id that means "no
    subcategory".
  - The Transaktionen page now reads `subcategory_id` and `no_subcategory` off
    the URL. Both were being silently dropped, which would have made the
    drill-down links land on an unfiltered list.
  - The drill-down and its links pass `excluded=false`. The transaction list
    keeps `exclude_from_stats` rows (the flag only hides them from aggregates)
    while every figure on this page drops them, so without it a row's
    transactions would not be the transactions its total was computed from.
  - `fillMonthGaps` in `lib/dateRanges.js` inserts the empty months the backend
    omits, between the first and last month present only. A chart that draws
    January next to March hides the stretch where nothing happened, which is
    exactly what a trend is for; padding out to the edges of the range would
    invent months instead.

- **Renaming a subcategory** — `PATCH /api/v1/subcategories/{id}`, wired to a
  pencil button next to each subcategory in the Kategorien list, matching the
  inline rename a category already had. From `Open`: "Allow for renaming of
  subcategories".

  A subcategory was the one named thing in the app that could only be deleted
  and recreated. That is not a rename: the new row gets a new id, so every
  transaction and every rule pointing at the old one is nulled out by the
  delete (and a transaction that had no `category_id` left also loses
  `user_categorized`, per "Deleting a category"). Re-typing the name was
  therefore a destructive operation for a cosmetic change.

  Renaming touches nothing else on purpose. Assignments are keyed by id, and
  CLAUDE.md's seed-data rule already forbids looking a category or subcategory
  up by name anywhere in the codebase, so there is no lookup that a rename can
  break — no migration, no backfill, no cascade. The uniqueness rule is
  unchanged: names are unique *within* a category, so renaming onto a sibling's
  name is a 400 while reusing a name that exists under a different category is
  fine.

  The endpoint takes `name` only. Re-filing a subcategory under a different
  category would move every transaction carrying it across a category boundary
  without touching `category_id` on those rows, which is a different feature
  with its own consistency question, and it was not asked for.

  Frontend: the rename invalidates `['categories']` and also `['rules']` —
  `/rules` serves `subcategory_name` next to the id, so the rules list would
  otherwise keep showing the old name until a reload.

- **SQL page** (`/sql`) — a read-only SQL editor over the local database, with
  the result set in a plain table, saved queries in named folders, and several
  query tabs open at once. From `Open`: "Add a SQL Tab … folder of stored
  queries … multiple active query windows".

  *Read-only, three ways.* The statement is parsed before it runs (one
  statement, must open with `SELECT` / `WITH` / `VALUES` / `EXPLAIN`, scanned
  for write keywords anywhere in the text — that last part is what catches
  `WITH x AS (…) DELETE FROM …`); it then runs on a second engine opened
  `mode=ro`, so SQLite refuses the write even if the parse were fooled; and it
  runs under a 5 s deadline on SQLite's progress handler, so a cross join
  cannot wedge the server. The keyword scan looks at a copy with string
  literals and comments blanked out — a `Verwendungszweck` reading "DROP
  TABLE" has to stay searchable. `ATTACH` is blocked by name because it takes a
  plain path and a plain path opens read-write even from a read-only
  connection.

  *Amounts come back as stored — integer cents, not euros.* An arbitrary query
  can compute anything, and dividing every integer that lands in a column
  called `amount` by 100 would corrupt the ones that aren't money. The schema
  panel labels the column and the starter query divides explicitly instead.
  This is the one place in the app where an amount is not a `Decimal`; it is a
  raw cell on its way to the screen, never arithmetic anything depends on.

  *Folders are not a table.* A folder is whatever distinct `folder` value the
  saved queries carry — it exists while something is in it, and renaming one is
  an UPDATE across the rows sharing the name. Renaming onto an existing folder
  merges them, which is the only sane reading when a folder is just a label.
  `folder` is `""` for the top level rather than NULL, because SQLite counts
  every NULL as distinct in a unique index and two unfiled queries could
  otherwise share a name.

  *Tabs are in-memory.* They do not survive a reload, which is the intended
  split between scratch work and the saved list — and the alternative would
  need browser storage, which CLAUDE.md rules out.

  **Spec change:** "SQL: never use raw SQL strings in application code" now
  carries an explicit exception for this console, made in CLAUDE.md in this
  commit rather than left implied. The rule is about app logic; here the SQL is
  the user's input. Nothing else may cite it as precedent — hence the fence in
  `services/sql_console.py` and the entry under "What not to do".

  New table `saved_queries` (migration `0002`), new endpoints under
  `/api/v1/sql/`, new page in the sidebar.
- **Internal transfers are filtered out** of the list, the export and all statistics.
  A PayPal purchase lands three times — the purchase, the `Bankgutschrift auf
  PayPal-Konto` that funds it, and the ING debit to `PayPal Europe` that funds
  that. Both funding legs are now dropped, keeping the one copy that names the
  real merchant. New `internal` filter (`hide` | `show` | `only`, default `hide`);
  `only` is the audit view. Definition: `services/internal_transfers.py`.
- **Date-range presets on Übersicht** — Gesamt / Dieser Monat / Letzter Monat /
  Letzte 3 Monate / Dieses Jahr / Letztes Jahr / Benutzerdefiniert, as a segmented
  control with the active one highlighted. Applies to all three charts including
  Top 10 Händler. The active preset is derived from the range rather than stored,
  so the highlight can never disagree with the range in effect.
- **Search and filters for the rules list** on Kategorien — free text over
  keyword and category name, plus match-field and category dropdowns, with a
  "x von y" count. Filtered in the browser: `GET /rules` returns the full
  ordered set anyway, since the categorizer's precedence only means anything
  as a complete list.
- **Kontostand card on Übersicht**, with `GET /api/v1/stats/balance`. A CSV
  records movements, not a balance, so it is anchored to a hand-verified figure
  (end of 11.08.2026 = 1.652,09 €, in `backend/balance.py`) and carried forward
  by every movement since. Add an anchor each time you reconcile against the
  bank: the endpoint then compares the balance the ledger predicts against the
  one observed, and any drift is flagged on the card as incomplete data. Also
  reports the implied opening balance — 3.719,00 € before 01.04.2026 on the
  current data.
- **Übersicht dashboard** (PLAN 4.1) — summary cards with a month-over-month
  trend, expenses by category (pie, click a slice to filter the list), income vs.
  expenses per month, top 10 merchants, and a date range for the charts.
- **Kategorien page** (PLAN 4.2) — categories with colors and nested
  subcategories, transaction counts, full CRUD, plus a rules section and
  "Regeln erneut anwenden".
- **Tags page** (PLAN 4.3) — list with usage counts, create / rename / delete,
  click a tag to filter the transaction list.
- **Export panel** (PLAN 3.5) — the transaction filters, a preview of the row
  count and date range, and a CSV download.
- **"Ohne Kategorie" filter** on Transaktionen, as a third state of the category
  dropdown.
- **`PATCH /api/v1/tags/{id}`** — rename and recolor a tag.
- **README:** how to start the app after a reboot.

### Changed

- **`Open` section added at the top of this file.** CLAUDE.md had described it
  since the changelog rules were written, but it never existed here, so notes
  taken away from a Claude session had nowhere to go and were lost. It is
  explicitly exempt from the "write down the why" rule — an idea inbox that
  demands a paragraph per entry is an inbox nobody uses. CLAUDE.md now also
  bars rewriting or pruning those bullets: they are the user's notes, not
  changelog copy.
- **CLAUDE.md now names bash as the shell** ("Development → Shells"). PowerShell
  hangs on this machine, so it is off the table entirely: commands that really
  need it get written out and handed to the user to run instead of being
  attempted. Also records the read-only `sqlite3` route for inspecting
  `data/finance.db` without starting the server — mirroring `_countable` and
  `is_internal_transfer()` so a scratch query agrees with the endpoints. That is
  analysis, not application code, so it does not conflict with the "no raw SQL"
  rule under "Code style"; the exception is stated there rather than left
  implied.
- **The balance anchor was withdrawn and replaced** — end of 10.08.2026 =
  1.608,90 € is gone; the only anchor is now end of 11.08.2026 = 1.652,09 €.
  The old figure was never a real end-of-day observation: it had expenses
  netted out of it before it was written down, so every drift measured against
  it would have reported a discrepancy in the imported data that does not
  exist. This is not the "append, never edit" rule in CLAUDE.md being broken —
  that rule bars adjusting a *good* observation to make a drift disappear.
  Retracting one that was never an observation is the opposite move, and the
  retraction is recorded in `backend/balance.py` rather than quietly dropped.
  With a single anchor there is no consecutive pair, so no drift is reported
  until the next reconciliation is appended. The implied opening balance moves
  with it: 3.719,00 € before 01.04.2026, not 3.593,40 € — the anchor is 43,19 €
  higher and now sits a day later, so the 82,41 € booked on 11.08 is inside it.
- **The Einnahmen / Ausgaben / Saldo cards now report the last complete month**,
  not the current one, which is always missing most of its spending and made the
  trend read as a collapse. Each card names its month (`AUSGABEN · 07.2026`) and
  the trend names its comparison (`ggü. 06.2026`), so the figures cannot be
  mistaken for current-month ones. The Kontostand card is unaffected — it is not
  a month figure. Trend percentages now use the German decimal comma.
- **"Ausgaben nach Kategorie" is now net of income in the same category** —
  rent that is partly reimbursed reports what it actually cost (on the current
  data: Wohnen −7.546,88 gross, +3.370,87 repaid, **−4.176,01 net**). Categories
  netting to zero or above get no slice. The uncategorized bucket is the
  exception and stays gross: its income is an uncategorized salary, unrelated to
  its spending, and netting it would have cancelled the two off and hidden
  −12.095,20 € of unfiled spending from the chart entirely. `total_expenses`
  stays gross, so it and the pie deliberately no longer reconcile.
- **The pie's uncategorized slice is labelled "Ohne Kategorie"**, not "Nicht
  kategorisiert" — that is the name of a real seeded category which appears in
  the same legend. Matches the transaction filter's wording.
- **Monthly chart: income and expenses side by side** instead of stacked around a
  zero baseline. Expenses plot as magnitude so both bars share a baseline and
  their heights compare directly; the tooltip keeps the real sign.

### Fixed

- **`.gitignore` was swallowing `frontend/src/lib/`.** A bare `lib/` line from the
  Python template matched the frontend source directory, so `format.js` had never
  been tracked by git. Scoped to `backend/lib/`.

### Known issues

- **The internal-transfer filter needs both CSVs to cover the same period.** An
  ING→PayPal debit whose PayPal counterpart was never imported gets hidden with
  nothing accounting for the money. Currently fine — 67 debits (−2.158,69 €)
  balance 67 funding legs (+2.158,69 €) exactly — but importing one source
  further than the other reopens it. `internal=only` is the check.
- **PayPal authorization holds are not filtered.** `Einbehaltung für offene
  Autorisierung` and its `Rückbuchung` net to zero but are not funding legs, so
  they still reach the totals.
- **Frontend dependencies live in the repo root**, not in `frontend/`.
  `frontend/package.json` declares none, and the root `node_modules/` is not
  gitignored. It resolves today, but `npm install` inside `frontend/` installs
  nothing.
