import { api } from './client.js';

/** Match fields a rule can declare — mirrors the backend's `RuleField` enum. */
export const RULE_FIELDS = [
  { value: 'description', label: 'Beschreibung' },
  { value: 'counter_account', label: 'Empfänger/Auftraggeber' },
  { value: 'transaction_type', label: 'Buchungstext' },
];

/** Create a rule. Creating one never recategorizes existing transactions —
 *  that only happens on import or via an explicit POST /rules/apply. */
export function createRule(body) {
  return api.post('/rules', body);
}
