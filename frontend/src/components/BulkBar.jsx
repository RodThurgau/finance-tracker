import { Eye, EyeOff, Tag as TagIcon, X } from 'lucide-react';

import { CategoryMenu } from './CategoryMenu.jsx';
import { Popover } from './Popover.jsx';

const ACTION =
  'flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm text-content-muted hover:bg-surface-hover hover:text-content disabled:opacity-50';

/** Action bar for the current checkbox selection. Hidden when nothing is selected. */
export function BulkBar({ count, onClear, onRecategorize, onSetExcluded, isPending }) {
  return (
    <div className="sticky bottom-4 z-20 mt-4 flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface-raised p-3 shadow-lg shadow-black/40">
      <span className="text-sm font-medium">{count} ausgewählt</span>

      <Popover
        align="left"
        renderTrigger={({ toggle }) => (
          <button type="button" className={ACTION} onClick={toggle} disabled={isPending}>
            <TagIcon size={14} />
            Kategorie zuweisen
          </button>
        )}
      >
        {({ close }) => (
          <CategoryMenu
            onSelect={(patch) => {
              close();
              onRecategorize(patch);
            }}
          />
        )}
      </Popover>

      <button
        type="button"
        className={ACTION}
        disabled={isPending}
        onClick={() => onSetExcluded(true)}
      >
        <EyeOff size={14} />
        Von Statistik ausschließen
      </button>
      <button
        type="button"
        className={ACTION}
        disabled={isPending}
        onClick={() => onSetExcluded(false)}
      >
        <Eye size={14} />
        Wieder einbeziehen
      </button>

      <button
        type="button"
        onClick={onClear}
        className="ml-auto flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
      >
        <X size={14} />
        Auswahl aufheben
      </button>
    </div>
  );
}
