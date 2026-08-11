export function ChartCard({ title, children }) {
  return (
    <div className="rounded-xl border border-line bg-surface-raised p-4">
      <h3 className="mb-3 text-sm font-semibold text-content">{title}</h3>
      {children}
    </div>
  );
}
