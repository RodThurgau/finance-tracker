import { AlertTriangle, ChevronDown } from 'lucide-react';

import { SourceBadge } from './Pills.jsx';
import { formatAmount, formatDate, isNegativeAmount } from '../lib/format.js';

/**
 * What preview_csv (backend) returns before anything is written: the detected
 * source, the preamble preclean discarded, the first few parsed rows, and any
 * row-level parse errors — so a wrong file is obvious before importing.
 */
export function ImportPreview({ preview }) {
  const { source, preamble_lines: preambleLines, rows, total_rows: totalRows, errors } = preview;

  return (
    <div className="mt-4 space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface-raised p-4">
        <SourceBadge source={source} />
        <span className="text-sm text-content-muted">
          {totalRows} {totalRows === 1 ? 'Zeile' : 'Zeilen'} erkannt
          {rows.length < totalRows && ` — Vorschau zeigt die ersten ${rows.length}`}
        </span>
      </div>

      <details className="rounded-xl border border-line bg-surface-raised p-4" open={preambleLines.length > 0}>
        <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium text-content-muted [&::-webkit-details-marker]:hidden">
          <ChevronDown size={14} className="transition-transform [details[open]_&]:rotate-180" />
          {preambleLines.length > 0
            ? `Verworfene Kopfzeilen (${preambleLines.length})`
            : 'Keine Präambel gefunden'}
        </summary>
        {preambleLines.length > 0 && (
          <pre className="mt-3 max-h-48 overflow-y-auto overscroll-contain whitespace-pre-wrap rounded-lg bg-surface p-3 font-mono text-xs text-content-muted">
            {preambleLines.join('\n')}
          </pre>
        )}
      </details>

      {errors.length > 0 && (
        <div className="rounded-xl border border-negative/40 bg-negative/10 p-4">
          <p className="flex items-center gap-2 text-sm font-medium text-negative">
            <AlertTriangle size={16} />
            {errors.length} {errors.length === 1 ? 'Zeile' : 'Zeilen'} konnten nicht gelesen werden
          </p>
          <ul className="mt-2 space-y-1 text-sm text-negative/90">
            {errors.map((error) => (
              <li key={`${error.row_number}-${error.column}`}>
                Zeile {error.row_number}, Spalte „{error.column}“ ({error.value || '—'}):{' '}
                {error.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full text-sm">
            <thead className="bg-surface-raised">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-content-muted">
                  Datum
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-content-muted">
                  Beschreibung
                </th>
                <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-content-muted">
                  Betrag
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index} className="border-t border-line">
                  <td className="tabular whitespace-nowrap px-3 py-2 text-content-muted">
                    {formatDate(row.date)}
                  </td>
                  <td className="max-w-md truncate px-3 py-2" title={row.description}>
                    {row.description}
                  </td>
                  <td
                    className={`tabular whitespace-nowrap px-3 py-2 text-right font-medium ${
                      isNegativeAmount(row.amount) ? 'text-negative' : 'text-positive'
                    }`}
                  >
                    {formatAmount(row.amount, row.currency)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
