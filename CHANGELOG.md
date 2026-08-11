# Changelog

What changed, newest first. Every change gets an entry — see "Changelog" in [CLAUDE.md](CLAUDE.md).

---

## Unreleased

### Added

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
  (end of 10.08.2026 = 1.608,90 €, in `backend/balance.py`) and carried forward
  by every movement since. Add an anchor each time you reconcile against the
  bank: the endpoint then compares the balance the ledger predicts against the
  one observed, and any drift is flagged on the card as incomplete data. Also
  reports the implied opening balance — 3.593,40 € before 01.04.2026 on the
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
