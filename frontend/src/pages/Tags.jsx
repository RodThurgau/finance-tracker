import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Pencil, Plus, Trash2 } from 'lucide-react';

import { createTag, deleteTag, updateTag } from '../api/tags.js';
import { useTags } from '../hooks/useLookups.js';
import { ColorPicker } from '../components/ColorPicker.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { PageHeader } from '../components/PageHeader.jsx';
import { formatCount } from '../lib/format.js';

const FIELD = 'rounded-lg border border-line bg-surface px-3 py-2 text-sm text-content placeholder:text-content-muted';
const ICON_BUTTON = 'rounded-md p-1.5 text-content-muted hover:bg-surface-hover hover:text-content';
const DEFAULT_COLOR = '#22d3ee';

export function Tags() {
  const queryClient = useQueryClient();
  const { data: tags, isPending, isError, error } = useTags();

  const [isCreating, setCreating] = useState(false);
  const [draft, setDraft] = useState({ name: '', color: DEFAULT_COLOR });
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState({ name: '', color: DEFAULT_COLOR });
  const [confirming, setConfirming] = useState(null);

  function invalidate({ transactionsToo = false } = {}) {
    queryClient.invalidateQueries({ queryKey: ['tags'] });
    // A tag's name and color are rendered on every transaction row that
    // carries it, and deleting one detaches it from those rows.
    if (transactionsToo) queryClient.invalidateQueries({ queryKey: ['transactions'] });
  }

  const createMutation = useMutation({
    mutationFn: () => createTag({ name: draft.name.trim(), color: draft.color }),
    onSuccess: () => {
      invalidate();
      setDraft({ name: '', color: DEFAULT_COLOR });
      setCreating(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (id) => updateTag(id, { name: editDraft.name.trim(), color: editDraft.color }),
    onSuccess: () => {
      invalidate({ transactionsToo: true });
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => deleteTag(id),
    onSuccess: () => {
      invalidate({ transactionsToo: true });
      setConfirming(null);
    },
  });

  function startEdit(tag) {
    setEditingId(tag.id);
    setEditDraft({ name: tag.name, color: tag.color ?? DEFAULT_COLOR });
    setCreating(false);
  }

  return (
    <>
      <PageHeader
        title="Tags"
        description="Tags anlegen, umbenennen und löschen."
        actions={
          <button
            type="button"
            onClick={() => {
              setCreating((previous) => !previous);
              setEditingId(null);
            }}
            className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
          >
            <Plus size={14} />
            Neuer Tag
          </button>
        }
      />

      {isCreating && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (draft.name.trim()) createMutation.mutate();
          }}
          className="mb-3 rounded-xl border border-line bg-surface-raised p-4"
        >
          <input
            value={draft.name}
            onChange={(event) => setDraft((previous) => ({ ...previous, name: event.target.value }))}
            placeholder="Name des Tags"
            aria-label="Name des Tags"
            autoFocus
            className={`${FIELD} w-full`}
          />
          <div className="mt-3">
            <ColorPicker
              value={draft.color}
              onChange={(color) => setDraft((previous) => ({ ...previous, color }))}
            />
          </div>
          {createMutation.isError && (
            <p className="mt-3 text-sm text-negative">{createMutation.error.message}</p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setCreating(false)}
              className="rounded-lg px-3 py-2 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
            >
              Abbrechen
            </button>
            <button
              type="submit"
              disabled={!draft.name.trim() || createMutation.isPending}
              className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-surface disabled:opacity-50"
            >
              {createMutation.isPending ? 'Wird angelegt …' : 'Anlegen'}
            </button>
          </div>
        </form>
      )}

      {isPending && <p className="text-sm text-content-muted">Wird geladen …</p>}
      {isError && (
        <p className="rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
          Tags konnten nicht geladen werden: {error.message}
        </p>
      )}

      {tags &&
        (tags.length === 0 ? (
          <div className="rounded-xl border border-dashed border-line p-10 text-center text-sm text-content-muted">
            Noch keine Tags angelegt.
          </div>
        ) : (
          <ul className="space-y-2">
            {tags.map((tag) => (
              <li key={tag.id} className="rounded-xl border border-line bg-surface-raised p-4">
                {editingId === tag.id ? (
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (editDraft.name.trim()) updateMutation.mutate(tag.id);
                    }}
                  >
                    <input
                      value={editDraft.name}
                      onChange={(event) =>
                        setEditDraft((previous) => ({ ...previous, name: event.target.value }))
                      }
                      aria-label="Name des Tags"
                      autoFocus
                      className={`${FIELD} w-full`}
                    />
                    <div className="mt-3">
                      <ColorPicker
                        value={editDraft.color}
                        onChange={(color) => setEditDraft((previous) => ({ ...previous, color }))}
                      />
                    </div>
                    {updateMutation.isError && (
                      <p className="mt-3 text-sm text-negative">{updateMutation.error.message}</p>
                    )}
                    <div className="mt-4 flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                        className="rounded-lg px-3 py-2 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
                      >
                        Abbrechen
                      </button>
                      <button
                        type="submit"
                        disabled={!editDraft.name.trim() || updateMutation.isPending}
                        className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-surface disabled:opacity-50"
                      >
                        Speichern
                      </button>
                    </div>
                  </form>
                ) : (
                  <div className="flex items-center gap-2">
                    <Link
                      to={`/transaktionen?tag_id=${tag.id}`}
                      title={`Transaktionen mit „${tag.name}“ anzeigen`}
                      className="flex flex-1 items-center gap-2 truncate hover:underline"
                    >
                      <span
                        className="size-3 shrink-0 rounded-full border border-line"
                        style={tag.color ? { backgroundColor: tag.color } : undefined}
                      />
                      <span className="font-medium">{tag.name}</span>
                    </Link>
                    <span className="tabular text-xs text-content-muted">
                      {formatCount(tag.usage_count)}{' '}
                      {tag.usage_count === 1 ? 'Transaktion' : 'Transaktionen'}
                    </span>
                    <button
                      type="button"
                      onClick={() => startEdit(tag)}
                      title="Umbenennen / Farbe ändern"
                      aria-label={`${tag.name} bearbeiten`}
                      className={ICON_BUTTON}
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirming(tag)}
                      title="Löschen"
                      aria-label={`${tag.name} löschen`}
                      className={`${ICON_BUTTON} hover:text-negative`}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        ))}

      {confirming && (
        <ConfirmDialog
          title={`„${confirming.name}“ löschen?`}
          description={
            <p>
              Der Tag wird von{' '}
              {confirming.usage_count === 1
                ? 'einer Transaktion'
                : `${formatCount(confirming.usage_count)} Transaktionen`}{' '}
              entfernt. Die Transaktionen selbst bleiben unverändert.
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
    </>
  );
}
