/**
 * The result grid.
 *
 * Values are rendered as SQLite returned them, with no unit guessing: `amount`
 * arrives as integer cents and is shown as `-1250`, not `-12,50 €`. A query can
 * select, sum or divide anything, so a column named `amount` is not reliably
 * money — the schema panel says what the raw column holds, and the formatting
 * this app does trust lives on the Transaktionen page.
 */
export function SqlResultTable({ result }) {
  if (result.columns.length === 0) {
    return <p className="px-4 py-6 text-sm text-content-muted">Die Abfrage liefert keine Spalten.</p>;
  }

  return (
    <div className="max-h-[28rem] overflow-auto">
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 bg-surface-raised">
          <tr>
            <th className="border-b border-line px-3 py-2 text-right font-mono text-xs text-content-muted">
              #
            </th>
            {result.columns.map((column, index) => (
              <th
                // Two columns may share a name (`SELECT a.id, b.id`), so the
                // position is the only unique key here.
                key={`${column}-${index}`}
                className="whitespace-nowrap border-b border-line px-3 py-2 text-left font-medium"
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="hover:bg-surface-hover">
              <td className="border-b border-line px-3 py-1.5 text-right font-mono text-xs text-content-muted tabular">
                {rowIndex + 1}
              </td>
              {row.map((value, columnIndex) => (
                <td
                  key={columnIndex}
                  className={`max-w-md truncate border-b border-line px-3 py-1.5 ${
                    typeof value === 'number' ? 'text-right tabular' : ''
                  }`}
                  title={value === null ? 'NULL' : String(value)}
                >
                  {value === null ? (
                    <span className="text-content-muted italic">NULL</span>
                  ) : (
                    String(value)
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {result.rows.length === 0 && (
        <p className="px-3 py-6 text-center text-sm text-content-muted">Keine Zeilen.</p>
      )}
    </div>
  );
}
