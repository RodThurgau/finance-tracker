/**
 * The pieces both analytics tables are built from — the money columns, the
 * per-row actions, and the two panels a row can open: its month-by-month
 * history and the transactions behind it.
 *
 * A row addresses its own slice of the ledger through a plain `params` object
 * whose keys are spelled exactly like the transaction list's filters
 * (`category_id`, `subcategory_id`, `uncategorized`, `no_subcategory`,
 * `tag_id`, `untagged`). The same object is handed to `/stats/trend`, to
 * `/transactions` and into the link to the Transaktionen page, so the three can
 * never end up describing different rows.
 */

import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ChevronDown,
  ChevronRight,
  ExternalLink,
  MoveDown,
  MoveUp,
  TrendingUp,
} from 'lucide-react';

import { buildQuery } from '../api/client.js';
import { getTrend } from '../api/stats.js';
import { listTransactions } from '../api/transactions.js';
import { fillMonthGaps, formatMonth } from '../lib/dateRanges.js';
import { formatAmount, formatCount, formatDate, formatPercent } from '../lib/format.js';
import { computeTrend } from '../lib/trend.js';
import { MonthlyBarChart } from './MonthlyBarChart.jsx';

/** Name, Buchungen, Einnahmen, Ausgaben, Saldo, Aktionen. */
export const COLUMN_COUNT = 6;

const HEAD = 'px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-content-muted';
const HEAD_RIGHT = `${HEAD} text-right`;
const CELL = 'border-t border-line px-3 py-2';
const NUMBER_CELL = `${CELL} tabular text-right whitespace-nowrap`;
const ICON_BUTTON = 'rounded-md p-1.5 text-content-muted hover:bg-surface-hover hover:text-content';
// How many transactions a drill-down shows before handing off to the full list.
const DRILL_DOWN_SIZE = 25;

// The transaction list keeps `exclude_from_stats` rows — the flag only hides a
// row from aggregates — while every figure on this page drops them. Left alone,
// a drill-down would list rows the total above it does not count. Internal
// transfers need no such opt-out: the list hides them by default already.
const COUNTABLE_ROWS = { excluded: false };

/** Zero reads as neither income nor expense — coloring it would imply one. */
function amountTone(amount) {
  if (Number(amount) === 0) return 'text-content-muted';
  return String(amount).startsWith('-') ? 'text-negative' : 'text-positive';
}

export function BreakdownHead({ nameLabel }) {
  return (
    <thead className="bg-surface-raised">
      <tr>
        <th scope="col" className={HEAD}>
          {nameLabel}
        </th>
        <th scope="col" className={HEAD_RIGHT}>
          Buchungen
        </th>
        <th scope="col" className={HEAD_RIGHT}>
          Einnahmen
        </th>
        <th scope="col" className={HEAD_RIGHT}>
          Ausgaben
        </th>
        <th scope="col" className={HEAD_RIGHT}>
          Saldo
        </th>
        <th scope="col" className={HEAD_RIGHT}>
          <span className="sr-only">Aktionen</span>
        </th>
      </tr>
    </thead>
  );
}

/** The four figures of a `SpendBucket`, as table cells. */
export function BucketCells({ bucket, bold = false }) {
  return (
    <>
      <td className={`${NUMBER_CELL} text-content-muted`}>
        {formatCount(bucket.transaction_count)}
      </td>
      <td className={`${NUMBER_CELL} ${amountTone(bucket.income)}`}>
        {formatAmount(bucket.income)}
      </td>
      <td className={`${NUMBER_CELL} ${amountTone(bucket.expenses)}`}>
        {formatAmount(bucket.expenses)}
      </td>
      <td className={`${NUMBER_CELL} ${amountTone(bucket.net)} ${bold ? 'font-semibold' : ''}`}>
        {formatAmount(bucket.net)}
      </td>
    </>
  );
}

export function ExpandButton({ isOpen, onClick, label }) {
  const Icon = isOpen ? ChevronDown : ChevronRight;
  return (
    <button type="button" onClick={onClick} aria-expanded={isOpen} aria-label={label} className={ICON_BUTTON}>
      <Icon size={16} />
    </button>
  );
}

/**
 * The two things a row can do: open its monthly history, or leave for the
 * transaction list carrying the row's filter and the page's date range.
 */
export function RowActions({ params, range, label, isTrendOpen, onToggleTrend }) {
  return (
    <td className={`${CELL} text-right whitespace-nowrap`}>
      <button
        type="button"
        onClick={onToggleTrend}
        aria-expanded={isTrendOpen}
        title="Monatlicher Verlauf"
        aria-label={`Monatlicher Verlauf für ${label}`}
        className={`${ICON_BUTTON} ${isTrendOpen ? 'bg-accent-soft text-accent' : ''}`}
      >
        <TrendingUp size={16} />
      </button>
      <Link
        to={`/transaktionen${buildQuery({ ...params, ...range, ...COUNTABLE_ROWS })}`}
        title="In den Transaktionen öffnen"
        aria-label={`${label} in den Transaktionen öffnen`}
        className={`${ICON_BUTTON} inline-block`}
      >
        <ExternalLink size={16} />
      </Link>
    </td>
  );
}

/**
 * A row's month-by-month history: the same income/expenses bars the Übersicht
 * uses, over a table of the underlying figures.
 *
 * The month-over-month column is deliberately colorless. Everywhere else in the
 * app a trend arrow is green or red, but that mapping depends on knowing
 * whether more is better — true for a salary, false for groceries — and this
 * panel is pointed at whichever row was clicked. An arrow that guessed would be
 * wrong half the time, so it states the direction and leaves the reading to
 * whoever picked the row.
 */
export function TrendRow({ label, params, range, colSpan = COLUMN_COUNT }) {
  const query = useQuery({
    queryKey: ['stats-trend', params, range],
    queryFn: () => getTrend({ ...params, ...range }),
  });

  const points = query.data ? fillMonthGaps(query.data.points) : [];

  return (
    <tr>
      <td colSpan={colSpan} className="border-t border-line bg-surface p-4">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-sm font-semibold">Monatlicher Verlauf · {label}</h3>
          {query.data && (
            <p className="text-xs text-content-muted">
              Saldo im Zeitraum{' '}
              <span className={`tabular font-medium ${amountTone(query.data.totals.net)}`}>
                {formatAmount(query.data.totals.net)}
              </span>{' '}
              aus {formatCount(query.data.totals.transaction_count)}{' '}
              {query.data.totals.transaction_count === 1 ? 'Buchung' : 'Buchungen'}
            </p>
          )}
        </div>

        {query.isPending && <p className="text-sm text-content-muted">Wird geladen …</p>}
        {query.isError && (
          <p className="rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
            Verlauf konnte nicht geladen werden: {query.error.message}
          </p>
        )}

        {query.isSuccess &&
          (points.length === 0 ? (
            <p className="text-sm text-content-muted">Keine Buchungen im gewählten Zeitraum.</p>
          ) : (
            <>
              <MonthlyBarChart data={points} />
              <div className="mt-3 overflow-x-auto rounded-lg border border-line">
                <table className="w-full min-w-[34rem] text-sm">
                  <thead className="bg-surface-raised">
                    <tr>
                      <th scope="col" className={HEAD}>
                        Monat
                      </th>
                      <th scope="col" className={HEAD_RIGHT}>
                        Buchungen
                      </th>
                      <th scope="col" className={HEAD_RIGHT}>
                        Einnahmen
                      </th>
                      <th scope="col" className={HEAD_RIGHT}>
                        Ausgaben
                      </th>
                      <th scope="col" className={HEAD_RIGHT}>
                        Saldo
                      </th>
                      <th scope="col" className={HEAD_RIGHT}>
                        ggü. Vormonat
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {points.map((point, index) => {
                      // Magnitudes, not signed values: for a spending row both
                      // months are negative, and "moved toward zero" is not what
                      // anyone means by a smaller month.
                      const trend =
                        index > 0
                          ? computeTrend(point.net, points[index - 1].net, { useAbsolute: true })
                          : null;
                      const Arrow = trend?.isUp ? MoveUp : MoveDown;
                      return (
                        <tr key={point.month} className="hover:bg-surface-hover">
                          <td className={`${CELL} tabular whitespace-nowrap`}>
                            {formatMonth(point.month)}
                          </td>
                          <BucketCells bucket={point} />
                          <td className={`${NUMBER_CELL} text-content-muted`}>
                            {trend ? (
                              <span className="inline-flex items-center gap-1">
                                <Arrow size={12} />
                                {formatPercent(trend.percent)}
                              </span>
                            ) : (
                              '—'
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          ))}
      </td>
    </tr>
  );
}

/**
 * The transactions behind one row — the last level of the drill-down.
 *
 * Capped at the newest {@link DRILL_DOWN_SIZE}: this is a look at what is in
 * the bucket, not a second transaction list. The link carries the same filter
 * to the page that does paging, sorting and editing properly.
 */
export function DrillDownRow({ label, params, range, colSpan = COLUMN_COUNT }) {
  const query = useQuery({
    queryKey: ['transactions', 'drill-down', params, range],
    queryFn: () =>
      listTransactions({
        ...params,
        ...range,
        ...COUNTABLE_ROWS,
        page_size: DRILL_DOWN_SIZE,
        sort_by: 'date',
        sort_dir: 'desc',
      }),
  });

  const items = query.data?.items ?? [];
  const total = query.data?.total ?? 0;

  return (
    <tr>
      <td colSpan={colSpan} className="border-t border-line bg-surface p-4">
        {query.isPending && <p className="text-sm text-content-muted">Wird geladen …</p>}
        {query.isError && (
          <p className="rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
            Transaktionen konnten nicht geladen werden: {query.error.message}
          </p>
        )}

        {query.isSuccess &&
          (items.length === 0 ? (
            <p className="text-sm text-content-muted">Keine Buchungen im gewählten Zeitraum.</p>
          ) : (
            <>
              <ul className="divide-y divide-line rounded-lg border border-line">
                {items.map((transaction) => (
                  <li key={transaction.id} className="flex items-center gap-3 px-3 py-1.5 text-sm">
                    <span className="tabular shrink-0 text-content-muted">
                      {formatDate(transaction.date)}
                    </span>
                    <span className="flex-1 truncate" title={transaction.description}>
                      {transaction.description}
                    </span>
                    <span
                      className={`tabular shrink-0 font-medium ${amountTone(transaction.amount)}`}
                    >
                      {formatAmount(transaction.amount, transaction.currency)}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-content-muted">
                {total > items.length
                  ? `Neueste ${formatCount(items.length)} von ${formatCount(total)} Buchungen. `
                  : ''}
                <Link
                  to={`/transaktionen${buildQuery({ ...params, ...range, ...COUNTABLE_ROWS })}`}
                  className="font-medium text-accent hover:underline"
                >
                  Alle in den Transaktionen öffnen
                </Link>{' '}
                — {label}
              </p>
            </>
          ))}
      </td>
    </tr>
  );
}

/**
 * The range's headline figures, above the table.
 *
 * `note` is where a page explains what its rows do and do not add up to — the
 * tag table's entries overlap, and a total that silently disagrees with the
 * rows under it is worse than no total.
 */
export function BucketTotals({ totals, note }) {
  const tiles = [
    { label: 'Einnahmen', value: totals.income },
    { label: 'Ausgaben', value: totals.expenses },
    { label: 'Saldo', value: totals.net },
  ];

  return (
    <div className="mb-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {tiles.map((tile) => (
          <div key={tile.label} className="rounded-xl border border-line bg-surface-raised p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">
              {tile.label}
            </p>
            <p className={`mt-1 text-2xl font-semibold ${amountTone(tile.value)}`}>
              {formatAmount(tile.value)}
            </p>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-content-muted">
        {formatCount(totals.transaction_count)}{' '}
        {totals.transaction_count === 1 ? 'Buchung' : 'Buchungen'} im gewählten Zeitraum
        {note ? ` · ${note}` : ''}
      </p>
    </div>
  );
}
