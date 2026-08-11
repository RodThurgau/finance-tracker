import { api } from './client.js';

/** Match fields a rule can declare — mirrors the backend's `RuleField` enum. */
export const RULE_FIELDS = [
  { value: 'description', label: 'Beschreibung' },
  { value: 'counter_account', label: 'Empfänger/Auftraggeber' },
  { value: 'transaction_type', label: 'Buchungstext' },
];

/**
 * Create a rule. By default this never touches existing transactions — only
 * newly imported rows and an explicit POST /rules/apply run the rule engine.
 * Passing `apply_to_existing: true` backfills existing rows this rule
 * matches, but only those with no category at all (`category_id === null`);
 * a row that already carries a category, even an auto-assigned one, is left
 * untouched. The response's `applied_count` reports how many were updated.
 */
export function createRule(body) {
  return api.post('/rules', body);
}

/** All rules, already ordered the way the categorizer evaluates them:
 *  `priority DESC, id ASC`, first match wins. Each entry carries the resolved
 *  category/subcategory names alongside the ids. */
export function listRules() {
  return api.get('/rules');
}

export function updateRule(id, body) {
  return api.patch(`/rules/${id}`, body);
}

export function deleteRule(id) {
  return api.del(`/rules/${id}`);
}

/**
 * Re-run every rule against every transaction with `user_categorized === false`.
 * Manually categorized rows are never touched; rows an *older* rule
 * auto-assigned are re-evaluated and may change category. Returns
 * `{ categorized }`.
 */
export function applyRules() {
  return api.post('/rules/apply');
}
