import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  ApiError,
  apiHealthCheck,
  apiIngestFile,
  apiForecastPredict,
  apiSafeToSpend,
  apiClassifyDescriptions,
  apiSubmitFeedback,
  apiUploadTrainingData,
  apiGetLatestTrainingJob,
} from './client';

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000';
  });

  describe('ApiError', () => {
    it('should create error with status code on API failures', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        text: () => Promise.resolve(JSON.stringify({ detail: 'Not found' })),
      });

      await expect(apiHealthCheck()).rejects.toThrow('Not found');
    });
  });

  describe('apiHealthCheck', () => {
    it('should return health status', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            status: 'healthy',
            engines: { ingestion: 'ready', forecasting: 'ready' },
          }),
      });

      const result = await apiHealthCheck();

      expect(result.status).toBe('healthy');
      expect(result.engines.ingestion).toBe('ready');
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/health',
        expect.objectContaining({
          headers: expect.objectContaining({
            Accept: 'application/json',
          }),
          signal: expect.any(AbortSignal),
        })
      );
    });

    it('should throw ApiError on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 503,
        statusText: 'Service Unavailable',
        text: () => Promise.resolve('Service down'),
      });

      await expect(apiHealthCheck()).rejects.toThrow(ApiError);
    });
  });

  describe('apiIngestFile', () => {
    it('should upload file successfully', async () => {
      const mockFile = new File(['test'], 'test.csv', { type: 'text/csv' });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            transactions: [{ date: '2024-01-01', amount: 100 }],
            count: 1,
          }),
      });

      const result = await apiIngestFile(mockFile);

      expect(result.count).toBe(1);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/ingest/csv',
        expect.objectContaining({
          method: 'POST',
          body: expect.any(FormData),
        })
      );
    });

    it('should include password if provided', async () => {
      const mockFile = new File(['test'], 'test.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ transactions: [], count: 0 }),
      });

      await apiIngestFile(mockFile, 'secret123');

      const callArgs = mockFetch.mock.calls[0];
      const formData = callArgs[1].body as FormData;
      expect(formData.get('password')).toBe('secret123');
    });
  });

  describe('apiForecastPredict', () => {
    it('should get forecast without auth', async () => {
      const mockFile = new File(['test'], 'test.csv', { type: 'text/csv' });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            predictions: [{ day_offset: 1, predicted_spend: 100 }],
            horizon_days: 7,
            model: 'test',
            note: 'Test forecast',
          }),
      });

      const result = await apiForecastPredict(mockFile);

      expect(result.horizon_days).toBe(7);
      expect(result.predictions).toHaveLength(1);
    });

    it('should include auth token if provided', async () => {
      const mockFile = new File(['test'], 'test.csv', { type: 'text/csv' });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ predictions: [], horizon_days: 7, model: 'test', note: '' }),
      });

      await apiForecastPredict(mockFile, 'test-token');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });
  });

  describe('apiSafeToSpend', () => {
    it('should get safe to spend amount', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            safe_amount: 5000,
            currency: 'USD',
            horizon_days: 7,
            confidence: 0.95,
            model: 'statistical',
            note: 'Safe to spend calculated',
          }),
      });

      const result = await apiSafeToSpend();

      expect(result.safe_amount).toBe(5000);
      expect(result.confidence).toBe(0.95);
    });

    it('should include auth token if provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            safe_amount: 0,
            currency: 'USD',
            horizon_days: 7,
            confidence: 0,
            model: '',
            note: '',
          }),
      });

      await apiSafeToSpend('auth-token');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer auth-token',
          }),
        })
      );
    });
  });

  describe('apiClassifyDescriptions', () => {
    it('should classify descriptions', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            'Starbucks Coffee': 'Food & Drink',
            'Uber Ride': 'Transportation',
          }),
      });

      const result = await apiClassifyDescriptions(['Starbucks Coffee', 'Uber Ride']);

      expect(result['Starbucks Coffee']).toBe('Food & Drink');
      expect(result['Uber Ride']).toBe('Transportation');
    });

    it('should send POST request with descriptions', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({}),
      });

      await apiClassifyDescriptions(['test']);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
          body: JSON.stringify({ descriptions: ['test'] }),
        })
      );
    });
  });

  describe('apiSubmitFeedback', () => {
    it('should submit category corrections', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            status: 'success',
            updated_categories: ['Food & Drink'],
          }),
      });

      const result = await apiSubmitFeedback({ Starbucks: 'Food & Drink' });

      expect(result.status).toBe('success');
    });
  });

  describe('apiUploadTrainingData', () => {
    it('should upload training file', async () => {
      const mockFile = new File(['test'], 'training.csv', { type: 'text/csv' });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            status: 'success',
            message: 'Upload successful',
            job_id: 'job-123',
            transaction_count: 100,
          }),
      });

      const result = await apiUploadTrainingData(mockFile);

      expect(result.job_id).toBe('job-123');
      expect(result.transaction_count).toBe(100);
    });

    it('should include password and auth token if provided', async () => {
      const mockFile = new File(['test'], 'training.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ status: 'success', message: '', job_id: '', transaction_count: 0 }),
      });

      await apiUploadTrainingData(mockFile, 'password123', 'auth-token');

      const callArgs = mockFetch.mock.calls[0];
      const formData = callArgs[1].body as FormData;
      expect(formData.get('password')).toBe('password123');
      expect(callArgs[1].headers.Authorization).toBe('Bearer auth-token');
    });
  });

  describe('apiGetLatestTrainingJob', () => {
    it('should get latest training job', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            id: 'job-123',
            user_id: 'user-456',
            status: 'completed',
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T01:00:00Z',
          }),
      });

      const result = await apiGetLatestTrainingJob();

      expect(result?.id).toBe('job-123');
      expect(result?.status).toBe('completed');
    });
  });

  describe('error handling', () => {
    it('should parse JSON error detail if available', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
        text: () => Promise.resolve(JSON.stringify({ detail: 'Invalid file format' })),
      });

      await expect(apiHealthCheck()).rejects.toThrow('Invalid file format');
    });

    it('should use status text if JSON parse fails', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        text: () => Promise.resolve('Plain text error'),
      });

      await expect(apiHealthCheck()).rejects.toThrow('API 500: Internal Server Error');
    });

    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network failure'));

      await expect(apiHealthCheck()).rejects.toThrow('Network failure');
    });

    it('should handle timeout errors', async () => {
      const abortError = new DOMException('The operation was aborted', 'AbortError');
      mockFetch.mockRejectedValueOnce(abortError);

      await expect(apiHealthCheck()).rejects.toThrow('API request timed out');
    });
  });
});
