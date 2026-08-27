import { api } from './client.js';

/**
 * Run one read-only statement. The backend refuses anything that writes and
 * caps the rows returned, so `limit` is a display cap — it does not become part
 * of the SQL.
 */
export function executeSql(sql, limit) {
  return api.post('/sql/execute', { sql, limit });
}

/** Tables and columns of the live database, for the reference panel. */
export function fetchSchema() {
  return api.get('/sql/schema');
}

/** All saved queries, ordered folder-then-name. */
export function listSavedQueries() {
  return api.get('/sql/queries');
}

export function createSavedQuery(body) {
  return api.post('/sql/queries', body);
}

/** Partial update — send only what changed. `folder: ''` moves to the top level. */
export function updateSavedQuery(id, body) {
  return api.patch(`/sql/queries/${id}`, body);
}

export function deleteSavedQuery(id) {
  return api.del(`/sql/queries/${id}`);
}

/**
 * Rename a folder, moving every query in it. Renaming onto an existing folder
 * merges them; there is no folder table, so this is the whole operation.
 */
export function renameFolder(name, newName) {
  return api.patch('/sql/folders', { name, new_name: newName });
}
