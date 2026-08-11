import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import { useCategoryIndex } from '../hooks/useLookups.js';
import { formatAmount } from '../lib/format.js';

// Slices reuse each category's own stored color (Pills.jsx does the same for
// pills/badges) rather than a freshly assigned categorical palette — the
// color already carries identity consistently everywhere else in the app.
// "Nicht kategorisiert" and any category left without a valid color fall
// back to this neutral gray, the same fallback Pills.jsx uses.
const FALLBACK_COLOR = '#9aa1ad';
const HEX_COLOR = /^#[0-9a-f]{6}$/i;

function sliceColor(category) {
  return category?.color && HEX_COLOR.test(category.color) ? category.color : FALLBACK_COLOR;
}

/**
 * Pie chart of spending by category. `data` is `/stats/summary`'s
 * `by_category`: **net** of any income filed under the same category (the
 * uncategorized bucket excepted — it stays gross), and always negative, since
 * the backend drops categories that net to zero or above. A fully reimbursed
 * category therefore has no slice at all rather than an empty one. Clicking a
 * slice navigates to the transaction list filtered to that category.
 */
export function CategoryPieChart({ data }) {
  const navigate = useNavigate();
  const categoryIndex = useCategoryIndex();

  const slices = useMemo(
    () =>
      data.map((entry) => ({
        key: entry.category_id ?? 'uncategorized',
        categoryId: entry.category_id,
        // "Ohne Kategorie", not "Nicht kategorisiert": the latter is the name
        // of a real seeded category rows can be filed under, and it turns up
        // in this same legend. Matches the transaction filter's wording, and
        // the slice links to that filter.
        name: entry.category_name ?? 'Ohne Kategorie',
        // Slice size is spend magnitude; totals arrive negative (expenses).
        amount: Math.abs(Number(entry.total)),
        total: entry.total,
        color: sliceColor(entry.category_id ? categoryIndex.byId.get(entry.category_id) : null),
      })),
    [data, categoryIndex],
  );

  if (slices.length === 0) {
    return (
      <p className="flex h-72 items-center justify-center text-sm text-content-muted">
        Keine Ausgaben im gewählten Zeitraum.
      </p>
    );
  }

  function handleClick(slice) {
    navigate(
      slice.categoryId
        ? `/transaktionen?category_id=${slice.categoryId}`
        : '/transaktionen?uncategorized=true',
    );
  }

  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={slices}
            dataKey="amount"
            nameKey="name"
            innerRadius="55%"
            outerRadius="85%"
            paddingAngle={2}
            cursor="pointer"
            onClick={handleClick}
          >
            {slices.map((slice) => (
              <Cell
                key={slice.key}
                fill={slice.color}
                stroke="var(--color-surface-raised)"
                strokeWidth={2}
              />
            ))}
          </Pie>
          <Tooltip
            formatter={(_value, _name, item) => [formatAmount(item.payload.total), item.payload.name]}
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
            wrapperStyle={{ fontSize: 12, color: 'var(--color-content-muted)' }}
            iconType="circle"
            iconSize={8}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
