import { TrendingDown, TrendingUp } from 'lucide-react';

import { formatAmount, isNegativeAmount } from '../lib/format.js';
import { computeTrend } from '../lib/trend.js';

function Trend({ trend }) {
  if (!trend) {
    return <p className="mt-1 text-xs text-content-muted">Kein Vergleich zum Vormonat</p>;
  }
  const Icon = trend.isUp ? TrendingUp : TrendingDown;
  const sign = trend.isUp ? '+' : '';
  return (
    <p
      className={`mt-1 flex items-center gap-1 text-xs font-medium ${
        trend.isGood ? 'text-positive' : 'text-negative'
      }`}
    >
      <Icon size={14} />
      {sign}
      {trend.percent.toFixed(1)} % ggü. Vormonat
    </p>
  );
}

function Card({ label, value, trend }) {
  return (
    <div className="rounded-xl border border-line bg-surface-raised p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">{label}</p>
      <p
        className={`mt-1 text-2xl font-semibold ${
          isNegativeAmount(value) ? 'text-negative' : 'text-positive'
        }`}
      >
        {formatAmount(value)}
      </p>
      <Trend trend={trend} />
    </div>
  );
}

/** The three headline stat tiles: current calendar month vs. the previous
 *  one. `current` and `previous` are `/stats/summary` responses. */
export function SummaryCards({ current, previous }) {
  const cards = [
    {
      label: 'Einnahmen',
      value: current.total_income,
      trend: computeTrend(current.total_income, previous.total_income),
    },
    {
      label: 'Ausgaben',
      value: current.total_expenses,
      trend: computeTrend(current.total_expenses, previous.total_expenses, {
        goodWhenUp: false,
        useAbsolute: true,
      }),
    },
    {
      label: 'Saldo',
      value: current.net,
      trend: computeTrend(current.net, previous.net),
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {cards.map((card) => (
        <Card key={card.label} {...card} />
      ))}
    </div>
  );
}
