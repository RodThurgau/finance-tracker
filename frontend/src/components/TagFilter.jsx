import { ChevronDown } from 'lucide-react';

import { useTags } from '../hooks/useLookups.js';
import { Popover } from './Popover.jsx';
import { formatCount } from '../lib/format.js';

/**
 * Multi-select tag filter.
 *
 * Selecting several tags is OR: a row qualifies if it carries any of them.
 * "Ohne Tags" is a different question — rows with no tags at all — so it is
 * mutually exclusive with a tag selection; picking one clears the other.
 * Nothing selected means no tag filter.
 */
export function TagFilter({ selectedIds, untagged, onChange }) {
  const { data: tags } = useTags();
  const selected = new Set(selectedIds.map(String));
  const isUntagged = untagged === 'true';

  let label = 'Alle Tags';
  if (isUntagged) {
    label = 'Ohne Tags';
  } else if (selected.size === 1) {
    const [only] = [...selected];
    label = tags?.find((tag) => String(tag.id) === only)?.name ?? '1 Tag';
  } else if (selected.size > 1) {
    label = `${selected.size} Tags`;
  }

  function toggleTag(id) {
    const next = new Set(selected);
    const key = String(id);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange({ tag_id: [...next], untagged: '' });
  }

  const isFiltering = isUntagged || selected.size > 0;

  return (
    <Popover
      renderTrigger={({ toggle }) => (
        <button
          type="button"
          onClick={toggle}
          className={`flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-sm ${
            isFiltering ? 'text-content' : 'text-content-muted'
          }`}
        >
          {label}
          <ChevronDown size={14} />
        </button>
      )}
    >
      {() => (
        <div className="w-64 p-1">
          <button
            type="button"
            onClick={() => onChange({ tag_id: [], untagged: isUntagged ? '' : 'true' })}
            className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-surface-hover ${
              isUntagged ? 'text-content' : 'text-content-muted'
            }`}
          >
            <input
              type="checkbox"
              checked={isUntagged}
              readOnly
              tabIndex={-1}
              className="size-3.5 accent-[var(--color-accent)]"
            />
            Ohne Tags
          </button>

          <div className="my-1 border-t border-line" />

          {(tags ?? []).length === 0 && (
            <p className="px-2 py-1.5 text-sm text-content-muted">Keine Tags vorhanden.</p>
          )}

          {(tags ?? []).map((tag) => (
            <button
              key={tag.id}
              type="button"
              onClick={() => toggleTag(tag.id)}
              className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-surface-hover ${
                selected.has(String(tag.id)) ? 'text-content' : 'text-content-muted'
              }`}
            >
              <input
                type="checkbox"
                checked={selected.has(String(tag.id))}
                readOnly
                tabIndex={-1}
                className="size-3.5 accent-[var(--color-accent)]"
              />
              <span
                className="size-2.5 shrink-0 rounded-full border border-line"
                style={tag.color ? { backgroundColor: tag.color } : undefined}
              />
              <span className="flex-1 truncate">{tag.name}</span>
              <span className="tabular text-xs text-content-muted">
                {formatCount(tag.usage_count)}
              </span>
            </button>
          ))}

          {isFiltering && (
            <>
              <div className="my-1 border-t border-line" />
              <button
                type="button"
                onClick={() => onChange({ tag_id: [], untagged: '' })}
                className="w-full rounded-md px-2 py-1.5 text-left text-sm text-content-muted hover:bg-surface-hover hover:text-content"
              >
                Auswahl aufheben
              </button>
            </>
          )}
        </div>
      )}
    </Popover>
  );
}
