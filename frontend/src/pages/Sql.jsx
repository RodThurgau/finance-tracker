import { useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Play, Plus, Save, X } from 'lucide-react';

import { createSavedQuery, executeSql, listSavedQueries, updateSavedQuery } from '../api/sql.js';
import { PageHeader } from '../components/PageHeader.jsx';
import { SaveQueryDialog } from '../components/SaveQueryDialog.jsx';
import { SavedQueryPanel } from '../components/SavedQueryPanel.jsx';
import { SqlResultTable } from '../components/SqlResultTable.jsx';
import { SqlSchemaPanel } from '../components/SqlSchemaPanel.jsx';
import { formatCount } from '../lib/format.js';

const ROW_LIMITS = [100, 500, 1000, 5000, 10000];
const DEFAULT_LIMIT = 500;

// Shown in the first tab so the page is not a blank box, and because the cents
// trap is easier to explain by example than in a paragraph.
const STARTER_SQL = `-- Beträge liegen als Cent-Integer in der Datenbank (siehe Schema).
SELECT c.name AS kategorie,
       SUM(t.amount) / 100.0 AS euro,
       COUNT(*) AS anzahl
FROM transactions t
LEFT JOIN categories c ON c.id = t.category_id
WHERE t.exclude_from_stats = 0
GROUP BY c.name
ORDER BY euro`;

function newTab(number, overrides = {}) {
  return {
    id: `tab-${number}-${Date.now()}`,
    title: `Abfrage ${number}`,
    sql: '',
    savedQueryId: null,
    savedSql: null,
    result: null,
    error: null,
    isRunning: false,
    limit: DEFAULT_LIMIT,
    ...overrides,
  };
}

/**
 * Ad-hoc SQL against the local database.
 *
 * Tabs are in-memory only. Reloading the page loses them, which is the intended
 * split: an unsaved tab is scratch work, and anything worth keeping goes into
 * the saved-query list on the left. Storing tabs in the browser is not an
 * option — no browser-side storage, per CLAUDE.md.
 */
export function Sql() {
  const queryClient = useQueryClient();
  const counter = useRef(1);
  const editorRef = useRef(null);

  const [tabs, setTabs] = useState(() => [newTab(1, { sql: STARTER_SQL })]);
  const [activeId, setActiveId] = useState(() => tabs[0].id);
  const [isSaveDialogOpen, setSaveDialogOpen] = useState(false);

  // Falls back to the first tab so a stale id — after closing the active tab —
  // can never leave the editor without a tab to render.
  const activeTab = tabs.find((tab) => tab.id === activeId) ?? tabs[0];

  const { data: savedQueries } = useQuery({
    queryKey: ['sql', 'queries'],
    queryFn: listSavedQueries,
  });

  const folders = useMemo(
    () => [...new Set((savedQueries ?? []).map((query) => query.folder).filter(Boolean))].sort(),
    [savedQueries],
  );

  function patchTab(id, changes) {
    setTabs((previous) =>
      previous.map((tab) => (tab.id === id ? { ...tab, ...changes } : tab)),
    );
  }

  async function run(tab) {
    if (!tab.sql.trim() || tab.isRunning) return;
    patchTab(tab.id, { isRunning: true, error: null });
    try {
      const result = await executeSql(tab.sql, tab.limit);
      patchTab(tab.id, { result, error: null, isRunning: false });
    } catch (error) {
      // The backend's `detail` is the whole message — a refused statement and a
      // SQL syntax error both come back as a 400 with the reason spelled out.
      patchTab(tab.id, { error, isRunning: false });
    }
  }

  function openTab(overrides) {
    counter.current += 1;
    const tab = newTab(counter.current, overrides);
    setTabs((previous) => [...previous, tab]);
    setActiveId(tab.id);
    return tab;
  }

  function closeTab(id) {
    const remaining = tabs.filter((tab) => tab.id !== id);

    // Closing the last tab opens an empty one rather than leaving the editor
    // with nothing to type into.
    if (remaining.length === 0) {
      counter.current += 1;
      const fresh = newTab(counter.current);
      setTabs([fresh]);
      setActiveId(fresh.id);
      return;
    }

    setTabs(remaining);
    if (id === activeTab.id) setActiveId(remaining[remaining.length - 1].id);
  }

  function openSavedQuery(query) {
    const existing = tabs.find((tab) => tab.savedQueryId === query.id);
    if (existing) {
      setActiveId(existing.id);
      return;
    }
    openTab({
      title: query.name,
      sql: query.sql,
      savedQueryId: query.id,
      savedSql: query.sql,
    });
  }

  function insertAtCursor(text) {
    const textarea = editorRef.current;
    const tab = activeTab;
    if (!textarea) {
      patchTab(tab.id, { sql: `${tab.sql}${text}` });
      return;
    }
    const { selectionStart, selectionEnd } = textarea;
    const next = `${tab.sql.slice(0, selectionStart)}${text}${tab.sql.slice(selectionEnd)}`;
    patchTab(tab.id, { sql: next });
    // Put the caret after what was just inserted, once React has re-rendered.
    requestAnimationFrame(() => {
      textarea.focus();
      const caret = selectionStart + text.length;
      textarea.setSelectionRange(caret, caret);
    });
  }

  const saveMutation = useMutation({
    mutationFn: ({ id, name, folder, sql }) =>
      id ? updateSavedQuery(id, { sql }) : createSavedQuery({ name, folder, sql }),
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['sql', 'queries'] });
      patchTab(activeTab.id, {
        savedQueryId: saved.id,
        savedSql: saved.sql,
        title: saved.name,
      });
      setSaveDialogOpen(false);
    },
  });

  const isDirty = activeTab.savedQueryId !== null && activeTab.sql !== activeTab.savedSql;

  return (
    <>
      <PageHeader
        title="SQL"
        description="Lesende Abfragen auf die lokale Datenbank. Schreibende Anweisungen werden abgelehnt."
      />

      <div className="grid gap-4 lg:grid-cols-[17rem_minmax(0,1fr)]">
        <div className="space-y-4">
          <SavedQueryPanel onOpen={openSavedQuery} activeSavedQueryId={activeTab.savedQueryId} />
          <SqlSchemaPanel onInsert={insertAtCursor} />
        </div>

        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1 border-b border-line pb-2">
            {tabs.map((tab) => (
              <div
                key={tab.id}
                className={`flex items-center gap-1 rounded-t-lg border border-b-0 px-3 py-1.5 text-sm ${
                  tab.id === activeTab.id
                    ? 'border-line bg-surface-raised text-content'
                    : 'border-transparent text-content-muted hover:bg-surface-hover'
                }`}
              >
                <button type="button" onClick={() => setActiveId(tab.id)} className="max-w-40 truncate">
                  {tab.title}
                  {tab.savedQueryId !== null && tab.sql !== tab.savedSql && ' •'}
                </button>
                <button
                  type="button"
                  onClick={() => closeTab(tab.id)}
                  aria-label={`${tab.title} schließen`}
                  className="rounded p-0.5 text-content-muted hover:text-content"
                >
                  <X size={13} />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => openTab()}
              aria-label="Neue Abfrage"
              title="Neue Abfrage"
              className="rounded-md p-1.5 text-content-muted hover:bg-surface-hover hover:text-content"
            >
              <Plus size={16} />
            </button>
          </div>

          <textarea
            ref={editorRef}
            value={activeTab.sql}
            onChange={(event) => patchTab(activeTab.id, { sql: event.target.value })}
            onKeyDown={(event) => {
              if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                event.preventDefault();
                run(activeTab);
              }
            }}
            spellCheck={false}
            aria-label="SQL-Abfrage"
            placeholder="SELECT * FROM transactions LIMIT 10"
            className="mt-3 h-56 w-full resize-y rounded-xl border border-line bg-surface-raised p-3 font-mono text-sm text-content placeholder:text-content-muted"
          />

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => run(activeTab)}
              disabled={!activeTab.sql.trim() || activeTab.isRunning}
              className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-surface disabled:opacity-50"
            >
              <Play size={14} />
              {activeTab.isRunning ? 'Läuft …' : 'Ausführen'}
            </button>
            <span className="text-xs text-content-muted">Strg + Enter</span>

            <label className="ml-auto flex items-center gap-2 text-xs text-content-muted">
              Zeilenlimit
              <select
                value={activeTab.limit}
                onChange={(event) =>
                  patchTab(activeTab.id, { limit: Number(event.target.value) })
                }
                className="rounded-lg border border-line bg-surface px-2 py-1.5 text-sm text-content"
              >
                {ROW_LIMITS.map((limit) => (
                  <option key={limit} value={limit}>
                    {formatCount(limit)}
                  </option>
                ))}
              </select>
            </label>

            {activeTab.savedQueryId !== null && (
              <button
                type="button"
                onClick={() =>
                  saveMutation.mutate({ id: activeTab.savedQueryId, sql: activeTab.sql })
                }
                disabled={!isDirty || saveMutation.isPending}
                className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-sm text-content-muted hover:bg-surface-hover hover:text-content disabled:opacity-50"
              >
                <Save size={14} />
                Speichern
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                saveMutation.reset();
                setSaveDialogOpen(true);
              }}
              disabled={!activeTab.sql.trim()}
              className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-sm text-content-muted hover:bg-surface-hover hover:text-content disabled:opacity-50"
            >
              <Save size={14} />
              {activeTab.savedQueryId === null ? 'Speichern' : 'Als neu speichern'}
            </button>
          </div>

          {saveMutation.isError && !isSaveDialogOpen && (
            <p className="mt-3 rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
              Speichern fehlgeschlagen: {saveMutation.error.message}
            </p>
          )}

          {activeTab.error && (
            <p className="mt-3 whitespace-pre-wrap rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 font-mono text-sm text-negative">
              {activeTab.error.message}
            </p>
          )}

          {activeTab.result && (
            <section className="mt-3 rounded-xl border border-line bg-surface-raised">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line px-3 py-2 text-xs text-content-muted">
                <span className="tabular">
                  {formatCount(activeTab.result.row_count)}{' '}
                  {activeTab.result.row_count === 1 ? 'Zeile' : 'Zeilen'}
                </span>
                <span className="tabular">{formatCount(activeTab.result.elapsed_ms)} ms</span>
                {activeTab.result.truncated && (
                  <span className="text-accent">
                    Nur die ersten {formatCount(activeTab.limit)} Zeilen — Limit erhöhen oder die
                    Abfrage eingrenzen.
                  </span>
                )}
              </div>
              <SqlResultTable result={activeTab.result} />
            </section>
          )}
        </div>
      </div>

      {isSaveDialogOpen && (
        <SaveQueryDialog
          initialName={activeTab.savedQueryId === null ? activeTab.title : `${activeTab.title} (Kopie)`}
          folders={folders}
          isPending={saveMutation.isPending}
          error={saveMutation.error}
          onSave={(name, folder) =>
            saveMutation.mutate({ id: null, name, folder, sql: activeTab.sql })
          }
          onCancel={() => setSaveDialogOpen(false)}
        />
      )}
    </>
  );
}
