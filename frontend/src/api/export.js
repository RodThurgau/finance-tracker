import { apiUrl } from './client.js';

/** Absolute URL for `GET /export/csv` with the given filters — meant for a
 *  plain `<a href>` navigation, not `fetch`, so the browser handles the
 *  `Content-Disposition` download itself. */
export function exportCsvUrl(filters) {
  return apiUrl('/export/csv', filters);
}
