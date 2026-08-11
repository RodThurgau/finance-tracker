const pad = (value) => String(value).padStart(2, '0');

function toIso(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/**
 * ISO `{ from, to }` bounds of a calendar month, `monthsAgo` months before the
 * current one (0 = this month, 1 = last month, …).
 *
 * Built from today's local date, not parsed from an API value, so — unlike
 * `lib/format.js`'s date helpers — using `Date` here doesn't risk shifting a
 * stored day across a timezone boundary.
 */
export function calendarMonthRange(monthsAgo = 0) {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth() - monthsAgo, 1);
  const last = new Date(now.getFullYear(), now.getMonth() - monthsAgo + 1, 0);
  return { from: toIso(first), to: toIso(last) };
}

/** Format a `"YYYY-MM"` bucket (as returned by `/stats/summary`'s `by_month`)
 *  as `"MM.JJJJ"`, matching the app's big-endian date convention. */
export function formatMonth(yearMonth) {
  const [year, month] = yearMonth.split('-');
  return `${month}.${year}`;
}
