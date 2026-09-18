import { api } from './client.js';

/** GET /stats/summary. Only `date_from`/`date_to` are accepted — the full
 *  transaction filter set does not apply here (CLAUDE.md 2.5). Every
 *  aggregate already excludes `exclude_from_stats` rows server-side. */
export function getStatsSummary(params) {
  return api.get('/stats/summary', params);
}

/**
 * GET /stats/by-category. Money per category with a subcategory level nested
 * under each, over `{ date_from, date_to }`.
 *
 * Not the same figures as `/stats/summary`'s `by_category`: this one keeps
 * every row, including categories that net positive and unfiled income, so the
 * entries add up to `totals`.
 */
export function getCategoryBreakdown(params) {
  return api.get('/stats/by-category', params);
}

/**
 * GET /stats/by-tag, plus an untagged entry (`tag_id: null`).
 *
 * Entries **overlap** — a transaction carrying two tags counts in full under
 * both — so they do not sum to `totals`, which is every countable row in the
 * range. The page says so on screen.
 */
export function getTagBreakdown(params) {
  return api.get('/stats/by-tag', params);
}

/**
 * GET /stats/trend — one breakdown row month by month.
 *
 * `params` carries the date range plus the row's own filter, whose keys
 * (`category_id`, `subcategory_id`, `uncategorized`, `no_subcategory`,
 * `tag_id`, `untagged`) are spelled exactly like the transaction list's, so the
 * same object addresses both this endpoint and `/transaktionen`.
 */
export function getTrend(params) {
  return api.get('/stats/trend', params);
}

/** GET /stats/balance. Not date-filtered: the balance is anchored to a
 *  hand-verified figure in the backend's `balance.py` and carried forward by
 *  every movement since, so a date range would not mean anything here. */
export function getBalance() {
  return api.get('/stats/balance');
}
