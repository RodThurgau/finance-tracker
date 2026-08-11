import { useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';

/**
 * Modal confirmation for an action that can't be undone from the UI.
 *
 * `description` takes nodes, not just a string, so a caller can spell out the
 * consequences (which transactions change, what happens to their category)
 * rather than asking "Sind Sie sicher?" and leaving the reader to guess.
 */
export function ConfirmDialog({
  title,
  description,
  confirmLabel = 'Bestätigen',
  cancelLabel = 'Abbrechen',
  tone = 'danger',
  isPending = false,
  error = null,
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === 'Escape') onCancel();
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-md rounded-xl border border-line bg-surface-raised p-5 shadow-xl shadow-black/50">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          {tone === 'danger' && <AlertTriangle size={18} className="text-negative" />}
          {title}
        </h2>
        {description && <div className="mt-2 text-sm text-content-muted">{description}</div>}

        {error && (
          <p className="mt-3 rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
            {error.message}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg px-3 py-2 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className={`rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-50 ${
              tone === 'danger' ? 'bg-negative text-surface' : 'bg-accent text-surface'
            }`}
          >
            {isPending ? 'Wird ausgeführt …' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
