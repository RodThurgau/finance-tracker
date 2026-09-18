import { Fragment, useState } from 'react';

import {
  BreakdownHead,
  BucketCells,
  DrillDownRow,
  ExpandButton,
  RowActions,
  TrendRow,
} from './Breakdown.jsx';

/**
 * Money per tag, each row expandable into its transactions and its monthly
 * history. `data` is `/stats/by-tag`.
 *
 * Two levels rather than the category table's three: tags are flat, and a
 * transaction can carry several of them, so there is no hierarchy to walk. That
 * same many-to-many is why there is no "Gesamt" row here — the rows overlap and
 * summing them would produce a number that is not the ledger's. The page states
 * the range's real totals above the table instead.
 */

const tagKey = (entry) => entry.tag_id ?? 'none';
const tagLabel = (entry) => entry.tag_name ?? 'Ohne Tag';
const tagParams = (entry) => (entry.tag_id === null ? { untagged: true } : { tag_id: entry.tag_id });

export function TagBreakdownTable({ data, range }) {
  const [drilled, setDrilled] = useState(() => new Set());
  const [trendFor, setTrendFor] = useState(null);

  function toggleDrilled(key) {
    setDrilled((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const toggleTrend = (key) => setTrendFor((previous) => (previous === key ? null : key));

  if (data.entries.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-line p-10 text-center text-sm text-content-muted">
        Keine Buchungen im gewählten Zeitraum.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full min-w-[52rem] text-sm">
        <BreakdownHead nameLabel="Tag" />
        <tbody>
          {data.entries.map((entry) => {
            const key = tagKey(entry);
            const label = tagLabel(entry);
            const params = tagParams(entry);
            const isDrilled = drilled.has(key);

            return (
              <Fragment key={key}>
                <tr className="hover:bg-surface-hover">
                  <td className="border-t border-line px-3 py-2">
                    <div className="flex items-center gap-2">
                      <ExpandButton
                        isOpen={isDrilled}
                        onClick={() => toggleDrilled(key)}
                        label={`Buchungen mit ${label} ${isDrilled ? 'einklappen' : 'ausklappen'}`}
                      />
                      <span
                        className="size-3 shrink-0 rounded-full border border-line"
                        style={entry.color ? { backgroundColor: entry.color } : undefined}
                        aria-hidden="true"
                      />
                      <span className={entry.tag_id === null ? 'text-content-muted' : 'font-medium'}>
                        {label}
                      </span>
                    </div>
                  </td>
                  <BucketCells bucket={entry} bold />
                  <RowActions
                    params={params}
                    range={range}
                    label={label}
                    isTrendOpen={trendFor === key}
                    onToggleTrend={() => toggleTrend(key)}
                  />
                </tr>

                {trendFor === key && <TrendRow label={label} params={params} range={range} />}
                {isDrilled && <DrillDownRow label={label} params={params} range={range} />}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
