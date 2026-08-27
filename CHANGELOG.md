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

- I want to Store the Händler info but want the ability of a calculated name Field, which is the same as the regular Unless I add mappings to this
- Allow for renaming of subcategories
- Add analytics top page
- Add page to analytics tab overview page of money by cataegory, not graphics. add an expand option where its then money by subcategoryand on further expansion the drill down. There should be a page filter for time range
  - this should additionaly allow for a specific category or subcategory to be viewed on a monthly basis with a trend
- Add Page to analytics tab where one can analyze money per tags. Also add time range filter
- SOme expenses such as rent are offset by income in rent. In the overview subtract this overlap from income and expenses
  - basically it should only be my salary which is income and maybe sparen. this is a logical crux nothing that is harcoded. Basically offset income and expenses in the same category

---

## Unreleased

### Added

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
