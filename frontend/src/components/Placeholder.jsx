/** Stand-in for a page that is scaffolded but not yet built out. */
export function Placeholder({ step, children }) {
  return (
    <div className="rounded-xl border border-dashed border-line bg-surface-raised p-8 text-center">
      <p className="text-sm text-content-muted">{children}</p>
      {step && <p className="mt-2 text-xs text-content-muted/70">Schritt {step}</p>}
    </div>
  );
}
