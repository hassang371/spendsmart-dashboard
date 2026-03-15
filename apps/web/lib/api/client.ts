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

import * as Sentry from '@sentry/nextjs';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface ApiOptions {
  method?: string;
  body?: unknown;
  token?: string;
  headers?: Record<string, string>;
}

class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public data?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export interface ForecastPrediction {
  day_offset: number;
  predicted_spend: number;
  predicted_income: number;
  predicted_net: number;
}

export interface ForecastResponse {
  model: string;
  note?: string;
  predictions: ForecastPrediction[];
}

export interface HealthResponse {
  services?: {
    api?: string;
    redis?: string;
    celery?: string;
  };
  engines?: {
    ingestion?: string;
  };
}

export interface TrainingUploadResponse {
  job_id: string;
  status?: string;
  message?: string;
  transaction_count?: number;
  queued_training?: boolean;
}

export interface TrainingJob {
  id: string;
  status: 'pending' | 'training' | 'completed' | 'failed';
  created_at: string;
  metrics?: {
    val_loss?: number;
    epochs_trained?: number;
    transaction_count?: number;
  };
}

export interface SafeToSpendResponse {
  safe_amount: number;
  horizon_days: number;
  confidence: number;
  model: string;
  forecast_breakdown?: any[];
}

// --- Bank Account types ---

export interface BankAccount {
  id: string;
  user_id: string;
  account_name: string;
  account_type: string;
  institution: string | null;
  provider: string | null;
  consent_status: 'none' | 'pending' | 'active' | 'expired' | 'revoked';
  last_synced_at: string | null;
  sync_status: 'idle' | 'syncing' | 'error';
  is_primary: boolean;
  is_manual: boolean;
  masked_number: string | null;
  currency: string;
  created_at: string;
  updated_at: string;
}

export interface LinkAccountRequest {
  fi_types?: string[];
}

export interface LinkAccountResponse {
  consent_id: string;
  redirect_url: string;
}

export interface SyncAccountResponse {
  account_id: string;
  inserted: number;
  skipped_duplicates: number;
}

// --- Import response ---

export interface ImportResponse {
  inserted: number;
  skipped_duplicates: number;
  total_parsed: number;
  filename: string;
}

// --- Transaction types ---

export interface Transaction {
  id: string;
  user_id: string;
  transaction_date: string;
  amount: number;
  currency: string;
  description: string;
  merchant_name: string;
  category: string;
  suggested_category?: string | null;
  confidence_score?: number | null;
  payment_method: string;
  status: string;
  type: string;
  fingerprint?: string;
  is_manual?: boolean;
  created_at?: string;
  raw_data?: Record<string, unknown>;
}

export interface UncategorizedTransaction {
  id: string;
  description: string;
  amount: number;
  category: string;
  suggested_category?: string | null;
  confidence_score?: number | null;
  transaction_date: string;
  merchant_name: string;
  payment_method: string;
  type: string;
  created_at: string;
  raw_data?: Record<string, unknown> | null;
  informative_text?: string | null;
  bank_name?: string | null;
}

export interface UncategorizedListResponse {
  items: UncategorizedTransaction[];
  count: number;
}

export interface TransactionListParams {
  limit?: number;
  cursor?: string;
  date_from?: string;
  date_to?: string;
  amount_min?: number;
  amount_max?: number;
  category?: string;
  merchant?: string;
  type?: string;
  include_total?: boolean;
  /** Filter by account UUID. Pass 'all' or omit for all accounts. */
  account_id?: string;
}

export interface TransactionListResponse {
  items: Transaction[];
  next_cursor: string | null;
  has_more: boolean;
  total_count?: number;
  truncated?: boolean;
}

export interface TransactionCountsResponse {
  all: number;
  debit: number;
  credit: number;
  uncategorized: number;
}

export interface TransactionUpdatePayload {
  category?: string;
  amount?: number;
  old_category?: string;
}

export interface BatchUpdateItem {
  id: string;
  category: string;
  amount?: number;
}

async function apiFetch<T = any>(path: string, options: ApiOptions = {}): Promise<T> {
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

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: requestHeaders,
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      const apiError = new ApiError(
        errorData.detail || 'Request failed',
        response.status,
        errorData
      );

      Sentry.captureException(apiError, {
        extra: { path, method, status: response.status, response: errorData },
      });

      throw apiError;
    }

    // BUG-025 fix: Do not unconditionally call response.json().
    // 204 No Content and other no-body success responses throw SyntaxError.
    // Check status and Content-Type before attempting to parse.
    const contentType = response.headers.get('content-type') ?? '';
    const hasBody =
      response.status !== 204 &&
      response.status !== 205 &&
      response.headers.get('content-length') !== '0' &&
      contentType.includes('application/json');

    return hasBody ? await response.json() : (undefined as unknown as T);

  } catch (error) {
    if (!(error instanceof ApiError)) {
      // Capture pure network errors or JSON parse errors
      Sentry.captureException(error, {
        extra: { path, method, type: 'network_or_parse_error' },
      });
    }
    throw error;
  }
}

// --- Domain-specific helpers ---

export const ingestionApi = {
  /** Parse-only: returns parsed transactions without inserting */
  uploadCSV: (file: File, token: string) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiFetch('/ingest/csv', { method: 'POST', body: formData, token });
  },

  /** Full import: parse → classify → dedup → insert into Supabase */
  importFile: (file: File, token: string, password?: string): Promise<ImportResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (password) {
      formData.append('password', password);
    }
    return apiFetch<ImportResponse>('/ingest/import', {
      method: 'POST',
      body: formData,
      token,
    });
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
  upload: (file: File, token: string, password?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (password) {
      formData.append('password', password);
    }
    return apiFetch('/training/upload', { method: 'POST', body: formData, token });
  },

  train: (params: { epochs?: number; batch_size?: number }, token: string) =>
    apiFetch('/training/train', { method: 'POST', body: params, token }),

  getStatus: (jobId: string, token: string) => apiFetch(`/training/status/${jobId}`, { token }),

  getLatest: (token: string) => apiFetch('/training/latest', { token }),
};

export const accountsApi = {
  /** Fetch transactions with cursor-based pagination and filters */
  getTransactions: (
    token: string,
    params?: TransactionListParams
  ): Promise<TransactionListResponse> => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.set(key, String(value));
        }
      });
    }
    const qs = searchParams.toString();
    const path = qs ? `/accounts/transactions?${qs}` : '/accounts/transactions';
    return apiFetch<TransactionListResponse>(path, { token });
  },

  /** Update a single transaction */
  updateTransaction: (transactionId: string, updates: TransactionUpdatePayload, token: string) =>
    apiFetch(`/accounts/transactions/${transactionId}`, {
      method: 'PATCH',
      body: updates,
      token,
    }),

  /** Batch update multiple transactions (e.g., reclassify similar) */
  batchUpdateTransactions: (updates: BatchUpdateItem[], token: string) =>
    apiFetch('/accounts/transactions/batch', {
      method: 'PATCH',
      body: { updates },
      token,
    }),

  /** Fetch transactions where category='Uncategorized' (for Review tab) */
  getUncategorized: (token: string, limit = 50): Promise<UncategorizedListResponse> =>
    apiFetch<UncategorizedListResponse>(`/accounts/transactions/uncategorized?limit=${limit}`, {
      token,
    }),

  /** Return total transaction counts (all/debit/credit/uncategorized) unaffected by pagination */
  getTransactionCounts: (token: string): Promise<TransactionCountsResponse> =>
    apiFetch<TransactionCountsResponse>('/accounts/transactions/count', { token }),

  getProfile: (token: string) => apiFetch('/accounts/profile', { token }),
};

export const bankAccountsApi = {
  /** List all bank accounts for the current user */
  list: (token: string): Promise<BankAccount[]> =>
    apiFetch<BankAccount[]>('/aggregator/accounts/', { token }),

  /** Get a single bank account by ID */
  get: (accountId: string, token: string): Promise<BankAccount> =>
    apiFetch<BankAccount>(`/aggregator/accounts/${accountId}`, { token }),

  /** Initiate AA consent flow — returns redirect URL to send user to */
  link: (token: string, body?: LinkAccountRequest): Promise<LinkAccountResponse> =>
    apiFetch<LinkAccountResponse>('/aggregator/accounts/link', {
      method: 'POST',
      body: body ?? {},
      token,
    }),

  /** Trigger manual sync for an account */
  sync: (accountId: string, token: string): Promise<SyncAccountResponse> =>
    apiFetch<SyncAccountResponse>(`/aggregator/accounts/${accountId}/sync`, {
      method: 'POST',
      token,
    }),

  /** Unlink (revoke consent + soft-delete) an account */
  unlink: (accountId: string, token: string): Promise<void> =>
    apiFetch<void>(`/aggregator/accounts/${accountId}`, {
      method: 'DELETE',
      token,
    }),

  /** Handle Setu consent callback — called after redirect back from Setu */
  handleCallback: (consentId: string, token: string) =>
    apiFetch(`/aggregator/accounts/callback?consent_id=${encodeURIComponent(consentId)}`, { token }),
};

export const healthApi = {
  // /health/ready returns { status, services: { api, redis } }
  check: () => apiFetch('/health/ready'),
};

export { ApiError, apiFetch };
