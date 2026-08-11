/**
 * Display formatting for values that arrive from the API as strings.
 *
 * Amounts are never converted to `Number` here. `Intl.NumberFormat.prototype
 * .format` accepts a decimal string and formats it exactly, so the value the
 * backend computed is the value shown. No arithmetic happens on this side.
 */

const currencyFormatters = new Map();

function currencyFormatter(currency) {
  let formatter = currencyFormatters.get(currency);
  if (!formatter) {
    formatter = new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    currencyFormatters.set(currency, formatter);
  }
  return formatter;
}

/**
 * Format an amount string from the API, e.g. `"-1234.56"` → `"-1.234,56 €"`.
 * Returns an em dash for missing values so table cells never render "NaN".
 */
export function formatAmount(amount, currency = 'EUR') {
  if (amount === null || amount === undefined || amount === '') return '—';
  return currencyFormatter(currency).format(amount);
}

/** True when the amount string represents an expense (a leading minus sign). */
export function isNegativeAmount(amount) {
  return typeof amount === 'string' && amount.trimStart().startsWith('-');
}

/**
 * Format an ISO date (`"2024-03-05"`) as `"2024.03.05"`.
 *
 * Done as string surgery rather than via `Date`, which would drag a timezone
 * into a value that has none and can shift the day.
 */
export function formatDate(isoDate) {
  if (!isoDate) return '—';
  return String(isoDate).slice(0, 10).replaceAll('-', '.');
}

/** Format an ISO date for a date *input*, which shows German `DD.MM.YYYY`. */
export function formatDateInput(isoDate) {
  if (!isoDate) return '';
  const [year, month, day] = String(isoDate).slice(0, 10).split('-');
  if (!year || !month || !day) return '';
  return `${day}.${month}.${year}`;
}

const pad = (value) => String(value).padStart(2, '0');

/**
 * Parse German date entry back to an ISO string for the API.
 *
 * Accepts `31.12.2024`, `31/12/2024`, `31-12-2024`, `31.12.24` and a bare
 * `31122024`. Returns `''` for empty input (meaning "no filter") and `null`
 * when the text is not a real date, which the caller treats as "reject".
 */
export function parseDateInput(text) {
  const trimmed = text.trim();
  if (!trimmed) return '';

  let day;
  let month;
  let year;

  const digits = trimmed.replace(/\D/g, '');
  if (digits.length === 8 && digits === trimmed) {
    [day, month, year] = [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4)];
  } else {
    const parts = trimmed.split(/[./\-\s]+/).filter(Boolean);
    if (parts.length !== 3) return null;
    [day, month, year] = parts;
    if (year.length === 2) year = `20${year}`;
  }

  const dayNumber = Number(day);
  const monthNumber = Number(month);
  const yearNumber = Number(year);
  if (![dayNumber, monthNumber, yearNumber].every(Number.isInteger)) return null;
  if (yearNumber < 1900 || yearNumber > 2999) return null;

  const iso = `${yearNumber}-${pad(monthNumber)}-${pad(dayNumber)}`;
  // Round-trip through UTC so "31.02.2024" is rejected rather than rolling
  // over into March, and so no local timezone can shift the day.
  const probe = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(probe.getTime())) return null;
  if (probe.getUTCFullYear() !== yearNumber) return null;
  if (probe.getUTCMonth() + 1 !== monthNumber) return null;
  if (probe.getUTCDate() !== dayNumber) return null;
  return iso;
}

/** Format a plain integer count, e.g. transaction counts in the sidebar. */
export function formatCount(value) {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('de-DE').format(value);
}
