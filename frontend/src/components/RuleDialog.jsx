import { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { RULE_FIELDS, createRule } from '../api/rules.js';

/**
 * Suggest the keyword for a new rule from the transaction the user just
 * recategorized.
 *
 * For `description` the useful part is the counterparty, which ING puts before
 * the em dash the parser inserts (`"Empfänger — Verwendungszweck"`). PayPal
 * descriptions have no dash, so the whole name is used.
 */
function suggestKeyword(transaction, field) {
  if (field !== 'description') return (transaction[field] ?? '').trim();
  const description = (transaction.description ?? '').trim();
  const [head] = description.split(' — ');
  return (head || description).slice(0, 60).trim();
}

/**
 * "Als Regel speichern?" — offered after a manual recategorization.
 *
 * Saving only creates the rule. Existing transactions are deliberately left
 * alone; re-running rules over history is an explicit action on the categories
 * page (4.2).
 */
export function RuleDialog({ transaction, categoryId, subcategoryId, categoryName, onClose }) {
  const [field, setField] = useState('description');
  const [keyword, setKeyword] = useState(() => suggestKeyword(transaction, 'description'));

  // Each field implies a different keyword, so re-suggest when it changes.
  useEffect(() => {
    setKeyword(suggestKeyword(transaction, field));
  }, [transaction, field]);

  const mutation = useMutation({
    mutationFn: () =>
      createRule({
        keyword: keyword.trim(),
        field,
        category_id: categoryId,
        subcategory_id: subcategoryId,
        priority: 0,
      }),
    onSuccess: onClose,
  });

  function onSubmit(event) {
    event.preventDefault();
    if (!keyword.trim()) return;
    mutation.mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md rounded-xl border border-line bg-surface-raised p-5 shadow-xl shadow-black/50"
      >
        <h2 className="text-lg font-semibold">Als Regel speichern?</h2>
        <p className="mt-1 text-sm text-content-muted">
          Künftige Transaktionen mit diesem Schlagwort werden automatisch „{categoryName}“
          zugeordnet. Bestehende Transaktionen bleiben unverändert.
        </p>

        <label className="mt-4 block text-sm font-medium">
          Feld
          <select
            value={field}
            onChange={(event) => setField(event.target.value)}
            className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm"
          >
            {RULE_FIELDS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="mt-3 block text-sm font-medium">
          Schlagwort
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm"
            placeholder="z. B. REWE"
          />
        </label>

        {mutation.isError && (
          <p className="mt-3 text-sm text-negative">
            Regel konnte nicht gespeichert werden: {mutation.error.message}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-2 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
          >
            Nicht speichern
          </button>
          <button
            type="submit"
            disabled={!keyword.trim() || mutation.isPending}
            className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-surface disabled:opacity-50"
          >
            {mutation.isPending ? 'Wird gespeichert …' : 'Regel speichern'}
          </button>
        </div>
      </form>
    </div>
  );
}
