import { api } from './client.js';

/** All tags, each with its usage count. */
export function listTags() {
  return api.get('/tags');
}
