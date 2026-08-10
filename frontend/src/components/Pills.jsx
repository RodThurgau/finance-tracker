const HEX_COLOR = /^#[0-9a-f]{6}$/i;

/**
 * Tint a pill from a category's or tag's stored hex color. Colors are free text
 * in the database, so anything that isn't a 6-digit hex falls back to the
 * theme's neutral styling instead of producing broken CSS.
 */
export function swatchStyle(color) {
  if (!color || !HEX_COLOR.test(color)) return null;
  return { color, backgroundColor: `${color}22`, borderColor: `${color}55` };
}

const PILL_BASE =
  'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap';

export function CategoryPill({ name, color, muted = false }) {
  const style = swatchStyle(color);
  return (
    <span
      className={`${PILL_BASE} ${
        style ? '' : muted ? 'border-line text-content-muted' : 'border-line bg-surface-hover text-content'
      }`}
      style={style ?? undefined}
    >
      {name}
    </span>
  );
}

export function TagChip({ name, color, onRemove }) {
  const style = swatchStyle(color);
  return (
    <span
      className={`${PILL_BASE} ${style ? '' : 'border-line bg-surface-hover text-content-muted'}`}
      style={style ?? undefined}
    >
      {name}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Tag ${name} entfernen`}
          className="-mr-0.5 rounded-full px-0.5 leading-none opacity-70 hover:opacity-100"
        >
          ×
        </button>
      )}
    </span>
  );
}

export function SourceBadge({ source }) {
  const tone = source === 'PayPal' ? 'border-accent/40 text-accent' : 'border-line text-content-muted';
  return <span className={`${PILL_BASE} ${tone}`}>{source}</span>;
}
