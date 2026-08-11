import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2 } from 'lucide-react';

import { RULE_FIELDS, createRule } from '../api/rules.js';

/**
 * Suggest the keyword for a new rule from the transaction the user just
 * recategorized.
 *
 * For `description` the useful part is the counterparty, which ING puts before
 * the em dash the parser inserts (`"Empfänger — Verwendungszweck"`). PayPal
 * descriptions have no dash, so the whole name is used. It's a starting point,
 * not a final answer — the field below is always editable (e.g. narrowing
 * "VISA REWE HAMBURG HORN" down to just "VISA REWE" to catch other branches).
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
 * Optionally backfills existing rows too (`apply_to_existing`), but only ones
 * with no category at all — a row that already carries a category, even one a
 * different rule assigned automatically, is left untouched. That scope is
 * enforced server-side (services/categorizer.py `apply_rule_to_uncategorized`),
 * not just suggested by the checkbox label.
 */
export function RuleDialog({ transaction, categoryId, subcategoryId, categoryName, onClose }) {
  const queryClient = useQueryClient();
  const [field, setField] = useState('description');
  const [keyword, setKeyword] = useState(() => suggestKeyword(transaction, 'description'));
  const [applyToExisting, setApplyToExisting] = useState(true);
  const [result, setResult] = useState(null);

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
        apply_to_existing: applyToExisting,
      }),
    onSuccess: (created) => {
      if (created.applied_count > 0) {
        queryClient.invalidateQueries({ queryKey: ['transactions'] });
        queryClient.invalidateQueries({ queryKey: ['categories'] });
      }
      // Show the backfill count rather than closing immediately — silently
      // closing would hide whether anything historical actually changed.
      setResult(created);
    },
  });

  function onSubmit(event) {
    event.preventDefault();
    if (!keyword.trim()) return;
    mutation.mutate();
  }

  if (result) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
        <div className="w-full max-w-md rounded-xl border border-line bg-surface-raised p-5 shadow-xl shadow-black/50">
          <p className="flex items-center gap-2 text-sm font-medium text-positive">
            <CheckCircle2 size={18} />
            Regel gespeichert
          </p>
          <p className="mt-2 text-sm text-content-muted">
            {applyToExisting
              ? result.applied_count > 0
                ? `${result.applied_count} bestehende Transaktion${result.applied_count === 1 ? '' : 'en'} ohne Kategorie wurde${result.applied_count === 1 ? '' : 'n'} „${categoryName}“ zugeordnet.`
                : 'Keine bestehende Transaktion ohne Kategorie passte zu diesem Schlagwort.'
              : 'Bestehende Transaktionen wurden nicht verändert.'}
          </p>
          <div className="mt-5 flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-surface"
            >
              Fertig
            </button>
          </div>
        </div>
      </div>
    );
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
          zugeordnet.
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

        <label className="mt-4 flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={applyToExisting}
            onChange={(event) => setApplyToExisting(event.target.checked)}
            className="mt-0.5 size-4 accent-[var(--color-accent)]"
          />
          <span>
            Auch auf bestehende Transaktionen anwenden
            <span className="block text-xs text-content-muted">
              Nur Transaktionen ohne Kategorie werden nachträglich zugeordnet — eine bereits
              vergebene Kategorie bleibt unangetastet.
            </span>
          </span>
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
