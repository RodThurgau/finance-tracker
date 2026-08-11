import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react';

import {
  createCategory,
  createSubcategory,
  deleteCategory,
  deleteSubcategory,
  updateCategory,
} from '../api/categories.js';
import { useCategories } from '../hooks/useLookups.js';
import { formatCount } from '../lib/format.js';
import { ColorPicker } from './ColorPicker.jsx';
import { ConfirmDialog } from './ConfirmDialog.jsx';

const FIELD = 'rounded-lg border border-line bg-surface px-3 py-2 text-sm text-content placeholder:text-content-muted';
const ICON_BUTTON = 'rounded-md p-1.5 text-content-muted hover:bg-surface-hover hover:text-content';
const DEFAULT_COLOR = '#94a3b8';

function Swatch({ color }) {
  return (
    <span
      className="size-3 shrink-0 rounded-full border border-line"
      style={color ? { backgroundColor: color } : undefined}
    />
  );
}

export function CategoryManager() {
  const queryClient = useQueryClient();
  const { data: categories, isPending, isError, error } = useCategories();

  const [isCreating, setCreating] = useState(false);
  const [draft, setDraft] = useState({ name: '', color: DEFAULT_COLOR });
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState({ name: '', color: DEFAULT_COLOR });
  const [subcategoryFor, setSubcategoryFor] = useState(null);
  const [subcategoryName, setSubcategoryName] = useState('');
  const [confirming, setConfirming] = useState(null);

  // Category changes move the pills and dropdowns on the transaction list, and
  // a delete rewrites the categorization of every row that carried it.
  function invalidate({ transactionsToo = false } = {}) {
    queryClient.invalidateQueries({ queryKey: ['categories'] });
    if (transactionsToo) {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['stats-summary'] });
      // DELETE /categories/{id} cascades into category_rules.
      queryClient.invalidateQueries({ queryKey: ['rules'] });
    }
  }

  const createMutation = useMutation({
    mutationFn: () => createCategory({ name: draft.name.trim(), color: draft.color }),
    onSuccess: () => {
      invalidate();
      setDraft({ name: '', color: DEFAULT_COLOR });
      setCreating(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (id) => updateCategory(id, { name: editDraft.name.trim(), color: editDraft.color }),
    onSuccess: () => {
      invalidate();
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => deleteCategory(id),
    onSuccess: () => {
      invalidate({ transactionsToo: true });
      setConfirming(null);
    },
  });

  const createSubMutation = useMutation({
    mutationFn: () => createSubcategory(subcategoryFor, { name: subcategoryName.trim() }),
    onSuccess: () => {
      invalidate();
      setSubcategoryName('');
      setSubcategoryFor(null);
    },
  });

  const deleteSubMutation = useMutation({
    mutationFn: (id) => deleteSubcategory(id),
    onSuccess: () => {
      invalidate({ transactionsToo: true });
      setConfirming(null);
    },
  });

  function startEdit(category) {
    setEditingId(category.id);
    setEditDraft({ name: category.name, color: category.color ?? DEFAULT_COLOR });
    setSubcategoryFor(null);
  }

  if (isPending) return <p className="text-sm text-content-muted">Wird geladen …</p>;
  if (isError) {
    return (
      <p className="rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
        Kategorien konnten nicht geladen werden: {error.message}
      </p>
    );
  }

  return (
    <>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Kategorien</h2>
        <button
          type="button"
          onClick={() => setCreating((previous) => !previous)}
          className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
        >
          <Plus size={14} />
          Neue Kategorie
        </button>
      </div>

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
            placeholder="Name der Kategorie"
            aria-label="Name der Kategorie"
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

      {categories.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line p-10 text-center text-sm text-content-muted">
          Noch keine Kategorien angelegt.
        </div>
      ) : (
        <ul className="space-y-2">
          {categories.map((category) => (
            <li key={category.id} className="rounded-xl border border-line bg-surface-raised p-4">
              {editingId === category.id ? (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (editDraft.name.trim()) updateMutation.mutate(category.id);
                  }}
                >
                  <input
                    value={editDraft.name}
                    onChange={(event) =>
                      setEditDraft((previous) => ({ ...previous, name: event.target.value }))
                    }
                    aria-label="Name der Kategorie"
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
                  <Swatch color={category.color} />
                  <span className="font-medium">{category.name}</span>
                  <span className="tabular text-xs text-content-muted">
                    {formatCount(category.transaction_count)}{' '}
                    {category.transaction_count === 1 ? 'Buchung' : 'Buchungen'}
                  </span>
                  <div className="ml-auto flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => {
                        setSubcategoryFor(category.id);
                        setSubcategoryName('');
                        setEditingId(null);
                      }}
                      title="Unterkategorie hinzufügen"
                      aria-label={`Unterkategorie zu ${category.name} hinzufügen`}
                      className={ICON_BUTTON}
                    >
                      <Plus size={16} />
                    </button>
                    <button
                      type="button"
                      onClick={() => startEdit(category)}
                      title="Umbenennen / Farbe ändern"
                      aria-label={`${category.name} bearbeiten`}
                      className={ICON_BUTTON}
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirming({ type: 'category', category })}
                      title="Löschen"
                      aria-label={`${category.name} löschen`}
                      className={`${ICON_BUTTON} hover:text-negative`}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              )}

              {(category.subcategories ?? []).length > 0 && (
                <ul className="mt-2 space-y-1 border-l border-line pl-4">
                  {category.subcategories.map((subcategory) => (
                    <li
                      key={subcategory.id}
                      className="flex items-center gap-2 text-sm text-content-muted"
                    >
                      <span className="flex-1 truncate">{subcategory.name}</span>
                      <button
                        type="button"
                        onClick={() => setConfirming({ type: 'subcategory', subcategory, category })}
                        title="Unterkategorie löschen"
                        aria-label={`${subcategory.name} löschen`}
                        className={`${ICON_BUTTON} hover:text-negative`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              {subcategoryFor === category.id && (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (subcategoryName.trim()) createSubMutation.mutate();
                  }}
                  className="mt-3 flex flex-wrap items-center gap-2 border-l border-line pl-4"
                >
                  <input
                    value={subcategoryName}
                    onChange={(event) => setSubcategoryName(event.target.value)}
                    placeholder="Name der Unterkategorie"
                    aria-label="Name der Unterkategorie"
                    autoFocus
                    className={`${FIELD} flex-1`}
                  />
                  <button
                    type="submit"
                    disabled={!subcategoryName.trim() || createSubMutation.isPending}
                    title="Anlegen"
                    aria-label="Unterkategorie anlegen"
                    className={ICON_BUTTON}
                  >
                    <Check size={16} />
                  </button>
                  <button
                    type="button"
                    onClick={() => setSubcategoryFor(null)}
                    title="Abbrechen"
                    aria-label="Abbrechen"
                    className={ICON_BUTTON}
                  >
                    <X size={16} />
                  </button>
                  {createSubMutation.isError && (
                    <p className="w-full text-sm text-negative">
                      {createSubMutation.error.message}
                    </p>
                  )}
                </form>
              )}
            </li>
          ))}
        </ul>
      )}

      {confirming?.type === 'category' && (
        <ConfirmDialog
          title={`„${confirming.category.name}“ löschen?`}
          description={
            <>
              <p>
                {formatCount(confirming.category.transaction_count)}{' '}
                {confirming.category.transaction_count === 1 ? 'Transaktion' : 'Transaktionen'}{' '}
                {confirming.category.transaction_count === 1 ? 'fällt' : 'fallen'} zurück auf „Nicht
                kategorisiert“ und {confirming.category.transaction_count === 1 ? 'wird' : 'werden'}{' '}
                bei der nächsten automatischen Zuordnung wieder von Regeln erfasst.
              </p>
              <p className="mt-2">
                Unterkategorien und Regeln, die auf diese Kategorie verweisen, werden mitgelöscht.
                Die Transaktionen selbst bleiben erhalten.
              </p>
            </>
          }
          confirmLabel="Löschen"
          isPending={deleteMutation.isPending}
          error={deleteMutation.error}
          onConfirm={() => deleteMutation.mutate(confirming.category.id)}
          onCancel={() => {
            deleteMutation.reset();
            setConfirming(null);
          }}
        />
      )}

      {confirming?.type === 'subcategory' && (
        <ConfirmDialog
          title={`„${confirming.subcategory.name}“ löschen?`}
          description={
            <p>
              Betroffene Transaktionen verlieren nur die Unterkategorie — „
              {confirming.category.name}“ bleibt ihnen erhalten.
            </p>
          }
          confirmLabel="Löschen"
          isPending={deleteSubMutation.isPending}
          error={deleteSubMutation.error}
          onConfirm={() => deleteSubMutation.mutate(confirming.subcategory.id)}
          onCancel={() => {
            deleteSubMutation.reset();
            setConfirming(null);
          }}
        />
      )}
    </>
  );
}
