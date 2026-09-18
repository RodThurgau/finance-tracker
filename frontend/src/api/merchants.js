import { api } from './client.js';

export function listMerchantMappings() {
  return api.get('/merchants');
}

export function createMerchantMapping(body) {
  return api.post('/merchants', body);
}

export function updateMerchantMapping(id, body) {
  return api.patch(`/merchants/${id}`, body);
}

export function deleteMerchantMapping(id) {
  return api.del(`/merchants/${id}`);
}
