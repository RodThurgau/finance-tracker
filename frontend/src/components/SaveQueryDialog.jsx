import { useEffect, useState } from 'react';

/**
 * Name-and-folder prompt for storing the query in the active tab.
 *
 * The folder is free text with the existing names offered as suggestions:
 * folders are derived from what the saved queries carry, so typing a new name
 * is how one gets created, and there is nothing to create up front.
 */
export function SaveQueryDialog({
  initialName = '',
  initialFolder = '',
  folders = [],
  isPending = false,
  error = null,
  onSave,
  onCancel,
}) {
  const [name, setName] = useState(initialName);
  const [folder, setFolder] = useState(initialFolder);

  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === 'Escape') onCancel();
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onCancel]);

  const field =
    'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-content placeholder:text-content-muted';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (name.trim()) onSave(name.trim(), folder.trim());
        }}
        className="w-full max-w-md rounded-xl border border-line bg-surface-raised p-5 shadow-xl shadow-black/50"
      >
        <h2 className="text-lg font-semibold">Abfrage speichern</h2>

        <label className="mt-4 block text-sm text-content-muted" htmlFor="saved-query-name">
          Name
        </label>
        <input
          id="saved-query-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="z. B. Ausgaben pro Monat"
          autoFocus
          className={`${field} mt-1`}
        />

        <label className="mt-3 block text-sm text-content-muted" htmlFor="saved-query-folder">
          Ordner <span className="text-xs">(optional)</span>
        </label>
        <input
          id="saved-query-folder"
          list="saved-query-folders"
          value={folder}
          onChange={(event) => setFolder(event.target.value)}
          placeholder="Ohne Ordner"
          className={`${field} mt-1`}
        />
        <datalist id="saved-query-folders">
          {folders.map((existing) => (
            <option key={existing} value={existing} />
          ))}
        </datalist>

        {error && <p className="mt-3 text-sm text-negative">{error.message}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg px-3 py-2 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
          >
            Abbrechen
          </button>
          <button
            type="submit"
            disabled={!name.trim() || isPending}
            className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-surface disabled:opacity-50"
          >
            {isPending ? 'Wird gespeichert …' : 'Speichern'}
          </button>
        </div>
      </form>
    </div>
  );
}
