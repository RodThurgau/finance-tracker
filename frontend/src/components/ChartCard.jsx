export function ChartCard({ title, hint, children }) {
  return (
    <div className="rounded-xl border border-line bg-surface-raised p-4">
      <h3 className="text-sm font-semibold text-content">{title}</h3>
      {hint && <p className="mt-0.5 text-xs text-content-muted">{hint}</p>}
      <div className="mt-3">{children}</div>
    </div>
  );
}
