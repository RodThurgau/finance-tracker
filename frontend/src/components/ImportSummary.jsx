import { AlertTriangle, CheckCircle2, ChevronDown } from 'lucide-react';

import { formatAmount, formatCount, formatDate } from '../lib/format.js';

function StatTile({ label, value, tone }) {
  return (
    <div className="rounded-xl border border-line bg-surface-raised p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular ${tone ?? ''}`}>{formatCount(value)}</p>
    </div>
  );
}

/** Result of a committed import: what CLAUDE.md's `ImportSummarySchema` returns. */
export function ImportSummary({ summary }) {
  const { new: created, updated, skipped, errors, date_range: dateRange, skipped_rows: skippedRows } =
    summary;

  return (
    <div className="mt-4 space-y-4">
      <div className="flex items-center gap-2 rounded-xl border border-positive/40 bg-positive/10 p-4 text-sm text-positive">
        <CheckCircle2 size={18} />
        Import abgeschlossen
        {dateRange && (
          <span className="text-positive/80">
            · {formatDate(dateRange[0])} – {formatDate(dateRange[1])}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Neu" value={created} tone="text-positive" />
        <StatTile label="Aktualisiert" value={updated} />
        <StatTile label="Übersprungen" value={skipped} />
        <StatTile label="Fehler" value={errors.length} tone={errors.length ? 'text-negative' : ''} />
      </div>

      {errors.length > 0 && (
        <div className="rounded-xl border border-negative/40 bg-negative/10 p-4">
          <p className="flex items-center gap-2 text-sm font-medium text-negative">
            <AlertTriangle size={16} />
            Nicht importierte Zeilen
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

      {skippedRows.length > 0 && (
        <details className="rounded-xl border border-line bg-surface-raised p-4">
          <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium text-content-muted [&::-webkit-details-marker]:hidden">
            <ChevronDown size={14} className="transition-transform [details[open]_&]:rotate-180" />
            Übersprungene Duplikate ({skippedRows.length})
          </summary>
          <div className="mt-3 max-h-64 overflow-y-auto overscroll-contain">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs font-semibold uppercase tracking-wide text-content-muted">
                  <th className="px-2 py-1">Datum</th>
                  <th className="px-2 py-1">Beschreibung</th>
                  <th className="px-2 py-1 text-right">Betrag</th>
                </tr>
              </thead>
              <tbody>
                {skippedRows.map((row) => (
                  <tr key={row.composite_hash} className="border-t border-line">
                    <td className="tabular whitespace-nowrap px-2 py-1 text-content-muted">
                      {formatDate(row.date)}
                    </td>
                    <td className="max-w-md truncate px-2 py-1" title={row.description}>
                      {row.description}
                    </td>
                    <td className="tabular whitespace-nowrap px-2 py-1 text-right">
                      {formatAmount(row.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  );
}
