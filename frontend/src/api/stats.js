import { api } from './client.js';

/** GET /stats/summary. Only `date_from`/`date_to` are accepted — the full
 *  transaction filter set does not apply here (CLAUDE.md 2.5). Every
 *  aggregate already excludes `exclude_from_stats` rows server-side. */
export function getStatsSummary(params) {
  return api.get('/stats/summary', params);
}

/** GET /stats/balance. Not date-filtered: the balance is anchored to a
 *  hand-verified figure in the backend's `balance.py` and carried forward by
 *  every movement since, so a date range would not mean anything here. */
export function getBalance() {
  return api.get('/stats/balance');
}
