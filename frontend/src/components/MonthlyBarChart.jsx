import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { formatMonth } from '../lib/dateRanges.js';
import { formatAmount } from '../lib/format.js';

const compactAmount = new Intl.NumberFormat('de-DE', { notation: 'compact', maximumFractionDigits: 1 });
const SERIES_LABEL = { income: 'Einnahmen', expenses: 'Ausgaben' };
const SERIES_COLOR = { income: 'var(--color-positive)', expenses: 'var(--color-negative)' };
// Left-to-right drawing order within each month. The legend and tooltip follow
// it so the ordering reads the same in all three places.
const SERIES_ORDER = ['income', 'expenses'];

function SeriesLegend() {
  return (
    <ul className="flex items-center justify-center gap-4 text-xs text-content-muted">
      {SERIES_ORDER.map((key) => (
        <li key={key} className="flex items-center gap-1.5">
          <span
            className="size-2 rounded-full"
            style={{ backgroundColor: SERIES_COLOR[key] }}
            aria-hidden="true"
          />
          {SERIES_LABEL[key]}
        </li>
      ))}
    </ul>
  );
}

/**
 * Monthly income vs. expenses, side by side — two bars per month off a shared
 * baseline, which is what makes their heights directly comparable. `data` is
 * `/stats/summary`'s `by_month`.
 *
 * Expenses arrive negative and are plotted as magnitude so both bars grow
 * upward; the tooltip restores the real sign, so nothing claims an expense is
 * a positive amount.
 *
 * The green/red pair is not far enough apart under red-green color blindness
 * to carry identity by itself, so two other channels do it: the order within
 * each month is fixed (income left, expenses right, matching the legend), and
 * the tooltip names the series. That is also why the two bars keep a 2px gap
 * rather than touching — adjacent fills need the surface showing between them.
 */
export function MonthlyBarChart({ data }) {
  // Recharts plots numeric geometry, not ledger values — the exact decimal
  // strings ride along per row for the tooltip, which is what actually
  // displays an amount to the user.
  const rows = data.map((entry) => ({
    month: entry.month,
    income: Number(entry.income),
    expenses: Math.abs(Number(entry.expenses)),
    incomeExact: entry.income,
    expensesExact: entry.expenses,
  }));

  if (rows.length === 0) {
    return (
      <p className="flex h-72 items-center justify-center text-sm text-content-muted">
        Keine Buchungen im gewählten Zeitraum.
      </p>
    );
  }

  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} barCategoryGap="25%" barGap={2}>
          <CartesianGrid vertical={false} stroke="var(--color-line)" />
          <XAxis
            dataKey="month"
            tickFormatter={formatMonth}
            tick={{ fill: 'var(--color-content-muted)', fontSize: 12 }}
            axisLine={{ stroke: 'var(--color-line)' }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(value) => compactAmount.format(value)}
            tick={{ fill: 'var(--color-content-muted)', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip
            labelFormatter={formatMonth}
            itemSorter={(item) => SERIES_ORDER.indexOf(item.dataKey)}
            formatter={(_value, name, item) => [
              formatAmount(name === 'income' ? item.payload.incomeExact : item.payload.expensesExact),
              SERIES_LABEL[name],
            ]}
            contentStyle={{
              background: 'var(--color-surface-raised)',
              border: '1px solid var(--color-line)',
              borderRadius: 8,
              fontSize: 13,
            }}
            labelStyle={{ color: 'var(--color-content)' }}
            itemStyle={{ color: 'var(--color-content)' }}
          />
          {/* Drawn by hand rather than from the <Bar>s' own payload, which
              Recharts emits in an order it picks itself (it came out reversed).
              The legend order *is* the fallback identity channel here — see the
              component docstring — so it has to match the drawing order, not
              merely list the same two series. */}
          <Legend content={<SeriesLegend />} />
          {SERIES_ORDER.map((key) => (
            <Bar
              key={key}
              dataKey={key}
              name={key}
              fill={SERIES_COLOR[key]}
              maxBarSize={24}
              radius={[4, 4, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
