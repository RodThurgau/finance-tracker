import { Check } from 'lucide-react';

import { useTags } from '../hooks/useLookups.js';

/**
 * Toggle list of every tag, ticked where the transaction already carries it.
 * Creating tags happens on the Tags page (4.3), not here.
 */
export function TagMenu({ assignedIds, onToggle }) {
  const { data: tags, isPending } = useTags();

  if (isPending) {
    return <p className="w-56 px-3 py-2 text-sm text-content-muted">Wird geladen …</p>;
  }
  if (!tags?.length) {
    return <p className="w-56 px-3 py-2 text-sm text-content-muted">Keine Tags vorhanden.</p>;
  }

  return (
    <div className="w-56 p-1">
      {tags.map((tag) => {
        const isAssigned = assignedIds.has(tag.id);
        return (
          <button
            key={tag.id}
            type="button"
            onClick={() => onToggle(tag, isAssigned)}
            className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-surface-hover ${
              isAssigned ? 'text-content' : 'text-content-muted'
            }`}
          >
            <span
              className="size-2.5 shrink-0 rounded-full border border-line"
              style={tag.color ? { backgroundColor: tag.color } : undefined}
            />
            <span className="flex-1 truncate">{tag.name}</span>
            {isAssigned && <Check size={14} />}
          </button>
        );
      })}
    </div>
  );
}
