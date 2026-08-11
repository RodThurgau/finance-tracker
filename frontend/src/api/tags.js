import { api } from './client.js';

/** All tags, each with its usage count. */
export function listTags() {
  return api.get('/tags');
}

export function createTag(body) {
  return api.post('/tags', body);
}

/** Rename and/or recolor. Assignments are keyed by tag id, so a renamed tag
 *  stays on every transaction that carried it. */
export function updateTag(id, body) {
  return api.patch(`/tags/${id}`, body);
}

/** Delete a tag, removing it from every transaction that carried it. */
export function deleteTag(id) {
  return api.del(`/tags/${id}`);
}
