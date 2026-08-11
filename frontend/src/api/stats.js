import { api } from './client.js';

/** GET /stats/summary. Only `date_from`/`date_to` are accepted — the full
 *  transaction filter set does not apply here (CLAUDE.md 2.5). Every
 *  aggregate already excludes `exclude_from_stats` rows server-side. */
export function getStatsSummary(params) {
  return api.get('/stats/summary', params);
}
