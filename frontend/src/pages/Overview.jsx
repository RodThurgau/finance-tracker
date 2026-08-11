import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { X } from 'lucide-react';

import { getStatsSummary } from '../api/stats.js';
import { CategoryPieChart } from '../components/CategoryPieChart.jsx';
import { ChartCard } from '../components/ChartCard.jsx';
import { DateField } from '../components/DateField.jsx';
import { MonthlyBarChart } from '../components/MonthlyBarChart.jsx';
import { PageHeader } from '../components/PageHeader.jsx';
import { SummaryCards } from '../components/SummaryCards.jsx';
import { TopMerchants } from '../components/TopMerchants.jsx';
import { calendarMonthRange } from '../lib/dateRanges.js';

const CURRENT_MONTH = calendarMonthRange(0);
const PREVIOUS_MONTH = calendarMonthRange(1);
const EMPTY_RANGE = { date_from: '', date_to: '' };

function useStatsSummary(key, params) {
  return useQuery({
    queryKey: ['stats-summary', key, params],
    queryFn: () => getStatsSummary(params),
  });
}

export function Overview() {
  const [range, setRange] = useState(EMPTY_RANGE);

  const currentMonth = useStatsSummary('current-month', {
    date_from: CURRENT_MONTH.from,
    date_to: CURRENT_MONTH.to,
  });
  const previousMonth = useStatsSummary('previous-month', {
    date_from: PREVIOUS_MONTH.from,
    date_to: PREVIOUS_MONTH.to,
  });
  const rangeStats = useStatsSummary('range', range);

  const cardsError = currentMonth.error ?? previousMonth.error;
  const cardsReady = currentMonth.isSuccess && previousMonth.isSuccess;

  return (
    <>
      <PageHeader title="Übersicht" description="Einnahmen, Ausgaben und Auswertungen." />

      <p className="mb-6 text-sm text-content-muted">
        Von der Statistik ausgeschlossene Transaktionen fließen in keine dieser Auswertungen ein.{' '}
        <Link to="/transaktionen?excluded=true" className="font-medium text-accent hover:underline">
          Ausgeschlossene Transaktionen ansehen
        </Link>
      </p>

      {cardsError && (
        <p className="mb-4 rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
          Kennzahlen konnten nicht geladen werden: {cardsError.message}
        </p>
      )}
      {cardsReady && (
        <div className="mb-8">
          <SummaryCards current={currentMonth.data} previous={previousMonth.data} />
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-sm text-content-muted">Zeitraum für die Diagramme:</span>
        <DateField
          value={range.date_from}
          onChange={(value) => setRange((previous) => ({ ...previous, date_from: value }))}
          label="Datum von"
        />
        <span className="text-sm text-content-muted">bis</span>
        <DateField
          value={range.date_to}
          onChange={(value) => setRange((previous) => ({ ...previous, date_to: value }))}
          label="Datum bis"
        />
        {(range.date_from || range.date_to) && (
          <button
            type="button"
            onClick={() => setRange(EMPTY_RANGE)}
            className="flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
          >
            <X size={14} />
            Zurücksetzen
          </button>
        )}
      </div>

      {rangeStats.isError && (
        <p className="mb-4 rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
          Diagramme konnten nicht geladen werden: {rangeStats.error.message}
        </p>
      )}

      {rangeStats.isSuccess && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ChartCard title="Ausgaben nach Kategorie">
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
