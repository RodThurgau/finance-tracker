import { api } from './client.js';

function fileFormData(file) {
  const formData = new FormData();
  formData.append('file', file);
  return formData;
}

/** Preclean + detect + parse only — nothing is written to the database. */
export function previewImport(file) {
  return api.post('/import/preview', fileFormData(file));
}

/** The real import: preclean → detect → parse → upsert, committed. */
export function importCsv(file) {
  return api.post('/import/csv', fileFormData(file));
}
