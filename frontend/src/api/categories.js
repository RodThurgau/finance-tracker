import { api } from './client.js';

/** Categories with nested subcategories and a transaction count each. */
export function listCategories() {
  return api.get('/categories');
}

export function createCategory(body) {
  return api.post('/categories', body);
}

/** Rename and/or recolor. Only the fields sent are changed. */
export function updateCategory(id, body) {
  return api.patch(`/categories/${id}`, body);
}

/**
 * Delete a category. Affected transactions keep their row but lose
 * `category_id`, `subcategory_id` *and* `user_categorized`, which puts them
 * back within reach of the rule engine. Rules pointing at the category go
 * with it — `category_rules.category_id` is NOT NULL and can't be orphaned.
 */
export function deleteCategory(id) {
  return api.del(`/categories/${id}`);
}

export function createSubcategory(categoryId, body) {
  return api.post(`/categories/${categoryId}/subcategories`, body);
}

/** Delete a subcategory. Affected transactions lose `subcategory_id`; their
 *  `user_categorized` flag only clears if they have no `category_id` either. */
export function deleteSubcategory(id) {
  return api.del(`/subcategories/${id}`);
}
