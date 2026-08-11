import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';

import { getBalance, getStatsSummary } from '../api/stats.js';
import { CategoryPieChart } from '../components/CategoryPieChart.jsx';
import { ChartCard } from '../components/ChartCard.jsx';
import { DateRangeFilter } from '../components/DateRangeFilter.jsx';
import { MonthlyBarChart } from '../components/MonthlyBarChart.jsx';
import { PageHeader } from '../components/PageHeader.jsx';
import { SummaryCards } from '../components/SummaryCards.jsx';
import { TopMerchants } from '../components/TopMerchants.jsx';
import { calendarMonthRange, formatMonth } from '../lib/dateRanges.js';

// The cards report the last *complete* month, not the current one: a month
// still in progress is always missing most of its spending, so its totals and
// especially its trend read as a collapse rather than as information.
const SUMMARY_MONTH = calendarMonthRange(1);
const COMPARISON_MONTH = calendarMonthRange(2);
const EMPTY_RANGE = { date_from: '', date_to: '' };

const monthLabel = (range) => formatMonth(range.from.slice(0, 7));

function useStatsSummary(key, params) {
  return useQuery({
    queryKey: ['stats-summary', key, params],
    queryFn: () => getStatsSummary(params),
  });
}

export function Overview() {
  const [range, setRange] = useState(EMPTY_RANGE);

  const summaryMonth = useStatsSummary('summary-month', {
    date_from: SUMMARY_MONTH.from,
    date_to: SUMMARY_MONTH.to,
  });
  const comparisonMonth = useStatsSummary('comparison-month', {
    date_from: COMPARISON_MONTH.from,
    date_to: COMPARISON_MONTH.to,
  });
  const rangeStats = useStatsSummary('range', range);
  const balance = useQuery({ queryKey: ['stats-balance'], queryFn: getBalance });

  const cardsError = summaryMonth.error ?? comparisonMonth.error ?? balance.error;
  const cardsReady = summaryMonth.isSuccess && comparisonMonth.isSuccess;

  return (
    <>
      <PageHeader title="Übersicht" description="Einnahmen, Ausgaben und Auswertungen." />

      <p className="mb-6 text-sm text-content-muted">
        Von der Statistik ausgeschlossene Transaktionen fließen in keine dieser Auswertungen ein.{' '}
        <Link to="/transaktionen?excluded=true" className="font-medium text-accent hover:underline">
          Ausgeschlossene Transaktionen ansehen
        </Link>
        <br />
        Ebenso unberücksichtigt bleiben PayPal-Verrechnungen — die ING-Lastschrift an PayPal und die
        zugehörige Bankgutschrift, die dieselbe Zahlung ein zweites und drittes Mal abbilden.{' '}
        <Link
          to="/transaktionen?internal=only"
          className="font-medium text-accent hover:underline"
        >
          PayPal-Verrechnungen ansehen
        </Link>
      </p>

      {cardsError && (
        <p className="mb-4 rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
          Kennzahlen konnten nicht geladen werden: {cardsError.message}
        </p>
      )}
      {cardsReady && (
        <div className="mb-8">
          <SummaryCards
            current={summaryMonth.data}
            previous={comparisonMonth.data}
            periodLabel={monthLabel(SUMMARY_MONTH)}
            comparisonLabel={monthLabel(COMPARISON_MONTH)}
            balance={balance.data}
          />
        </div>
      )}

      <DateRangeFilter value={range} onChange={setRange} />

      {rangeStats.isError && (
        <p className="mb-4 rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
          Diagramme konnten nicht geladen werden: {rangeStats.error.message}
        </p>
      )}

      {rangeStats.isSuccess && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ChartCard
              title="Ausgaben nach Kategorie"
              hint="Einnahmen einer Kategorie sind gegengerechnet, z. B. erstattete Miete. Ohne Kategorie zählen nur Ausgaben."
            >
              <CategoryPieChart data={rangeStats.data.by_category} />
            </ChartCard>
            <ChartCard title="Einnahmen und Ausgaben je Monat">
              <MonthlyBarChart data={rangeStats.data.by_month} />
            </ChartCard>
          </div>

          <ChartCard title="Top 10 Händler">
            <TopMerchants data={rangeStats.data.top_merchants} />
          </ChartCard>
        </div>
      )}
    </>
  );
}
