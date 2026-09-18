import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, Pencil, X } from 'lucide-react';

import { createMerchantMapping } from '../api/merchants.js';
import { formatAmount } from '../lib/format.js';

function MerchantRow({ entry, index, maxAmount }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (displayName) =>
      createMerchantMapping({ raw_name: entry.counter_account, display_name: displayName }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stats-summary'] });
      setEditing(false);
    },
  });

  const share = maxAmount > 0 ? (Math.abs(Number(entry.total)) / maxAmount) * 100 : 0;

  const startEditing = () => {
    setDraft(entry.display_name);
    setEditing(true);
  };

  const submit = () => {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== entry.counter_account) {
      mutation.mutate(trimmed);
    } else {
      setEditing(false);
    }
  };

  return (
    <li className="group relative overflow-hidden rounded-lg">
      <div
        className="absolute inset-y-0 left-0 bg-accent/10"
        style={{ width: `${share}%` }}
        aria-hidden="true"
      />
      <div className="relative flex items-center gap-3 px-3 py-2 text-sm">
        <span className="w-5 shrink-0 text-content-muted">{index + 1}.</span>
        {editing ? (
          <form
            className="flex flex-1 items-center gap-1"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="flex-1 rounded border border-line bg-surface px-2 py-0.5 text-sm text-content outline-none focus:border-accent"
              autoFocus
              onKeyDown={(e) => e.key === 'Escape' && setEditing(false)}
            />
            <button
              type="submit"
              className="rounded p-0.5 text-positive hover:bg-surface-hover"
              title="Speichern"
            >
              <Check size={14} />
            </button>
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="rounded p-0.5 text-content-muted hover:bg-surface-hover"
              title="Abbrechen"
            >
              <X size={14} />
            </button>
          </form>
        ) : (
          <>
            <span className="flex-1 truncate" title={entry.counter_account}>
              {entry.display_name}
            </span>
            <button
              type="button"
              onClick={startEditing}
              className="rounded p-0.5 text-content-muted opacity-0 transition-opacity hover:bg-surface-hover hover:text-content group-hover:opacity-100"
              title="Händlername bearbeiten"
            >
              <Pencil size={14} />
            </button>
          </>
        )}
        <span className="tabular font-medium text-negative">{formatAmount(entry.total)}</span>
      </div>
    </li>
  );
}

export function TopMerchants({ data }) {
  if (data.length === 0) {
    return <p className="text-sm text-content-muted">Keine Ausgaben im gewählten Zeitraum.</p>;
  }

  const maxAmount = Math.max(...data.map((entry) => Math.abs(Number(entry.total))));

  return (
    <ul className="space-y-1">
      {data.map((entry, index) => (
        <MerchantRow
          key={entry.counter_account}
          entry={entry}
          index={index}
          maxAmount={maxAmount}
        />
      ))}
    </ul>
  );
}
