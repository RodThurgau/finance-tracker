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
 * Money per category, in three levels: the category, its subcategories, and the
 * transactions themselves.
 *
 * Every level is a row in the same table rather than a separate view, so the
 * figure a row shows stays on screen next to what it is made of — the point of
 * drilling down is the comparison, and a drill-down that replaces the page
 * takes that away.
 *
 * `data` is `/stats/by-category`.
 */

// `null` is a real bucket here — the unfiled rows — so it needs a key of its
// own rather than being treated as "missing".
const categoryKey = (entry) => entry.category_id ?? 'none';
const subcategoryKey = (entry, subcategory) =>
  `${categoryKey(entry)}:${subcategory.subcategory_id ?? 'none'}`;

const categoryLabel = (entry) => entry.category_name ?? 'Ohne Kategorie';
const subcategoryLabel = (subcategory) => subcategory.subcategory_name ?? 'Ohne Unterkategorie';

const categoryParams = (entry) =>
  entry.category_id === null ? { uncategorized: true } : { category_id: entry.category_id };

const subcategoryParams = (entry, subcategory) => ({
  ...categoryParams(entry),
  ...(subcategory.subcategory_id === null
    ? { no_subcategory: true }
    : { subcategory_id: subcategory.subcategory_id }),
});

function Swatch({ color }) {
  return (
    <span
      className="size-3 shrink-0 rounded-full border border-line"
      style={color ? { backgroundColor: color } : undefined}
      aria-hidden="true"
    />
  );
}

export function CategoryBreakdownTable({ data, range }) {
  const [expanded, setExpanded] = useState(() => new Set());
  const [drilled, setDrilled] = useState(() => new Set());
  // One trend panel at a time: it is a full chart, and two of them stacked in a
  // table stop being a comparison and start being a scroll.
  const [trendFor, setTrendFor] = useState(null);

  function toggle(setter, key) {
    setter((previous) => {
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
        <BreakdownHead nameLabel="Kategorie" />
        {data.entries.map((entry) => {
          const key = categoryKey(entry);
          const isExpanded = expanded.has(key);
          const label = categoryLabel(entry);
          const params = categoryParams(entry);

          return (
            <tbody key={key}>
              <tr className="hover:bg-surface-hover">
                <td className="border-t border-line px-3 py-2">
                  <div className="flex items-center gap-2">
                    <ExpandButton
                      isOpen={isExpanded}
                      onClick={() => toggle(setExpanded, key)}
                      label={`Unterkategorien von ${label} ${isExpanded ? 'einklappen' : 'ausklappen'}`}
                    />
                    <Swatch color={entry.color} />
                    <span className="font-medium">{label}</span>
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

              {isExpanded &&
                entry.subcategories.map((subcategory) => {
                  const subKey = subcategoryKey(entry, subcategory);
                  const subLabel = subcategoryLabel(subcategory);
                  const subParams = subcategoryParams(entry, subcategory);
                  const isDrilled = drilled.has(subKey);

                  return (
                    <Fragment key={subKey}>
                      <tr className="hover:bg-surface-hover">
                        <td className="border-t border-line py-2 pl-10 pr-3">
                          <div className="flex items-center gap-2">
                            <ExpandButton
                              isOpen={isDrilled}
                              onClick={() => toggle(setDrilled, subKey)}
                              label={`Buchungen in ${subLabel} ${isDrilled ? 'einklappen' : 'ausklappen'}`}
                            />
                            <span
                              className={subcategory.subcategory_id === null ? 'text-content-muted' : ''}
                            >
                              {subLabel}
                            </span>
                          </div>
                        </td>
                        <BucketCells bucket={subcategory} />
                        <RowActions
                          params={subParams}
                          range={range}
                          label={`${label} · ${subLabel}`}
                          isTrendOpen={trendFor === subKey}
                          onToggleTrend={() => toggleTrend(subKey)}
                        />
                      </tr>

                      {trendFor === subKey && (
                        <TrendRow
                          label={`${label} · ${subLabel}`}
                          params={subParams}
                          range={range}
                        />
                      )}
                      {isDrilled && (
                        <DrillDownRow
                          label={`${label} · ${subLabel}`}
                          params={subParams}
                          range={range}
                        />
                      )}
                    </Fragment>
                  );
                })}
            </tbody>
          );
        })}

        <tfoot>
          <tr className="bg-surface-raised">
            <td className="border-t border-line px-3 py-2 font-semibold">Gesamt</td>
            <BucketCells bucket={data.totals} bold />
            <td className="border-t border-line" />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
