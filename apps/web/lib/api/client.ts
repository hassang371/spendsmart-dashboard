/**
 * Centralized API client for the SCALE frontend.
 *
 * All backend calls go through this client, which handles:
 * - Base URL configuration
 * - Auth token injection
 * - Error normalization
 *
 * The backend routes are under /api/v1/ on the FastAPI server.
 * The Next.js API routes have been deleted as part of M1.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface ApiOptions {
  method?: string;
  body?: unknown;
  token?: string;
  headers?: Record<string, string>;
}

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function apiFetch<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { method = 'GET', body, token, headers = {} } = options;

  const requestHeaders: Record<string, string> = {
    ...headers,
  };

  if (token) {
    requestHeaders['Authorization'] = `Bearer ${token}`;
  }

  if (body && !(body instanceof FormData)) {
    requestHeaders['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: requestHeaders,
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(response.status, errorData.detail || 'Request failed');
  }

  return response.json();
}

// --- Domain-specific helpers ---

export const ingestionApi = {
  uploadCSV: (file: File, token: string) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiFetch('/ingest/csv', { method: 'POST', body: formData, token });
  },
};

export const categorizationApi = {
  classify: (description: string, token: string) =>
    apiFetch('/categorization/classify', {
      method: 'POST',
      body: { description },
      token,
    }),

  classifyBatch: (descriptions: string[], token: string) =>
    apiFetch('/categorization/classify/batch', {
      method: 'POST',
      body: { descriptions },
      token,
    }),

  submitFeedback: (corrections: Record<string, string>, token: string) =>
    apiFetch('/categorization/feedback', {
      method: 'POST',
      body: { corrections },
      token,
    }),
};

export const forecastApi = {
  predict: (file: File, token: string) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiFetch('/forecast/predict', { method: 'POST', body: formData, token });
  },

  safeToSpend: (token: string) => apiFetch('/forecast/safe-to-spend', { token }),
};

export const trainingApi = {
  upload: (file: File, token: string) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiFetch('/training/upload', { method: 'POST', body: formData, token });
  },

  train: (params: { epochs?: number; batch_size?: number }, token: string) =>
    apiFetch('/training/train', { method: 'POST', body: params, token }),

  getStatus: (jobId: string, token: string) => apiFetch(`/training/status/${jobId}`, { token }),

  getLatest: (token: string) => apiFetch('/training/latest', { token }),
};

export const accountsApi = {
  getTransactions: (token: string) => apiFetch('/accounts/transactions', { token }),

  getProfile: (token: string) => apiFetch('/accounts/profile', { token }),
};

export const healthApi = {
  check: () => apiFetch('/health'),
};

export { ApiError, apiFetch };
