import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';

import { TransactionRow } from './TransactionRow.jsx';

const HEAD = 'px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-content-muted';

function SortHeader({ column, label, sortBy, sortDir, onSort, className = '' }) {
  const isActive = sortBy === column;
  const Icon = !isActive ? ArrowUpDown : sortDir === 'asc' ? ArrowUp : ArrowDown;
  return (
    <th scope="col" className={`${HEAD} ${className}`}>
      <button
        type="button"
        onClick={() => onSort(column)}
        className={`inline-flex items-center gap-1 hover:text-content ${
          isActive ? 'text-content' : ''
        }`}
      >
        {label}
        <Icon size={12} />
      </button>
    </th>
  );
}

export function TransactionsTable({
  transactions,
  categoryIndex,
  sortBy,
  sortDir,
  onSort,
  selectedIds,
  onToggleSelect,
  onToggleAll,
  onRecategorize,
  onToggleTag,
  onToggleExclude,
}) {
  const allSelected =
    transactions.length > 0 && transactions.every((transaction) => selectedIds.has(transaction.id));

  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full min-w-[62rem] text-sm">
        <thead className="bg-surface-raised">
          <tr>
            <th scope="col" className={HEAD}>
              <input
                type="checkbox"
                checked={allSelected}
                onChange={() => onToggleAll(!allSelected)}
                aria-label="Alle auf dieser Seite auswählen"
                className="size-4 accent-[var(--color-accent)]"
              />
            </th>
            <SortHeader
              column="date"
              label="Datum"
              sortBy={sortBy}
              sortDir={sortDir}
              onSort={onSort}
            />
            <SortHeader
              column="description"
              label="Beschreibung"
              sortBy={sortBy}
              sortDir={sortDir}
              onSort={onSort}
            />
            <th scope="col" className={HEAD}>
              Kategorie
            </th>
            <th scope="col" className={HEAD}>
              Tags
            </th>
            <th scope="col" className={HEAD}>
              Quelle
            </th>
            <SortHeader
              column="amount"
              label="Betrag"
              sortBy={sortBy}
              sortDir={sortDir}
              onSort={onSort}
              className="text-right [&>button]:justify-end"
            />
            <th scope="col" className={HEAD}>
              <span className="sr-only">Statistik</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((transaction) => (
            <TransactionRow
              key={transaction.id}
              transaction={transaction}
              categoryIndex={categoryIndex}
              isSelected={selectedIds.has(transaction.id)}
              onToggleSelect={onToggleSelect}
              onRecategorize={onRecategorize}
              onToggleTag={onToggleTag}
              onToggleExclude={onToggleExclude}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
