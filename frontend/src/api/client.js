const BASE_URL = '/api/v1';

/**
 * Error thrown for any non-2xx response. `status` is the HTTP status and
 * `detail` is the backend's standard `{ "detail": "message" }` payload.
 */
export class ApiError extends Error {
  constructor(status, detail, body) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.body = body;
  }
}

/**
 * Build a query string, dropping params the caller left unset. `null`,
 * `undefined` and `''` all mean "no filter" and must not reach the backend as
 * empty values — FastAPI would try to parse them.
 */
export function buildQuery(params = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue;
    if (Array.isArray(value)) {
      value.forEach((item) => search.append(key, String(item)));
    } else {
      search.append(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : '';
}

async function request(path, { method = 'GET', params, body, signal } = {}) {
  const response = await fetch(`${BASE_URL}${path}${buildQuery(params)}`, {
    method,
    signal,
    headers: body instanceof FormData || body === undefined
      ? undefined
      : { 'Content-Type': 'application/json' },
    body: body instanceof FormData || body === undefined ? body : JSON.stringify(body),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response), await safeClone(response));
  }

  if (response.status === 204) return null;

  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) return response;
  return response.json();
}

/** Pull `detail` out of the error body, falling back to the status text. */
async function readErrorDetail(response) {
  try {
    const payload = await response.clone().json();
    if (typeof payload?.detail === 'string') return payload.detail;
    if (payload?.detail) return JSON.stringify(payload.detail);
    return response.statusText || `HTTP ${response.status}`;
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
}

/** Keep the parsed error body around when there is one — the import endpoint
 *  returns preamble lines on 422 and the UI wants to show them. */
async function safeClone(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export const api = {
  get: (path, params, options) => request(path, { ...options, params }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  patch: (path, body, options) => request(path, { ...options, method: 'PATCH', body }),
  del: (path, options) => request(path, { ...options, method: 'DELETE' }),
};

/**
 * Absolute URL for endpoints the browser fetches directly rather than through
 * `fetch` — CSV export is a plain navigation so the browser handles the
 * Content-Disposition download itself.
 */
export function apiUrl(path, params) {
  return `${BASE_URL}${path}${buildQuery(params)}`;
}
