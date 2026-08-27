import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronRight, Table2 } from 'lucide-react';

import { fetchSchema } from '../api/sql.js';

// The schema only moves when a migration runs, which means a restart.
const SCHEMA_STALE_TIME = 30 * 60 * 1000;

/**
 * Table and column reference next to the editor.
 *
 * Read from the live database rather than hard-coded, so it cannot fall behind
 * a migration. Column notes come from the backend and carry the traps — chiefly
 * that `amount` is stored as integer cents.
 */
export function SqlSchemaPanel({ onInsert }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['sql', 'schema'],
    queryFn: fetchSchema,
    staleTime: SCHEMA_STALE_TIME,
  });

  const [expanded, setExpanded] = useState(() => new Set(['transactions']));

  function toggle(name) {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  return (
    <section className="rounded-xl border border-line bg-surface-raised">
      <h2 className="border-b border-line px-3 py-2 text-xs font-semibold uppercase tracking-wide text-content-muted">
        Schema
      </h2>

      {isPending && <p className="px-3 py-3 text-sm text-content-muted">Wird geladen …</p>}
      {isError && <p className="px-3 py-3 text-sm text-negative">{error.message}</p>}

      <ul className="py-1">
        {data?.tables.map((table) => (
          <li key={table.name}>
            <div className="flex items-center">
              <button
                type="button"
                onClick={() => toggle(table.name)}
                className="flex min-w-0 flex-1 items-center gap-1.5 px-2 py-1 text-left text-sm text-content hover:bg-surface-hover"
              >
                {expanded.has(table.name) ? (
                  <ChevronDown size={14} className="text-content-muted" />
                ) : (
                  <ChevronRight size={14} className="text-content-muted" />
                )}
                <Table2 size={13} className="shrink-0 text-content-muted" />
                <span className="truncate font-mono text-xs">{table.name}</span>
              </button>
              <button
                type="button"
                onClick={() => onInsert(table.name)}
                title="In die Abfrage einfügen"
                aria-label={`${table.name} einfügen`}
                className="px-2 py-1 text-xs text-content-muted hover:text-content"
              >
                +
              </button>
            </div>

            {expanded.has(table.name) && (
              <ul className="pb-1 pl-7 pr-2">
                {table.columns.map((column) => (
                  <li key={column.name} className="py-0.5">
                    <button
                      type="button"
                      onClick={() => onInsert(column.name)}
                      className="w-full text-left"
                      title={`${column.type}${column.nullable ? '' : ' NOT NULL'}`}
                    >
                      <span className="font-mono text-xs text-content">{column.name}</span>{' '}
                      <span className="text-[10px] uppercase text-content-muted">
                        {column.type}
                      </span>
                      {column.note && (
                        <span className="block text-[10px] leading-tight text-accent">
                          {column.note}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
