import { useEffect, useState } from 'react';

import { formatDateInput, parseDateInput } from '../lib/format.js';

/**
 * German date entry, `TT.MM.JJJJ`.
 *
 * Deliberately not `<input type="date">`: that control renders in the
 * *browser's* locale (an en-US browser shows `mm/dd/yyyy`) and the page has no
 * way to override it — not via `lang`, not via CSS. A text field is the only
 * way to guarantee the format.
 *
 * The draft text is committed on blur or Enter. Unparseable text snaps back to
 * the last valid value instead of clearing the filter out from under the user.
 */
export function DateField({ value, onChange, label, className = '' }) {
  const [draft, setDraft] = useState(() => formatDateInput(value));
  const [isInvalid, setInvalid] = useState(false);

  // Follow changes that came from elsewhere (filter reset, or a URL with dates).
  useEffect(() => {
    setDraft(formatDateInput(value));
    setInvalid(false);
  }, [value]);

  function commit() {
    const parsed = parseDateInput(draft);
    if (parsed === null) {
      setDraft(formatDateInput(value));
      setInvalid(true);
      return;
    }
    setInvalid(false);
    if (parsed !== value) onChange(parsed);
  }

  return (
    <input
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === 'Enter') commit();
        if (event.key === 'Escape') setDraft(formatDateInput(value));
      }}
      inputMode="numeric"
      placeholder="TT.MM.JJJJ"
      aria-label={label}
      aria-invalid={isInvalid || undefined}
      className={`w-36 rounded-lg border bg-surface px-3 py-2 text-sm text-content placeholder:text-content-muted ${
        isInvalid ? 'border-negative' : 'border-line'
      } ${className}`}
    />
  );
}
