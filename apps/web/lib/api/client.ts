// -----------------------------------------------------------------
// SCALE API Gateway Client
// Typed wrappers for the FastAPI backend at /api/v1
// -----------------------------------------------------------------

const API_BASE =
  (typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || 'http://localhost:8000';

// ── Types ────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  services?: {
    api: string;
    redis: string;
    celery: string;
  };
  engines?: {
    ingestion: string;
    forecasting: string;
  };
}

export interface IngestTransaction {
  date: string;
  amount: number;
  merchant: string;
  fingerprint: string;
  [key: string]: unknown;
}

export interface IngestResponse {
  transactions: IngestTransaction[];
  count: number;
}

export interface ForecastPrediction {
  day_offset: number;
  predicted_spend: number;
  predicted_income: number;
  predicted_net: number;
}

export interface ForecastResponse {
  predictions: ForecastPrediction[];
  horizon_days: number;
  model: string;
  note: string;
}

export interface SafeToSpendResponse {
  safe_amount: number;
  currency: string;
  horizon_days: number;
  confidence: number;
  avg_daily_income?: number;
  avg_daily_spend?: number;
  days_analyzed?: number;
  model: string;
  note: string;
  forecast_breakdown?: {
    date: string;
    p10: number;
    p50: number;
    p90: number;
  }[];
}

// ── Helpers ──────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function apiFetch<T>(path: string, options?: RequestInit, timeoutMs = 10_000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...options?.headers,
      },
    });

    if (!res.ok) {
      const bodyText = await res.text().catch(() => '');
      let errorMessage = `API ${res.status}: ${res.statusText}`;

      // Try to parse JSON body for "detail"
      try {
        const bodyJson = JSON.parse(bodyText);
        if (bodyJson.detail) {
          errorMessage = bodyJson.detail;
        }
      } catch {
        // 'e' variable removed as it was unused
        // ignore JSON parse error
      }

      throw new ApiError(errorMessage, res.status, bodyText);
    }

    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError('API request timed out', 0);
    }
    throw new ApiError(err instanceof Error ? err.message : 'Network error', 0);
  } finally {
    clearTimeout(timer);
  }
}

// ── Public API ───────────────────────────────────────────────────

/** Check if the AI gateway is reachable */
export async function apiHealthCheck(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/api/v1/health');
}

/** Upload a CSV/Excel file for server-side ingestion + fingerprinting + categorization */
export async function apiIngestFile(file: File, password?: string): Promise<IngestResponse> {
  const form = new FormData();
  form.append('file', file);
  if (password) {
    form.append('password', password);
  }

  // 120s timeout — Excel parsing + HypCD classifier cold start can take 30-60s on first request
  return apiFetch<IngestResponse>(
    '/api/v1/ingest/csv',
    {
      method: 'POST',
      body: form,
    },
    120_000
  );
}

/** Upload a CSV and get a 7-day spending forecast */
export async function apiForecastPredict(
  file: File,
  accessToken?: string
): Promise<ForecastResponse> {
  const form = new FormData();
  form.append('file', file);

  return apiFetch<ForecastResponse>('/api/v1/forecast/predict', {
    method: 'POST',
    body: form,
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
  });
}

/** Get the current safe-to-spend amount (requires auth) */
export async function apiSafeToSpend(accessToken?: string): Promise<SafeToSpendResponse> {
  return apiFetch<SafeToSpendResponse>('/api/v1/forecast/safe-to-spend', {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
  });
}

export interface ClassifyResponse {
  [description: string]: string;
}

export interface FeedbackResponse {
  status: string;
  updated_categories: string[];
}

/** Classify transaction descriptions using HypCD */
export async function apiClassifyDescriptions(
  descriptions: string[],
  accessToken?: string
): Promise<ClassifyResponse> {
  return apiFetch<ClassifyResponse>(
    '/api/v1/classify',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify({ descriptions }),
    },
    30_000
  ); // 30s for HypCD cold start
}

/** Send category corrections to HypCD for active learning */
export async function apiSubmitFeedback(
  corrections: Record<string, string>,
  accessToken?: string
): Promise<FeedbackResponse> {
  return apiFetch<FeedbackResponse>(
    '/api/v1/feedback',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify({ corrections }),
    },
    15_000
  );
}

export interface TrainingUploadResponse {
  status: string;
  message: string;
  job_id: string;
  transaction_count: number;
}

/** Upload training data (CSV/Excel) and trigger training job */
export async function apiUploadTrainingData(
  file: File,
  password?: string,
  accessToken?: string
): Promise<TrainingUploadResponse> {
  const form = new FormData();
  form.append('file', file);
  if (password) {
    form.append('password', password);
  }

  // The client sends the token in the header
  const headers: Record<string, string> = {};
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  return apiFetch<TrainingUploadResponse>('/api/v1/training/upload', {
    method: 'POST',
    body: form,
    headers,
  });
}

export interface TrainingJob {
  id: string;
  user_id: string;
  status: 'pending' | 'training' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  logs?: string;
  metrics?: {
    val_loss?: number;
    transaction_count?: number;
    epochs_trained?: number;
    [key: string]: unknown;
  };
}

/** Get the latest training job for the current user */
export async function apiGetLatestTrainingJob(accessToken?: string): Promise<TrainingJob | null> {
  // Use apiFetch if available, or fetch directly.
  // Assuming apiFetch handles full URL if it doesn't start with /api...?
  // The existing calls use "/api/v1/..."
  // So:
  return apiFetch<TrainingJob>('/api/v1/training/latest', {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
  });
}
