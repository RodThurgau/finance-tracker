import { useEffect, useState } from 'react';
import { Search, X } from 'lucide-react';

import { useCategories } from '../hooks/useLookups.js';
import { DateField } from './DateField.jsx';
import { TagFilter } from './TagFilter.jsx';

const FIELD =
  'rounded-lg border border-line bg-surface px-3 py-2 text-sm text-content placeholder:text-content-muted';

const SOURCES = [
  { value: '', label: 'Alle' },
  { value: 'ING', label: 'ING' },
  { value: 'PayPal', label: 'PayPal' },
];

export function FilterBar({ filters, onChange, onReset }) {
  const { data: categories } = useCategories();
  const [searchDraft, setSearchDraft] = useState(filters.search);

  // Adopt changes that came from outside the input (reset, or a link that
  // arrives with a search term in the URL).
  useEffect(() => {
    setSearchDraft(filters.search);
  }, [filters.search]);

  // Debounce typing so a query isn't fired per keystroke.
  useEffect(() => {
    if (searchDraft === filters.search) return undefined;
    const timer = setTimeout(() => onChange({ search: searchDraft }), 300);
    return () => clearTimeout(timer);
  }, [searchDraft, filters.search, onChange]);

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <div className="relative min-w-56 flex-1">
        <Search
          size={16}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-content-muted"
        />
        <input
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
          placeholder="Beschreibung durchsuchen"
          className={`${FIELD} w-full pl-9`}
        />
      </div>

      <select
        value={filters.category_id}
        onChange={(event) => onChange({ category_id: event.target.value })}
        className={FIELD}
      >
        <option value="">Alle Kategorien</option>
        {(categories ?? []).map((category) => (
          <option key={category.id} value={category.id}>
            {category.name}
          </option>
        ))}
      </select>

      <TagFilter
        selectedIds={filters.tag_id}
        untagged={filters.untagged}
        onChange={onChange}
      />

      <div className="flex items-center overflow-hidden rounded-lg border border-line">
        {SOURCES.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange({ source: option.value })}
            className={`px-3 py-2 text-sm ${
              filters.source === option.value
                ? 'bg-accent-soft text-accent'
                : 'text-content-muted hover:bg-surface-hover hover:text-content'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <DateField
          value={filters.date_from}
          onChange={(value) => onChange({ date_from: value })}
          label="Datum von"
        />
        <span className="text-sm text-content-muted">bis</span>
        <DateField
          value={filters.date_to}
          onChange={(value) => onChange({ date_to: value })}
          label="Datum bis"
        />
      </div>

      <select
        value={filters.excluded}
        onChange={(event) => onChange({ excluded: event.target.value })}
        className={FIELD}
        aria-label="Ausgeschlossene Transaktionen"
      >
        <option value="">Alle Zeilen</option>
        <option value="false">Ohne ausgeschlossene</option>
        <option value="true">Nur ausgeschlossene</option>
      </select>

      <button
        type="button"
        onClick={onReset}
        className="flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
      >
        <X size={14} />
        Filter zurücksetzen
      </button>
    </div>
  );
}
