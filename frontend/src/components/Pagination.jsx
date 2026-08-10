import { ChevronLeft, ChevronRight } from 'lucide-react';

import { formatCount } from '../lib/format.js';

const PAGE_SIZES = [25, 50, 100, 200];

const BUTTON =
  'flex items-center gap-1 rounded-lg border border-line px-3 py-1.5 text-sm text-content-muted hover:bg-surface-hover hover:text-content disabled:opacity-40 disabled:hover:bg-transparent';

export function Pagination({ page, pageSize, total, onChange }) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);

  return (
    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-content-muted">
      <span>
        {formatCount(first)}–{formatCount(last)} von {formatCount(total)}
      </span>

      <div className="flex items-center gap-2">
        <select
          value={pageSize}
          onChange={(event) => onChange({ page_size: event.target.value, page: 1 })}
          aria-label="Zeilen pro Seite"
          className="rounded-lg border border-line bg-surface px-2 py-1.5 text-sm"
        >
          {PAGE_SIZES.map((size) => (
            <option key={size} value={size}>
              {size} pro Seite
            </option>
          ))}
        </select>

        <button
          type="button"
          className={BUTTON}
          disabled={page <= 1}
          onClick={() => onChange({ page: page - 1 })}
        >
          <ChevronLeft size={16} />
          Zurück
        </button>
        <span className="tabular">
          Seite {formatCount(page)} von {formatCount(pageCount)}
        </span>
        <button
          type="button"
          className={BUTTON}
          disabled={page >= pageCount}
          onClick={() => onChange({ page: page + 1 })}
        >
          Weiter
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
