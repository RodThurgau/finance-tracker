import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  addTagToTransaction,
  bulkUpdateTransactions,
  listTransactions,
  removeTagFromTransaction,
  updateTransaction,
} from '../api/transactions.js';
import { useCategoryIndex } from '../hooks/useLookups.js';
import { BulkBar } from '../components/BulkBar.jsx';
import { FilterBar } from '../components/FilterBar.jsx';
import { PageHeader } from '../components/PageHeader.jsx';
import { Pagination } from '../components/Pagination.jsx';
import { RuleDialog } from '../components/RuleDialog.jsx';
import { TransactionsTable } from '../components/TransactionsTable.jsx';

// Filters live in the URL rather than in component state: it makes the view
// linkable, survives a reload, and is what later steps need when the overview
// charts and the tags page navigate here pre-filtered.
const DEFAULT_FILTERS = {
  category_id: '',
  // No FilterBar control sets this (yet) — it exists here so a link built
  // elsewhere, e.g. the Übersicht page's "Nicht kategorisiert" pie slice,
  // is actually honored instead of silently dropped.
  uncategorized: '',
  untagged: '',
  source: '',
  date_from: '',
  date_to: '',
  search: '',
  excluded: '',
  // '' means "hide", matching the backend default — PayPal funding legs are
  // duplicates of money already counted, so they stay out unless asked for.
  internal: '',
  sort_by: 'date',
  sort_dir: 'desc',
  page: '1',
  page_size: '50',
};

export function Transactions() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const categoryIndex = useCategoryIndex();

  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [rulePrompt, setRulePrompt] = useState(null);

  const filters = useMemo(() => {
    const values = { ...DEFAULT_FILTERS };
    for (const key of Object.keys(DEFAULT_FILTERS)) {
      const value = searchParams.get(key);
      if (value !== null) values[key] = value;
    }
    // tag_id is repeatable — ?tag_id=1&tag_id=2 means "either tag".
    values.tag_id = searchParams.getAll('tag_id');
    return values;
  }, [searchParams]);

  const setFilter = useCallback(
    (patch) => {
      setSearchParams((previous) => {
        const next = new URLSearchParams(previous);
        for (const [key, value] of Object.entries(patch)) {
          if (Array.isArray(value)) {
            next.delete(key);
            for (const item of value) next.append(key, String(item));
          } else if (value === '' || value === null || value === undefined) {
            next.delete(key);
          } else {
            next.set(key, String(value));
          }
        }
        // Any filter change invalidates the current page number — page 3 of the
        // old result set is meaningless in the new one.
        if (!('page' in patch)) next.delete('page');
        return next;
      });
    },
    [setSearchParams],
  );

  // A new page or filter means the old selection refers to rows that are no
  // longer on screen, and a bulk action would silently hit them.
  const searchKey = searchParams.toString();
  useEffect(() => {
    setSelectedIds(new Set());
  }, [searchKey]);

  const query = useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => listTransactions(filters),
    placeholderData: keepPreviousData,
  });

  const transactions = query.data?.items ?? [];
  const total = query.data?.total ?? 0;

  const invalidateTransactions = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['transactions'] });
    // Category assignment moves the per-category transaction counts.
    queryClient.invalidateQueries({ queryKey: ['categories'] });
  }, [queryClient]);

  const updateMutation = useMutation({
    mutationFn: ({ id, patch }) => updateTransaction(id, patch),
    onSuccess: invalidateTransactions,
  });

  const tagMutation = useMutation({
    mutationFn: ({ transaction, tag, isAssigned }) =>
      isAssigned
        ? removeTagFromTransaction(transaction.id, tag.id)
        : addTagToTransaction(transaction.id, tag.id),
    onSuccess: () => {
      invalidateTransactions();
      queryClient.invalidateQueries({ queryKey: ['tags'] });
    },
  });

  const bulkMutation = useMutation({
    mutationFn: (body) => bulkUpdateTransactions(body),
    onSuccess: () => {
      invalidateTransactions();
      setSelectedIds(new Set());
    },
  });

  function handleRecategorize(transaction, patch) {
    updateMutation.mutate(
      { id: transaction.id, patch },
      {
        onSuccess: () => {
          // Offer a rule only when a category was actually assigned — clearing
          // one has nothing to generalize from.
          if (patch.category_id !== null) {
            setRulePrompt({ transaction, ...patch });
          }
        },
      },
    );
  }

  function toggleSelect(id) {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll(select) {
    setSelectedIds(select ? new Set(transactions.map((transaction) => transaction.id)) : new Set());
  }

  function handleSort(column) {
    const sortDir =
      filters.sort_by === column && filters.sort_dir === 'desc' ? 'asc' : 'desc';
    setFilter({ sort_by: column, sort_dir: sortDir });
  }

  const isBusy = updateMutation.isPending || tagMutation.isPending || bulkMutation.isPending;
  const mutationError = updateMutation.error ?? tagMutation.error ?? bulkMutation.error;

  return (
    <>
      <PageHeader
        title="Transaktionen"
        description={
          query.isFetching ? 'Wird geladen …' : `${total} Buchungen im aktuellen Filter.`
        }
      />

      <FilterBar
        filters={filters}
        onChange={setFilter}
        onReset={() => setSearchParams(new URLSearchParams())}
      />

      {query.isError && (
        <p className="mb-4 rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
          Transaktionen konnten nicht geladen werden: {query.error.message}
        </p>
      )}
      {mutationError && (
        <p className="mb-4 rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
          Änderung fehlgeschlagen: {mutationError.message}
        </p>
      )}

      {query.isPending ? (
        <p className="text-sm text-content-muted">Wird geladen …</p>
      ) : transactions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line p-10 text-center text-sm text-content-muted">
          Keine Transaktionen gefunden.
        </div>
      ) : (
        <>
          <TransactionsTable
            transactions={transactions}
            categoryIndex={categoryIndex}
            sortBy={filters.sort_by}
            sortDir={filters.sort_dir}
            onSort={handleSort}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelect}
            onToggleAll={toggleAll}
            onRecategorize={handleRecategorize}
            onToggleTag={(transaction, tag, isAssigned) =>
              tagMutation.mutate({ transaction, tag, isAssigned })
            }
            onToggleExclude={(transaction) =>
              updateMutation.mutate({
                id: transaction.id,
                patch: { exclude_from_stats: !transaction.exclude_from_stats },
              })
            }
          />

          <Pagination
            page={Number(filters.page)}
            pageSize={Number(filters.page_size)}
            total={total}
            onChange={setFilter}
          />
        </>
      )}

      {selectedIds.size > 0 && (
        <BulkBar
          count={selectedIds.size}
          isPending={isBusy}
          onClear={() => setSelectedIds(new Set())}
          onRecategorize={(patch) => bulkMutation.mutate({ ids: [...selectedIds], ...patch })}
          onSetExcluded={(value) =>
            bulkMutation.mutate({ ids: [...selectedIds], exclude_from_stats: value })
          }
        />
      )}

      {rulePrompt && (
        <RuleDialog
          transaction={rulePrompt.transaction}
          categoryId={rulePrompt.category_id}
          subcategoryId={rulePrompt.subcategory_id}
          categoryName={categoryIndex.byId.get(rulePrompt.category_id)?.name ?? ''}
          onClose={() => setRulePrompt(null)}
        />
      )}
    </>
  );
}
