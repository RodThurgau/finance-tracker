import { api } from './client.js';

/** List transactions. `params` maps 1:1 onto the endpoint's query parameters;
 *  unset values are dropped by the client's query builder. */
export function listTransactions(params) {
  return api.get('/transactions', params);
}

/** Patch one transaction. Sending `category_id`/`subcategory_id` makes the
 *  backend set `user_categorized = True`; sending only `exclude_from_stats`
 *  does not. */
export function updateTransaction(id, body) {
  return api.patch(`/transactions/${id}`, body);
}

export function bulkUpdateTransactions(body) {
  return api.patch('/transactions/bulk', body);
}

export function addTagToTransaction(transactionId, tagId) {
  return api.post(`/transactions/${transactionId}/tags`, { tag_id: tagId });
}

export function removeTagFromTransaction(transactionId, tagId) {
  return api.del(`/transactions/${transactionId}/tags/${tagId}`);
}
