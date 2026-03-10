import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  ApiError,
  healthApi,
  ingestionApi,
  forecastApi,
  categorizationApi,
  trainingApi,
} from './client';

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000/api/v1';
  });

  describe('ApiError', () => {
    it('should create error with status code on API failures', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        headers: new Map([['content-type', 'application/json']]),
        text: () => Promise.resolve(JSON.stringify({ detail: 'Not found' })),
        json: () => Promise.resolve({ detail: 'Not found' }),
      });

      await expect(healthApi.check()).rejects.toThrow('Not found');
    });
  });

  describe('healthApi.check', () => {
    it('should return health status', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: () =>
          Promise.resolve({
            status: 'healthy',
            engines: { ingestion: 'ready', forecasting: 'ready' },
          }),
      });

      const result = await healthApi.check();

      expect(result.status).toBe('healthy');
      expect(result.engines?.ingestion).toBe('ready');
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/health/ready',
        expect.objectContaining({
          method: 'GET',
        })
      );
    });

    it('should throw ApiError on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 503,
        statusText: 'Service Unavailable',
        headers: new Map([['content-type', 'text/plain']]),
        text: () => Promise.resolve('Service down'),
        json: () => Promise.reject(new Error('not json')),
      });

      await expect(healthApi.check()).rejects.toThrow(ApiError);
    });
  });

  describe('ingestionApi', () => {
    it('should upload file successfully', async () => {
      const mockFile = new File(['test'], 'test.csv', { type: 'text/csv' });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: () =>
          Promise.resolve({
            transactions: [{ date: '2024-01-01', amount: 100 }],
            count: 1,
          }),
      });

      const result = await ingestionApi.uploadCSV(mockFile, 'test-token');

      expect(result.count).toBe(1);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/ingest/csv',
        expect.objectContaining({
          method: 'POST',
          body: expect.any(FormData),
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });
  });

  describe('forecastApi', () => {
    it('should get forecast prediction', async () => {
      const mockFile = new File(['test'], 'test.csv', { type: 'text/csv' });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: () =>
          Promise.resolve({
            predictions: [{ day_offset: 1, predicted_spend: 100 }],
            horizon_days: 7,
            model: 'test',
            note: 'Test forecast',
          }),
      });

      const result = await forecastApi.predict(mockFile, 'target-token');

      expect(result.horizon_days).toBe(7);
      expect(result.predictions).toHaveLength(1);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/forecast/predict',
        expect.objectContaining({
          method: 'POST',
          body: expect.any(FormData),
          headers: expect.objectContaining({
            Authorization: 'Bearer target-token',
          }),
        })
      );
    });

    it('should get safe to spend amount', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
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

      const result = await forecastApi.safeToSpend('auth-token');

      expect(result.safe_amount).toBe(5000);
      expect(result.confidence).toBe(0.95);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/forecast/safe-to-spend',
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            Authorization: 'Bearer auth-token',
          }),
        })
      );
    });
  });

  describe('categorizationApi', () => {
    it('should classify descriptions in batch', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: () =>
          Promise.resolve({
            'Starbucks Coffee': 'Food & Drink',
            'Uber Ride': 'Transportation',
          }),
      });

      const result = await categorizationApi.classifyBatch(
        ['Starbucks Coffee', 'Uber Ride'],
        'token'
      );

      expect(result['Starbucks Coffee']).toBe('Food & Drink');
      expect(result['Uber Ride']).toBe('Transportation');
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/categorization/classify/batch',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            Authorization: 'Bearer token',
          }),
          body: JSON.stringify({ descriptions: ['Starbucks Coffee', 'Uber Ride'] }),
        })
      );
    });

    it('should submit category corrections', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: () =>
          Promise.resolve({
            status: 'success',
            updated_categories: ['Food & Drink'],
          }),
      });

      const result = await categorizationApi.submitFeedback({ Starbucks: 'Food & Drink' }, 'token');

      expect(result.status).toBe('success');
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/categorization/feedback',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            Authorization: 'Bearer token',
          }),
          body: JSON.stringify({ corrections: { Starbucks: 'Food & Drink' } }),
        })
      );
    });
  });

  describe('trainingApi', () => {
    it('should upload training file', async () => {
      const mockFile = new File(['test'], 'training.csv', { type: 'text/csv' });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: () =>
          Promise.resolve({
            status: 'success',
            message: 'Upload successful',
            job_id: 'job-123',
            transaction_count: 100,
          }),
      });

      const result = await trainingApi.upload(mockFile, 'auth-token');

      expect(result.job_id).toBe('job-123');
      expect(result.transaction_count).toBe(100);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/training/upload',
        expect.objectContaining({
          method: 'POST',
          body: expect.any(FormData),
          headers: expect.objectContaining({
            Authorization: 'Bearer auth-token',
          }),
        })
      );
    });

    it('should get latest training job', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: () =>
          Promise.resolve({
            id: 'job-123',
            user_id: 'user-456',
            status: 'completed',
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T01:00:00Z',
          }),
      });

      const result = await trainingApi.getLatest('auth-token');

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
        headers: new Map([['content-type', 'application/json']]),
        text: () => Promise.resolve(JSON.stringify({ detail: 'Invalid request format' })),
        json: () => Promise.resolve({ detail: 'Invalid request format' }),
      });

      await expect(healthApi.check()).rejects.toThrow('Invalid request format');
    });

    it('should use default error if no JSON detail', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        headers: new Map([['content-type', 'text/plain']]),
        text: () => Promise.resolve('Plain text error'),
        json: () => Promise.reject(new Error('not json')),
      });

      await expect(healthApi.check()).rejects.toThrow('Unknown error');
    });
  });
});
