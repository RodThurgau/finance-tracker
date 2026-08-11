/**
 * Color picker for categories and tags.
 *
 * Presets first — they are the palette the seed data already uses, so a
 * hand-made category sits next to the defaults without clashing. The native
 * `<input type="color">` alongside covers anything else; unlike
 * `<input type="date">` (see DateField), it has no locale-dependent rendering
 * to work around.
 */
const PRESETS = [
  '#38bdf8',
  '#fb923c',
  '#a78bfa',
  '#f472b6',
  '#4ade80',
  '#facc15',
  '#60a5fa',
  '#34d399',
  '#22d3ee',
  '#c084fc',
  '#fbbf24',
  '#818cf8',
  '#94a3b8',
];

export function ColorPicker({ value, onChange, label = 'Farbe' }) {
  return (
    <div>
      <span className="text-sm font-medium">{label}</span>
      <div className="mt-1 flex flex-wrap items-center gap-1.5">
        {PRESETS.map((preset) => (
          <button
            key={preset}
            type="button"
            onClick={() => onChange(preset)}
            aria-label={`Farbe ${preset}`}
            aria-pressed={value?.toLowerCase() === preset}
            className={`size-6 rounded-full border transition-transform ${
              value?.toLowerCase() === preset
                ? 'scale-110 border-content'
                : 'border-line hover:scale-105'
            }`}
            style={{ backgroundColor: preset }}
          />
        ))}
        <input
          type="color"
          value={value || '#94a3b8'}
          onChange={(event) => onChange(event.target.value)}
          aria-label="Eigene Farbe"
          className="size-6 cursor-pointer rounded-full border border-line bg-transparent p-0"
        />
      </div>
    </div>
  );
}
