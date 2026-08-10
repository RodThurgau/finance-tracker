import { Eye, EyeOff, Plus } from 'lucide-react';

import { CategoryPill, SourceBadge, TagChip } from './Pills.jsx';
import { CategoryMenu } from './CategoryMenu.jsx';
import { TagMenu } from './TagMenu.jsx';
import { Popover } from './Popover.jsx';
import { formatAmount, formatDate, isNegativeAmount } from '../lib/format.js';

const CELL = 'px-3 py-2 align-top';

export function TransactionRow({
  transaction,
  isSelected,
  onToggleSelect,
  categoryIndex,
  onRecategorize,
  onToggleTag,
  onToggleExclude,
}) {
  const category = transaction.category_id ? categoryIndex.byId.get(transaction.category_id) : null;
  const subcategory = transaction.subcategory_id
    ? categoryIndex.subcategoryById.get(transaction.subcategory_id)
    : null;
  const assignedTagIds = new Set(transaction.tags.map((tag) => tag.id));
  const excluded = transaction.exclude_from_stats;

  return (
    <tr
      className={`border-t border-line hover:bg-surface-raised/60 ${excluded ? 'opacity-50' : ''}`}
    >
      <td className={CELL}>
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onToggleSelect(transaction.id)}
          aria-label={`Transaktion ${transaction.id} auswählen`}
          className="size-4 accent-[var(--color-accent)]"
        />
      </td>

      <td className={`${CELL} tabular whitespace-nowrap text-content-muted`}>
        {formatDate(transaction.date)}
      </td>

      <td className={`${CELL} max-w-md`}>
        <div className="truncate" title={transaction.description}>
          {transaction.description}
        </div>
        {transaction.transaction_type && (
          <div className="truncate text-xs text-content-muted">{transaction.transaction_type}</div>
        )}
      </td>

      <td className={CELL}>
        <Popover
          renderTrigger={({ toggle }) => (
            <button type="button" onClick={toggle} className="cursor-pointer">
              {category ? (
                <CategoryPill name={category.name} color={category.color} />
              ) : (
                <CategoryPill name="Nicht zugeordnet" muted />
              )}
            </button>
          )}
        >
          {({ close }) => (
            <CategoryMenu
              categoryId={transaction.category_id}
              subcategoryId={transaction.subcategory_id}
              onSelect={(patch) => {
                close();
                onRecategorize(transaction, patch);
              }}
            />
          )}
        </Popover>
        {subcategory && (
          <div className="mt-1 truncate text-xs text-content-muted">{subcategory.name}</div>
        )}
      </td>

      <td className={CELL}>
        <div className="flex flex-wrap items-center gap-1">
          {transaction.tags.map((tag) => (
            <TagChip
              key={tag.id}
              name={tag.name}
              color={tag.color}
              onRemove={() => onToggleTag(transaction, tag, true)}
            />
          ))}
          <Popover
            renderTrigger={({ toggle }) => (
              <button
                type="button"
                onClick={toggle}
                aria-label="Tag hinzufügen"
                className="rounded-full border border-dashed border-line p-1 text-content-muted hover:text-content"
              >
                <Plus size={12} />
              </button>
            )}
          >
            {() => (
              <TagMenu
                assignedIds={assignedTagIds}
                onToggle={(tag, isAssigned) => onToggleTag(transaction, tag, isAssigned)}
              />
            )}
          </Popover>
        </div>
      </td>

      <td className={CELL}>
        <SourceBadge source={transaction.source} />
      </td>

      <td
        className={`${CELL} tabular whitespace-nowrap text-right font-medium ${
          isNegativeAmount(transaction.amount) ? 'text-negative' : 'text-positive'
        }`}
      >
        {formatAmount(transaction.amount, transaction.currency)}
      </td>

      <td className={CELL}>
        <button
          type="button"
          onClick={() => onToggleExclude(transaction)}
          title={excluded ? 'Wieder in Statistik einbeziehen' : 'Von Statistik ausschließen'}
          aria-label={excluded ? 'Wieder in Statistik einbeziehen' : 'Von Statistik ausschließen'}
          className="rounded-md p-1 text-content-muted hover:bg-surface-hover hover:text-content"
        >
          {excluded ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </td>
    </tr>
  );
}
