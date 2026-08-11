/**
 * Percent change from `previous` to `current`, both `/stats/summary` decimal
 * strings, for a stat-tile delta indicator. Unlike the amounts themselves,
 * this value is never summed, stored, or exported — it only drives a rounded
 * "+12.3%" label and an up/down arrow — so parsing through `Number` here
 * doesn't touch the precision guarantees CLAUDE.md cares about for ledger data.
 *
 * `goodWhenUp` sets the up/down → good/bad mapping (spending more is bad, so
 * the expenses tile passes `false`). `useAbsolute` compares magnitudes rather
 * than signed values — expenses arrive as negative amounts, and "trend" there
 * means "spent more", not "amount moved toward positive".
 *
 * Returns `null` when there's no prior-period baseline to compare against.
 */
export function computeTrend(current, previous, { goodWhenUp = true, useAbsolute = false } = {}) {
  let currentValue = Number(current);
  let previousValue = Number(previous);
  if (useAbsolute) {
    currentValue = Math.abs(currentValue);
    previousValue = Math.abs(previousValue);
  }
  if (previousValue === 0) return null;

  const percent = ((currentValue - previousValue) / Math.abs(previousValue)) * 100;
  const isUp = percent > 0;
  return { percent, isUp, isGood: goodWhenUp ? isUp : !isUp };
}
