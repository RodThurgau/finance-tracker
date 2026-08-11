import { formatAmount } from '../lib/format.js';

/** Ranked list of top-10 merchants by spend. `data` is `/stats/summary`'s
 *  `top_merchants` (expense-only, already sorted, amounts negative). The
 *  background bar is a rough share-of-max cue, not a value to read exactly —
 *  the amount text carries the real number. */
export function TopMerchants({ data }) {
  if (data.length === 0) {
    return <p className="text-sm text-content-muted">Keine Ausgaben im gewählten Zeitraum.</p>;
  }

  const maxAmount = Math.max(...data.map((entry) => Math.abs(Number(entry.total))));

  return (
    <ul className="space-y-1">
      {data.map((entry, index) => {
        const share = maxAmount > 0 ? (Math.abs(Number(entry.total)) / maxAmount) * 100 : 0;
        return (
          <li key={entry.counter_account} className="relative overflow-hidden rounded-lg">
            <div
              className="absolute inset-y-0 left-0 bg-accent/10"
              style={{ width: `${share}%` }}
              aria-hidden="true"
            />
            <div className="relative flex items-center gap-3 px-3 py-2 text-sm">
              <span className="w-5 shrink-0 text-content-muted">{index + 1}.</span>
              <span className="flex-1 truncate" title={entry.counter_account}>
                {entry.counter_account}
              </span>
              <span className="tabular font-medium text-negative">{formatAmount(entry.total)}</span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
