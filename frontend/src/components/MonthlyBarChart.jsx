import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { formatMonth } from '../lib/dateRanges.js';
import { formatAmount } from '../lib/format.js';

const compactAmount = new Intl.NumberFormat('de-DE', { notation: 'compact', maximumFractionDigits: 1 });
const SERIES_LABEL = { income: 'Einnahmen', expenses: 'Ausgaben' };

/** Monthly income vs. expenses, stacked around a zero baseline. `data` is
 *  `/stats/summary`'s `by_month`: income positive, expenses negative, so
 *  stacking the two under one `stackId` draws income above the line and
 *  expenses below it — position, not just color, carries which is which. */
export function MonthlyBarChart({ data }) {
  // Recharts plots numeric geometry, not ledger values — the exact decimal
  // strings ride along per row for the tooltip, which is what actually
  // displays an amount to the user.
  const rows = data.map((entry) => ({
    month: entry.month,
    income: Number(entry.income),
    expenses: Number(entry.expenses),
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
        <BarChart data={rows} barCategoryGap="20%">
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
          <ReferenceLine y={0} stroke="var(--color-line)" />
          <Tooltip
            labelFormatter={formatMonth}
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
          <Legend
            formatter={(value) => SERIES_LABEL[value]}
            wrapperStyle={{ fontSize: 12, color: 'var(--color-content-muted)' }}
            iconType="circle"
            iconSize={8}
          />
          <Bar
            dataKey="income"
            name="income"
            stackId="total"
            fill="var(--color-positive)"
            barSize={24}
            radius={[4, 4, 0, 0]}
          />
          <Bar
            dataKey="expenses"
            name="expenses"
            stackId="total"
            fill="var(--color-negative)"
            barSize={24}
            radius={[0, 0, 4, 4]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
