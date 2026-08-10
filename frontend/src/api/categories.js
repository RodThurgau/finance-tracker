import { api } from './client.js';

/** Categories with nested subcategories and a transaction count each. */
export function listCategories() {
  return api.get('/categories');
}
