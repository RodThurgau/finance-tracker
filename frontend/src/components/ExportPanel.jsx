import { useCallback, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Download } from 'lucide-react';

import { exportCsvUrl } from '../api/export.js';
import { listTransactions } from '../api/transactions.js';
import { formatCount, formatDate } from '../lib/format.js';
import { FilterBar } from './FilterBar.jsx';

const DEFAULT_FILTERS = {
  category_id: '',
  tag_id: [],
  untagged: '',
  source: '',
  date_from: '',
  date_to: '',
  search: '',
  excluded: '',
};

/** There's no dedicated export-preview endpoint — `GET /transactions` already
 *  returns `total` for any filter set, and asking for one row sorted by date
 *  ascending vs. descending gives the earliest/latest date for free. Two
 *  cheap requests instead of a new backend endpoint. */
async function fetchPreview(filters) {
  const [earliest, latest] = await Promise.all([
    listTransactions({ ...filters, page_size: 1, sort_by: 'date', sort_dir: 'asc' }),
    listTransactions({ ...filters, page_size: 1, sort_by: 'date', sort_dir: 'desc' }),
  ]);
  return {
    total: earliest.total,
    dateFrom: earliest.items[0]?.date ?? null,
    dateTo: latest.items[0]?.date ?? null,
  };
}

export function ExportPanel() {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);

  const setFilter = useCallback((patch) => {
    setFilters((previous) => ({ ...previous, ...patch }));
  }, []);

  const preview = useQuery({
    queryKey: ['export-preview', filters],
    queryFn: () => fetchPreview(filters),
    placeholderData: keepPreviousData,
  });

  const total = preview.data?.total ?? 0;
  const canDownload = !preview.isLoading && total > 0;

  return (
    <div>
      <FilterBar
        filters={filters}
        onChange={setFilter}
        onReset={() => setFilters(DEFAULT_FILTERS)}
      />

      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-line bg-surface-raised p-4">
        <p className="text-sm text-content-muted">
          {preview.isLoading ? (
            'Wird berechnet …'
          ) : total > 0 ? (
            <>
              <span className="font-medium text-content">{formatCount(total)}</span> Buchungen ·{' '}
              {formatDate(preview.data.dateFrom)} – {formatDate(preview.data.dateTo)}
            </>
          ) : (
            'Keine Buchungen im aktuellen Filter.'
          )}
        </p>

        <a
          href={canDownload ? exportCsvUrl(filters) : undefined}
          aria-disabled={!canDownload}
          className={`ml-auto flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
            canDownload
              ? 'bg-accent text-surface'
              : 'pointer-events-none bg-accent/40 text-surface/70'
          }`}
        >
          <Download size={16} />
          CSV herunterladen
        </a>
      </div>
    </div>
  );
}
