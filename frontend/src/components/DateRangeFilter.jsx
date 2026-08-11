import { useState } from 'react';

import { calendarMonthRange, calendarYearRange, lastMonthsRange } from '../lib/dateRanges.js';
import { DateField } from './DateField.jsx';

/**
 * Date-range presets plus a custom range — a segmented control, styled like the
 * source toggle on the transaction filter bar.
 *
 * The active preset is *derived* by matching the current range against each
 * preset rather than stored alongside it. That way the highlight can never
 * disagree with the range actually in effect: typing a date by hand, or
 * arriving on a URL that carries one, lands on "Benutzerdefiniert" on its own
 * with nothing to keep in sync.
 *
 * The one piece of real state is whether the custom fields are open, since
 * "Benutzerdefiniert" has to be clickable while the range still happens to
 * match a preset.
 */
const EMPTY = { date_from: '', date_to: '' };

const asFilter = ({ from, to }) => ({ date_from: from, date_to: to });

const PRESETS = [
  // "Gesamt" is the unset range — the default, and the only preset that is not
  // a date window. Without it the empty range would read as "Benutzerdefiniert".
  { key: 'all', label: 'Gesamt', build: () => EMPTY },
  { key: 'month', label: 'Dieser Monat', build: () => asFilter(calendarMonthRange(0)) },
  { key: 'lastMonth', label: 'Letzter Monat', build: () => asFilter(calendarMonthRange(1)) },
  { key: 'quarter', label: 'Letzte 3 Monate', build: () => asFilter(lastMonthsRange(3)) },
  { key: 'year', label: 'Dieses Jahr', build: () => asFilter(calendarYearRange(0)) },
  { key: 'lastYear', label: 'Letztes Jahr', build: () => asFilter(calendarYearRange(1)) },
];

const CUSTOM = 'custom';

function matchingPreset(value) {
  return PRESETS.find((preset) => {
    const range = preset.build();
    return range.date_from === value.date_from && range.date_to === value.date_to;
  });
}

export function DateRangeFilter({ value, onChange, label = 'Zeitraum für die Diagramme' }) {
  const [isCustomOpen, setCustomOpen] = useState(false);

  const matched = matchingPreset(value);
  const activeKey = isCustomOpen || !matched ? CUSTOM : matched.key;
  const showFields = activeKey === CUSTOM;

  function selectPreset(preset) {
    setCustomOpen(false);
    onChange(preset.build());
  }

  return (
    <div className="mb-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-content-muted">{label}:</span>

        <div className="flex flex-wrap items-center overflow-hidden rounded-lg border border-line">
          {[...PRESETS, { key: CUSTOM, label: 'Benutzerdefiniert' }].map((preset) => {
            const isActive = activeKey === preset.key;
            return (
              <button
                key={preset.key}
                type="button"
                aria-pressed={isActive}
                onClick={() =>
                  preset.key === CUSTOM ? setCustomOpen(true) : selectPreset(preset)
                }
                className={`px-3 py-2 text-sm ${
                  isActive
                    ? 'bg-accent-soft text-accent'
                    : 'text-content-muted hover:bg-surface-hover hover:text-content'
                }`}
              >
                {preset.label}
              </button>
            );
          })}
        </div>
      </div>

      {showFields && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <DateField
            value={value.date_from}
            onChange={(date_from) => onChange({ ...value, date_from })}
            label="Datum von"
          />
          <span className="text-sm text-content-muted">bis</span>
          <DateField
            value={value.date_to}
            onChange={(date_to) => onChange({ ...value, date_to })}
            label="Datum bis"
          />
        </div>
      )}
    </div>
  );
}
