import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react';

import { RULE_FIELDS, applyRules, createRule, deleteRule, listRules, updateRule } from '../api/rules.js';
import { useCategories } from '../hooks/useLookups.js';
import { ConfirmDialog } from './ConfirmDialog.jsx';

const FIELD = 'rounded-lg border border-line bg-surface px-3 py-2 text-sm text-content placeholder:text-content-muted';
const ICON_BUTTON = 'rounded-md p-1.5 text-content-muted hover:bg-surface-hover hover:text-content';

const EMPTY_DRAFT = {
  keyword: '',
  field: 'description',
  category_id: '',
  subcategory_id: '',
  priority: '0',
  apply_to_existing: false,
};

const fieldLabel = (value) =>
  RULE_FIELDS.find((option) => option.value === value)?.label ?? value;

/** Shared create/edit form. Editing reuses it minus the backfill checkbox —
 *  `PATCH /rules/{id}` has no `apply_to_existing`; re-running rules over
 *  existing rows is what the "Regeln erneut anwenden" button is for. */
function RuleForm({ draft, setDraft, categories, onSubmit, onCancel, isPending, error, mode }) {
  const selectedCategory = categories.find(
    (category) => String(category.id) === String(draft.category_id),
  );

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (draft.keyword.trim() && draft.category_id) onSubmit();
      }}
      className="rounded-xl border border-line bg-surface-raised p-4"
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <label className="text-sm font-medium lg:col-span-2">
          Schlagwort
          <input
            value={draft.keyword}
            onChange={(event) => setDraft({ ...draft, keyword: event.target.value })}
            placeholder="z. B. REWE"
            className={`${FIELD} mt-1 w-full`}
          />
        </label>

        <label className="text-sm font-medium">
          Feld
          <select
            value={draft.field}
            onChange={(event) => setDraft({ ...draft, field: event.target.value })}
            className={`${FIELD} mt-1 w-full`}
          >
            {RULE_FIELDS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm font-medium">
          Kategorie
          <select
            value={draft.category_id}
            onChange={(event) =>
              setDraft({ ...draft, category_id: event.target.value, subcategory_id: '' })
            }
            className={`${FIELD} mt-1 w-full`}
          >
            <option value="">Bitte wählen</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm font-medium">
          Unterkategorie
          <select
            value={draft.subcategory_id}
            onChange={(event) => setDraft({ ...draft, subcategory_id: event.target.value })}
            disabled={!selectedCategory}
            className={`${FIELD} mt-1 w-full disabled:opacity-50`}
          >
            <option value="">Keine</option>
            {(selectedCategory?.subcategories ?? []).map((subcategory) => (
              <option key={subcategory.id} value={subcategory.id}>
                {subcategory.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-4">
        <label className="text-sm font-medium">
          Priorität
          <input
            type="number"
            value={draft.priority}
            onChange={(event) => setDraft({ ...draft, priority: event.target.value })}
            className={`${FIELD} mt-1 w-24`}
          />
          <span className="mt-1 block text-xs font-normal text-content-muted">
            Höher wird zuerst geprüft
          </span>
        </label>

        {mode === 'create' && (
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={draft.apply_to_existing}
              onChange={(event) => setDraft({ ...draft, apply_to_existing: event.target.checked })}
              className="mt-0.5 size-4 accent-[var(--color-accent)]"
            />
            <span>
              Auch auf bestehende Transaktionen anwenden
              <span className="block text-xs text-content-muted">
                Nur Transaktionen ohne Kategorie werden nachträglich zugeordnet.
              </span>
            </span>
          </label>
        )}
      </div>

      {error && <p className="mt-3 text-sm text-negative">{error.message}</p>}

      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg px-3 py-2 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
        >
          Abbrechen
        </button>
        <button
          type="submit"
          disabled={!draft.keyword.trim() || !draft.category_id || isPending}
          className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-surface disabled:opacity-50"
        >
          {isPending ? 'Wird gespeichert …' : 'Speichern'}
        </button>
      </div>
    </form>
  );
}

export function RulesSection() {
  const queryClient = useQueryClient();
  const { data: categories } = useCategories();
  const rules = useQuery({ queryKey: ['rules'], queryFn: listRules });

  const [isCreating, setCreating] = useState(false);
  const [draft, setDraft] = useState(EMPTY_DRAFT);
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState(EMPTY_DRAFT);
  const [confirming, setConfirming] = useState(null);
  const [applyResult, setApplyResult] = useState(null);

  function invalidateRules({ transactionsToo = false } = {}) {
    queryClient.invalidateQueries({ queryKey: ['rules'] });
    if (transactionsToo) {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      queryClient.invalidateQueries({ queryKey: ['stats-summary'] });
    }
  }

  // Empty selects mean "not set" and must reach the API as null, not "".
  function toBody(values) {
    return {
      keyword: values.keyword.trim(),
      field: values.field,
      category_id: Number(values.category_id),
      subcategory_id: values.subcategory_id ? Number(values.subcategory_id) : null,
      priority: Number(values.priority) || 0,
    };
  }

  const createMutation = useMutation({
    mutationFn: () => createRule({ ...toBody(draft), apply_to_existing: draft.apply_to_existing }),
    onSuccess: (created) => {
      invalidateRules({ transactionsToo: created.applied_count > 0 });
      setDraft(EMPTY_DRAFT);
      setCreating(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (id) => updateRule(id, toBody(editDraft)),
    onSuccess: () => {
      invalidateRules();
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => deleteRule(id),
    onSuccess: () => {
      invalidateRules();
      setConfirming(null);
    },
  });

  const applyMutation = useMutation({
    mutationFn: applyRules,
    onSuccess: (result) => {
      invalidateRules({ transactionsToo: true });
      setApplyResult(result);
      setConfirming(null);
    },
  });

  function startEdit(rule) {
    setEditingId(rule.id);
    setEditDraft({
      keyword: rule.keyword,
      field: rule.field ?? 'description',
      category_id: String(rule.category_id),
      subcategory_id: rule.subcategory_id ? String(rule.subcategory_id) : '',
      priority: String(rule.priority),
      apply_to_existing: false,
    });
    setCreating(false);
  }

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Regeln</h2>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setConfirming({ type: 'apply' })}
            className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
          >
            <RefreshCw size={14} />
            Regeln erneut anwenden
          </button>
          <button
            type="button"
            onClick={() => {
              setCreating((previous) => !previous);
              setDraft(EMPTY_DRAFT);
              setEditingId(null);
            }}
            className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
          >
            <Plus size={14} />
            Neue Regel
          </button>
        </div>
      </div>

      {applyResult && (
        <p className="mb-3 flex items-center gap-2 rounded-lg border border-positive/40 bg-positive/10 px-3 py-2 text-sm text-positive">
          <CheckCircle2 size={16} />
          {applyResult.categorized === 0
            ? 'Keine Transaktion passte auf eine Regel.'
            : `${applyResult.categorized} Transaktion${applyResult.categorized === 1 ? '' : 'en'} neu zugeordnet.`}
        </p>
      )}

      {isCreating && (
        <div className="mb-3">
          <RuleForm
            mode="create"
            draft={draft}
            setDraft={setDraft}
            categories={categories ?? []}
            onSubmit={() => createMutation.mutate()}
            onCancel={() => setCreating(false)}
            isPending={createMutation.isPending}
            error={createMutation.error}
          />
        </div>
      )}

      {rules.isPending && <p className="text-sm text-content-muted">Wird geladen …</p>}
      {rules.isError && (
        <p className="rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
          Regeln konnten nicht geladen werden: {rules.error.message}
        </p>
      )}

      {rules.isSuccess &&
        (rules.data.length === 0 ? (
          <div className="rounded-xl border border-dashed border-line p-10 text-center text-sm text-content-muted">
            Noch keine Regeln angelegt.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs font-semibold uppercase tracking-wide text-content-muted">
                  <th className="px-3 py-2">Schlagwort</th>
                  <th className="px-3 py-2">Feld</th>
                  <th className="px-3 py-2">Kategorie</th>
                  <th className="px-3 py-2 text-right">Priorität</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {rules.data.map((rule) =>
                  editingId === rule.id ? (
                    <tr key={rule.id} className="border-t border-line">
                      <td colSpan={5} className="p-3">
                        <RuleForm
                          mode="edit"
                          draft={editDraft}
                          setDraft={setEditDraft}
                          categories={categories ?? []}
                          onSubmit={() => updateMutation.mutate(rule.id)}
                          onCancel={() => setEditingId(null)}
                          isPending={updateMutation.isPending}
                          error={updateMutation.error}
                        />
                      </td>
                    </tr>
                  ) : (
                    <tr key={rule.id} className="border-t border-line">
                      <td className="px-3 py-2 font-medium">{rule.keyword}</td>
                      <td className="px-3 py-2 text-content-muted">{fieldLabel(rule.field)}</td>
                      <td className="px-3 py-2">
                        {rule.category_name}
                        {rule.subcategory_name && (
                          <span className="text-content-muted"> › {rule.subcategory_name}</span>
                        )}
                      </td>
                      <td className="tabular px-3 py-2 text-right text-content-muted">
                        {rule.priority}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => startEdit(rule)}
                            title="Bearbeiten"
                            aria-label={`Regel ${rule.keyword} bearbeiten`}
                            className={ICON_BUTTON}
                          >
                            <Pencil size={16} />
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirming({ type: 'rule', rule })}
                            title="Löschen"
                            aria-label={`Regel ${rule.keyword} löschen`}
                            className={`${ICON_BUTTON} hover:text-negative`}
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        ))}

      {confirming?.type === 'rule' && (
        <ConfirmDialog
          title={`Regel „${confirming.rule.keyword}“ löschen?`}
          description={
            <p>
              Bereits zugeordnete Transaktionen behalten ihre Kategorie — die Regel greift nur
              künftig nicht mehr.
            </p>
          }
          confirmLabel="Löschen"
          isPending={deleteMutation.isPending}
          error={deleteMutation.error}
          onConfirm={() => deleteMutation.mutate(confirming.rule.id)}
          onCancel={() => {
            deleteMutation.reset();
            setConfirming(null);
          }}
        />
      )}

      {confirming?.type === 'apply' && (
        <ConfirmDialog
          title="Regeln erneut anwenden?"
          description={
            <>
              <p>
                Alle Regeln werden erneut auf jede Transaktion angewendet, die nicht manuell
                kategorisiert wurde.
              </p>
              <p className="mt-2">
                Manuell vergebene Kategorien bleiben unangetastet. Automatisch zugeordnete
                Transaktionen können dabei eine andere Kategorie erhalten.
              </p>
            </>
          }
          confirmLabel="Anwenden"
          tone="accent"
          isPending={applyMutation.isPending}
          error={applyMutation.error}
          onConfirm={() => {
            setApplyResult(null);
            applyMutation.mutate();
          }}
          onCancel={() => {
            applyMutation.reset();
            setConfirming(null);
          }}
        />
      )}
    </>
  );
}
