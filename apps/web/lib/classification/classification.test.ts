/**
 * Tests for parallel classification flow
 *
 * These tests define the expected behavior for classifying transactions
 * in parallel with insertion, enabling faster UI response times.
 *
 * @see docs/plans/2026-02-14-hybrid-import-architecture.md
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  classifyInBackground,
  buildCategoryUpdatePayload,
  type ClassificationResult,
} from './classification';

// Mock the API client
vi.mock('../api/client', () => ({
  apiClassifyDescriptions: vi.fn(),
}));

import { apiClassifyDescriptions } from '../api/client';

describe('classifyInBackground', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('deduplication before classification', () => {
    it('only sends unique descriptions to classifier', async () => {
      const mockClassify = vi.mocked(apiClassifyDescriptions);
      // Mock returns categories for normalized descriptions (with #ORDER placeholder)
      // Note: normalization lowercases the description but keeps #ORDER uppercase
      mockClassify.mockResolvedValue({
        'swiggy order #ORDER': 'Food',
        'zomato order #ORDER': 'Food',
      });

      const descriptions = [
        'SWIGGY ORDER #12345',
        'SWIGGY ORDER #67890', // Duplicate normalized form
        'ZOMATO ORDER #11111',
      ];

      await classifyInBackground(descriptions);

      // Should only call API with unique normalized descriptions
      expect(mockClassify).toHaveBeenCalledTimes(1);
      // Check first argument (descriptions array) - second arg is optional accessToken
      expect(mockClassify.mock.calls[0][0]).toEqual(
        expect.arrayContaining(['swiggy order #ORDER', 'zomato order #ORDER'])
      );
      expect(mockClassify.mock.calls[0][0]).toHaveLength(2);
    });

    it('returns mapping of all original descriptions to categories', async () => {
      const mockClassify = vi.mocked(apiClassifyDescriptions);
      // Mock returns categories for normalized descriptions (with #ORDER placeholder)
      mockClassify.mockResolvedValue({
        'swiggy order #ORDER': 'Food',
        'zomato order #ORDER': 'Food',
      });

      const descriptions = ['SWIGGY ORDER #12345', 'SWIGGY ORDER #67890', 'ZOMATO ORDER #11111'];

      const result = await classifyInBackground(descriptions);

      // Both Swiggy orders should map to Food
      expect(result.get('SWIGGY ORDER #12345')).toBe('Food');
      expect(result.get('SWIGGY ORDER #67890')).toBe('Food');
      expect(result.get('ZOMATO ORDER #11111')).toBe('Food');
    });
  });

  describe('error handling', () => {
    it('returns empty map when classification fails', async () => {
      const mockClassify = vi.mocked(apiClassifyDescriptions);
      mockClassify.mockRejectedValue(new Error('API unavailable'));

      const descriptions = ['SWIGGY ORDER #12345'];
      const result = await classifyInBackground(descriptions);

      expect(result.size).toBe(0);
    });

    it('handles timeout gracefully', async () => {
      const mockClassify = vi.mocked(apiClassifyDescriptions);
      mockClassify.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 60000)));

      const descriptions = ['SWIGGY ORDER #12345'];

      // Start classification with a short timeout (100ms)
      const resultPromise = classifyInBackground(descriptions, undefined, 100);

      // Advance past timeout (need to advance past the 100ms timeout)
      await vi.advanceTimersByTimeAsync(200);

      const result = await resultPromise;
      expect(result.size).toBe(0);
    });
  });

  describe('performance', () => {
    it('classifies 100 unique descriptions in reasonable time', async () => {
      const mockClassify = vi.mocked(apiClassifyDescriptions);
      // Create 100 unique normalized descriptions (using different merchants)
      // Note: normalization produces lowercase description with uppercase #ORDER
      const mockCategories = Object.fromEntries(
        Array.from({ length: 100 }, (_, i) => [`merchant${i} #ORDER`, 'Misc'])
      );
      mockClassify.mockResolvedValue(mockCategories);

      // Create 100 descriptions with unique normalized forms
      const descriptions = Array.from({ length: 100 }, (_, i) => `MERCHANT${i} #${i}000`);

      const start = Date.now();
      const result = await classifyInBackground(descriptions);
      const elapsed = Date.now() - start;

      expect(result.size).toBe(100);
      expect(elapsed).toBeLessThan(100); // Should be instant with mock
    });
  });
});

describe('buildCategoryUpdatePayload', () => {
  it('builds payload for Supabase update', () => {
    const categoryMap = new Map<string, string>([
      ['SWIGGY ORDER #12345', 'Food'],
      ['ZOMATO ORDER #11111', 'Food'],
      ['AMAZON TXN_99999', 'Shopping'],
    ]);

    const payload = buildCategoryUpdatePayload(categoryMap);

    expect(payload).toEqual({
      updates: [
        { description: 'SWIGGY ORDER #12345', category: 'Food' },
        { description: 'ZOMATO ORDER #11111', category: 'Food' },
        { description: 'AMAZON TXN_99999', category: 'Shopping' },
      ],
    });
  });

  it('handles empty map', () => {
    const payload = buildCategoryUpdatePayload(new Map());
    expect(payload).toEqual({ updates: [] });
  });

  it('filters out Uncategorized entries', () => {
    const categoryMap = new Map<string, string>([
      ['SWIGGY ORDER #12345', 'Food'],
      ['UNKNOWN TRANSACTION', 'Uncategorized'],
    ]);

    const payload = buildCategoryUpdatePayload(categoryMap);

    expect(payload.updates).toHaveLength(1);
    expect(payload.updates[0].category).toBe('Food');
  });
});

describe('ClassificationResult type', () => {
  it('represents successful classification', () => {
    const result: ClassificationResult = {
      success: true,
      categories: new Map([['SWIGGY ORDER', 'Food']]),
      classifiedCount: 1,
      totalCount: 1,
    };

    expect(result.success).toBe(true);
    expect(result.classifiedCount).toBe(1);
  });

  it('represents failed classification', () => {
    const result: ClassificationResult = {
      success: false,
      categories: new Map(),
      classifiedCount: 0,
      totalCount: 5,
      error: 'API unavailable',
    };

    expect(result.success).toBe(false);
    expect(result.error).toBe('API unavailable');
  });
});
