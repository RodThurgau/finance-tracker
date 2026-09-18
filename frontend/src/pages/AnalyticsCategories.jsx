import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { getCategoryBreakdown } from '../api/stats.js';
import { BucketTotals } from '../components/Breakdown.jsx';
import { CategoryBreakdownTable } from '../components/CategoryBreakdownTable.jsx';
import { useAnalyticsRange } from './Analytics.jsx';

export function AnalyticsCategories() {
  const range = useAnalyticsRange();
  const query = useQuery({
    queryKey: ['stats-by-category', range],
    queryFn: () => getCategoryBreakdown(range),
    // Changing the range swaps a whole table; keeping the previous one on
    // screen while the new figures load stops the page from collapsing to a
    // "Wird geladen …" line on every click.
    placeholderData: keepPreviousData,
  });

  if (query.isPending) return <p className="text-sm text-content-muted">Wird geladen …</p>;
  if (query.isError) {
    return (
      <p className="rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
        Auswertung konnte nicht geladen werden: {query.error.message}
      </p>
    );
  }

  return (
    <>
      <BucketTotals
        totals={query.data.totals}
        note="jede Buchung zählt in genau einer Kategorie, die Zeilen ergeben zusammen den Gesamtsaldo"
      />
      <CategoryBreakdownTable data={query.data} range={range} />
    </>
  );
}
