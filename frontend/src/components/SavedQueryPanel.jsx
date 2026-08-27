import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronDown, ChevronRight, FolderClosed, Pencil, Play, Trash2 } from 'lucide-react';

import {
  deleteSavedQuery,
  listSavedQueries,
  renameFolder,
  updateSavedQuery,
} from '../api/sql.js';
import { ConfirmDialog } from './ConfirmDialog.jsx';

const ICON_BUTTON = 'rounded p-1 text-content-muted hover:bg-surface-hover hover:text-content';
const FIELD = 'rounded-md border border-line bg-surface px-2 py-1 text-sm text-content';

// The top level is an empty folder name, not a null one — see the SavedQuery
// model. It sorts first and is labelled rather than shown as a blank heading.
const ROOT = '';
const ROOT_LABEL = 'Ohne Ordner';

/** Group the flat list the API returns into `[folder, queries]` pairs. */
function groupByFolder(queries) {
  const folders = new Map();
  for (const query of queries) {
    if (!folders.has(query.folder)) folders.set(query.folder, []);
    folders.get(query.folder).push(query);
  }
  return [...folders.entries()];
}

export function SavedQueryPanel({ onOpen, activeSavedQueryId }) {
  const queryClient = useQueryClient();
  const { data: queries, isPending, isError, error } = useQuery({
    queryKey: ['sql', 'queries'],
    queryFn: listSavedQueries,
  });

  const [collapsed, setCollapsed] = useState(() => new Set());
  const [renamingId, setRenamingId] = useState(null);
  const [renameDraft, setRenameDraft] = useState('');
  const [renamingFolder, setRenamingFolder] = useState(null);
  const [folderDraft, setFolderDraft] = useState('');
  const [confirming, setConfirming] = useState(null);

  const groups = useMemo(() => groupByFolder(queries ?? []), [queries]);

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['sql', 'queries'] });
  }

  const renameMutation = useMutation({
    mutationFn: ({ id, name }) => updateSavedQuery(id, { name }),
    onSuccess: () => {
      invalidate();
      setRenamingId(null);
    },
  });

  const folderMutation = useMutation({
    mutationFn: ({ name, newName }) => renameFolder(name, newName),
    onSuccess: () => {
      invalidate();
      setRenamingFolder(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => deleteSavedQuery(id),
    onSuccess: () => {
      invalidate();
      setConfirming(null);
    },
  });

  function toggleFolder(folder) {
    setCollapsed((previous) => {
      const next = new Set(previous);
      if (next.has(folder)) next.delete(folder);
      else next.add(folder);
      return next;
    });
  }

  return (
    <section className="rounded-xl border border-line bg-surface-raised">
      <h2 className="border-b border-line px-3 py-2 text-xs font-semibold uppercase tracking-wide text-content-muted">
        Gespeicherte Abfragen
      </h2>

      {isPending && <p className="px-3 py-3 text-sm text-content-muted">Wird geladen …</p>}
      {isError && (
        <p className="px-3 py-3 text-sm text-negative">
          Konnten nicht geladen werden: {error.message}
        </p>
      )}

      {queries && queries.length === 0 && (
        <p className="px-3 py-4 text-sm text-content-muted">
          Noch nichts gespeichert. Über „Speichern“ landet die aktuelle Abfrage hier — wahlweise in
          einem selbst benannten Ordner.
        </p>
      )}

      <ul className="py-1">
        {groups.map(([folder, folderQueries]) => (
          <li key={folder || ROOT}>
            <div className="group flex items-center gap-1 px-2 py-1">
              <button
                type="button"
                onClick={() => toggleFolder(folder)}
                className="flex min-w-0 flex-1 items-center gap-1.5 rounded px-1 py-1 text-left text-sm text-content-muted hover:bg-surface-hover hover:text-content"
              >
                {collapsed.has(folder) ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                {folder !== ROOT && <FolderClosed size={14} />}
                <span className={`truncate ${folder === ROOT ? 'italic' : 'font-medium'}`}>
                  {folder === ROOT ? ROOT_LABEL : folder}
                </span>
                <span className="tabular text-xs">{folderQueries.length}</span>
              </button>
              {folder !== ROOT && (
                <button
                  type="button"
                  onClick={() => {
                    setRenamingFolder(folder);
                    setFolderDraft(folder);
                  }}
                  title="Ordner umbenennen"
                  aria-label={`Ordner ${folder} umbenennen`}
                  className={`${ICON_BUTTON} opacity-0 group-hover:opacity-100`}
                >
                  <Pencil size={13} />
                </button>
              )}
            </div>

            {renamingFolder === folder && (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  const newName = folderDraft.trim();
                  if (newName && newName !== folder) {
                    folderMutation.mutate({ name: folder, newName });
                  } else {
                    setRenamingFolder(null);
                  }
                }}
                className="px-3 pb-2"
              >
                <input
                  value={folderDraft}
                  onChange={(event) => setFolderDraft(event.target.value)}
                  aria-label="Neuer Ordnername"
                  autoFocus
                  onBlur={() => setRenamingFolder(null)}
                  className={`${FIELD} w-full`}
                />
                <p className="mt-1 text-xs text-content-muted">
                  Ein bestehender Name führt die Ordner zusammen.
                </p>
                {folderMutation.isError && (
                  <p className="mt-1 text-xs text-negative">{folderMutation.error.message}</p>
                )}
              </form>
            )}

            {!collapsed.has(folder) && (
              <ul>
                {folderQueries.map((query) => (
                  <li key={query.id} className="group flex items-center gap-1 pl-6 pr-2">
                    {renamingId === query.id ? (
                      <form
                        onSubmit={(event) => {
                          event.preventDefault();
                          const name = renameDraft.trim();
                          if (name) renameMutation.mutate({ id: query.id, name });
                        }}
                        className="flex-1 py-1"
                      >
                        <input
                          value={renameDraft}
                          onChange={(event) => setRenameDraft(event.target.value)}
                          aria-label="Neuer Name"
                          autoFocus
                          className={`${FIELD} w-full`}
                        />
                        {renameMutation.isError && (
                          <p className="mt-1 text-xs text-negative">{renameMutation.error.message}</p>
                        )}
                      </form>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={() => onOpen(query)}
                          title={query.sql}
                          className={`flex min-w-0 flex-1 items-center gap-1.5 rounded px-1 py-1 text-left text-sm hover:bg-surface-hover ${
                            activeSavedQueryId === query.id ? 'text-accent' : 'text-content'
                          }`}
                        >
                          <Play size={12} className="shrink-0 text-content-muted" />
                          <span className="truncate">{query.name}</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setRenamingId(query.id);
                            setRenameDraft(query.name);
                          }}
                          title="Umbenennen"
                          aria-label={`${query.name} umbenennen`}
                          className={`${ICON_BUTTON} opacity-0 group-hover:opacity-100`}
                        >
                          <Pencil size={13} />
                        </button>
                        <button
                          type="button"
                          onClick={() => setConfirming(query)}
                          title="Löschen"
                          aria-label={`${query.name} löschen`}
                          className={`${ICON_BUTTON} opacity-0 group-hover:opacity-100 hover:text-negative`}
                        >
                          <Trash2 size={13} />
                        </button>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>

      {confirming && (
        <ConfirmDialog
          title={`„${confirming.name}“ löschen?`}
          description={
            <p>
              Die gespeicherte Abfrage wird entfernt. Bereits geöffnete Tabs behalten ihren Text —
              gelöscht wird nur der Eintrag in dieser Liste.
            </p>
          }
          confirmLabel="Löschen"
          isPending={deleteMutation.isPending}
          error={deleteMutation.error}
          onConfirm={() => deleteMutation.mutate(confirming.id)}
          onCancel={() => {
            deleteMutation.reset();
            setConfirming(null);
          }}
        />
      )}
    </section>
  );
}
