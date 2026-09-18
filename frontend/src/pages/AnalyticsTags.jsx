import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { getTagBreakdown } from '../api/stats.js';
import { BucketTotals } from '../components/Breakdown.jsx';
import { TagBreakdownTable } from '../components/TagBreakdownTable.jsx';
import { useAnalyticsRange } from './Analytics.jsx';

export function AnalyticsTags() {
  const range = useAnalyticsRange();
  const query = useQuery({
    queryKey: ['stats-by-tag', range],
    queryFn: () => getTagBreakdown(range),
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
        // Said plainly, because the table below genuinely does not add up: a
        // transaction with two tags is counted in full under both.
        note="Buchungen mit mehreren Tags zählen in jeder ihrer Zeilen — die Zeilen ergeben zusammen mehr als diesen Saldo"
      />
      <TagBreakdownTable data={query.data} range={range} />
    </>
  );
}
