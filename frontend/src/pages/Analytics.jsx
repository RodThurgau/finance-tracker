import { useState } from 'react';
import { Link, NavLink, Outlet, useOutletContext } from 'react-router-dom';

import { DateRangeFilter } from '../components/DateRangeFilter.jsx';
import { PageHeader } from '../components/PageHeader.jsx';

/**
 * The Auswertungen tab: a shell holding the sub-tabs and the one date range
 * they share.
 *
 * The range lives here rather than in each page so switching sub-tabs keeps the
 * period you were looking at — "the last quarter, by category" and "the last
 * quarter, by tag" are two views of one question, and re-picking the range at
 * every tab change would make them feel like unrelated screens.
 */
const EMPTY_RANGE = { date_from: '', date_to: '' };

const TABS = [
  { to: 'kategorien', label: 'Kategorien' },
  { to: 'tags', label: 'Tags' },
];

function tabClasses({ isActive }) {
  const base = 'px-3 py-2 text-sm';
  return isActive
    ? `${base} bg-accent-soft text-accent`
    : `${base} text-content-muted hover:bg-surface-hover hover:text-content`;
}

/** The shared date range, for the sub-tab pages. */
export function useAnalyticsRange() {
  return useOutletContext();
}

export function Analytics() {
  const [range, setRange] = useState(EMPTY_RANGE);

  return (
    <>
      <PageHeader
        title="Auswertungen"
        description="Wohin das Geld geht — nach Kategorie und nach Tag, über einen frei wählbaren Zeitraum."
      />

      <p className="mb-4 text-sm text-content-muted">
        Wie auf der Übersicht bleiben von der Statistik ausgeschlossene Transaktionen und
        PayPal-Verrechnungen außen vor.{' '}
        <Link to="/transaktionen?internal=only" className="font-medium text-accent hover:underline">
          PayPal-Verrechnungen ansehen
        </Link>
      </p>

      <div className="mb-4 flex w-fit flex-wrap items-center overflow-hidden rounded-lg border border-line">
        {TABS.map((tab) => (
          <NavLink key={tab.to} to={tab.to} className={tabClasses}>
            {tab.label}
          </NavLink>
        ))}
      </div>

      <DateRangeFilter value={range} onChange={setRange} label="Zeitraum" />

      <Outlet context={range} />
    </>
  );
}
