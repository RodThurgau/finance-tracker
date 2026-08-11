import { AlertTriangle, TrendingDown, TrendingUp } from 'lucide-react';

import { formatAmount, formatDate, formatPercent, isNegativeAmount } from '../lib/format.js';
import { computeTrend } from '../lib/trend.js';

function Trend({ trend, comparisonLabel }) {
  if (!trend) {
    return <p className="mt-1 text-xs text-content-muted">Kein Vergleich zu {comparisonLabel}</p>;
  }
  const Icon = trend.isUp ? TrendingUp : TrendingDown;
  return (
    <p
      className={`mt-1 flex items-center gap-1 text-xs font-medium ${
        trend.isGood ? 'text-positive' : 'text-negative'
      }`}
    >
      <Icon size={14} />
      {formatPercent(trend.percent)} ggü. {comparisonLabel}
    </p>
  );
}

function Card({ label, periodLabel, comparisonLabel, value, trend }) {
  return (
    <div className="rounded-xl border border-line bg-surface-raised p-4">
      {/* The month is named on every card. These are not current-month figures,
          and a total that silently covers a different period than the reader
          assumes is worse than no total at all. */}
      <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">
        {label} <span className="tabular font-normal normal-case">· {periodLabel}</span>
      </p>
      <p
        className={`mt-1 text-2xl font-semibold ${
          isNegativeAmount(value) ? 'text-negative' : 'text-positive'
        }`}
      >
        {formatAmount(value)}
      </p>
      <Trend trend={trend} comparisonLabel={comparisonLabel} />
    </div>
  );
}

/**
 * The account balance, which is not a month figure like the other three — it
 * is the running total carried forward from a hand-verified anchor, so it gets
 * an as-of date instead of a month-over-month trend.
 *
 * Any anchor whose predicted balance disagrees with what was actually observed
 * is surfaced here rather than logged quietly: a drift means the imported data
 * is incomplete, and every figure on this page is understating or overstating
 * by that much.
 */
function BalanceCard({ balance }) {
  const drifted = balance.checks.filter((check) => Number(check.drift) !== 0);

  return (
    <div className="rounded-xl border border-line bg-surface-raised p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">Kontostand</p>
      <p className="mt-1 text-2xl font-semibold text-content">
        {formatAmount(balance.current_balance)}
      </p>
      {drifted.length > 0 ? (
        <p className="mt-1 flex items-start gap-1 text-xs font-medium text-negative">
          <AlertTriangle size={14} className="mt-px shrink-0" />
          Abweichung {formatAmount(drifted[0].drift)} zum {formatDate(drifted[0].on)} — Daten
          unvollständig
        </p>
      ) : (
        <p className="mt-1 text-xs text-content-muted">
          Stand {formatDate(balance.as_of)} · Basis {formatDate(balance.anchor_date)}
        </p>
      )}
    </div>
  );
}

/**
 * The headline stat tiles: one complete calendar month against the one before
 * it, plus the running account balance.
 *
 * The caller decides which month — the page passes the last *complete* one
 * rather than the current one, since a month in progress is missing most of
 * its spending and its trend reads as a collapse. `periodLabel` and
 * `comparisonLabel` name both months on the cards so the figures can't be
 * mistaken for current-month ones.
 *
 * `current` and `previous` are `/stats/summary` responses; `balance` is
 * `/stats/balance`.
 */
export function SummaryCards({ current, previous, periodLabel, comparisonLabel, balance }) {
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
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card
          key={card.label}
          {...card}
          periodLabel={periodLabel}
          comparisonLabel={comparisonLabel}
        />
      ))}
      {balance && <BalanceCard balance={balance} />}
    </div>
  );
}
