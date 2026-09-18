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

const EMPTY_MONTH = { income: '0.00', expenses: '0.00', net: '0.00', transaction_count: 0 };

/**
 * Insert empty months into a `/stats/trend` series wherever the backend left a
 * gap.
 *
 * Months with no matching transaction are omitted server-side, which on a chart
 * would put January next to March as if they were neighbors — the flat stretch
 * where nothing happened is exactly what a trend is supposed to show. Filling
 * happens strictly *between* the first and last point present: padding out to
 * the edges of the selected range would draw months the account may not even
 * have existed in.
 *
 * The inserted months carry amount **strings** like the real ones, so nothing
 * downstream has to care which is which.
 */
export function fillMonthGaps(points) {
  if (points.length < 2) return points;

  const filled = [];
  for (const point of points) {
    const previous = filled.at(-1);
    if (previous) {
      let [year, month] = previous.month.split('-').map(Number);
      for (;;) {
        month += 1;
        if (month > 12) {
          month = 1;
          year += 1;
        }
        const key = `${year}-${String(month).padStart(2, '0')}`;
        if (key >= point.month) break;
        filled.push({ month: key, ...EMPTY_MONTH });
      }
    }
    filled.push(point);
  }
  return filled;
}
