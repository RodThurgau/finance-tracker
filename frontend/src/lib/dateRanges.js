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

/** ISO `{ from, to }` bounds of a calendar year, `yearsAgo` years before the
 *  current one (0 = this year, 1 = last year). */
export function calendarYearRange(yearsAgo = 0) {
  const year = new Date().getFullYear() - yearsAgo;
  return { from: `${year}-01-01`, to: `${year}-12-31` };
}

/**
 * ISO `{ from, to }` bounds of the last `count` calendar months, **including
 * the current one** — `lastMonthsRange(3)` in August covers 1 June to 31
 * August, not the three completed months before August.
 */
export function lastMonthsRange(count) {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth() - (count - 1), 1);
  const last = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return { from: toIso(first), to: toIso(last) };
}

/** Format a `"YYYY-MM"` bucket (as returned by `/stats/summary`'s `by_month`)
 *  as `"MM.JJJJ"`, matching the app's big-endian date convention. */
export function formatMonth(yearMonth) {
  const [year, month] = yearMonth.split('-');
  return `${month}.${year}`;
}
