/**
 * Tests for batch category update API endpoint
 *
 * This endpoint enables the hybrid import architecture by allowing
 * background classification to update categories after transactions
 * have been inserted.
 *
 * @see docs/plans/2026-02-14-hybrid-import-architecture.md
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { NextRequest } from 'next/server';

// Mock Supabase createClient
const mockSupabase = {
  auth: {
    getUser: vi.fn(),
  },
  from: vi.fn(),
};

vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => mockSupabase),
}));

// Set required environment variables
vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL', 'https://test.supabase.co');
vi.stubEnv('NEXT_PUBLIC_SUPABASE_ANON_KEY', 'test-anon-key');

// Import the route AFTER mocking
const { POST } = await import('./route');

describe('POST /api/transactions/update-categories', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('authentication', () => {
    it('returns 401 when bearer token is missing', async () => {
      const request = new NextRequest('http://localhost/api/transactions/update-categories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          updates: [{ description: 'SWIGGY ORDER #12345', category: 'Food' }],
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(401);
      expect(data.error).toBe('Missing bearer token');
    });

    it('returns 401 when bearer token is invalid', async () => {
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: null },
        error: new Error('Invalid token'),
      });

      const request = new NextRequest('http://localhost/api/transactions/update-categories', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer invalid-token',
        },
        body: JSON.stringify({
          updates: [{ description: 'SWIGGY ORDER #12345', category: 'Food' }],
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(401);
      expect(data.error).toBe('Invalid bearer token');
    });
  });

  describe('input validation', () => {
    it('returns 400 when updates array is missing', async () => {
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: { id: 'user-123' } },
        error: null,
      });

      const request = new NextRequest('http://localhost/api/transactions/update-categories', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer valid-token',
        },
        body: JSON.stringify({}),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain('updates');
    });

    it('returns 400 when updates array is empty', async () => {
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: { id: 'user-123' } },
        error: null,
      });

      const request = new NextRequest('http://localhost/api/transactions/update-categories', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer valid-token',
        },
        body: JSON.stringify({ updates: [] }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain('empty');
    });

    it('returns 400 when updates exceed batch size', async () => {
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: { id: 'user-123' } },
        error: null,
      });

      const updates = Array(501).fill({ description: 'test', category: 'test' });

      const request = new NextRequest('http://localhost/api/transactions/update-categories', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer valid-token',
        },
        body: JSON.stringify({ updates }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain('batch size');
    });

    it('returns 400 when description is missing', async () => {
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: { id: 'user-123' } },
        error: null,
      });

      const request = new NextRequest('http://localhost/api/transactions/update-categories', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer valid-token',
        },
        body: JSON.stringify({
          updates: [{ category: 'Food' }],
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain('description');
    });

    it('returns 400 when category is missing', async () => {
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: { id: 'user-123' } },
        error: null,
      });

      const request = new NextRequest('http://localhost/api/transactions/update-categories', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer valid-token',
        },
        body: JSON.stringify({
          updates: [{ description: 'SWIGGY ORDER #12345' }],
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain('category');
    });
  });

  describe('successful updates', () => {
    it('updates categories and returns count', async () => {
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: { id: 'user-123' } },
        error: null,
      });

      const countEq = vi.fn().mockResolvedValue({ count: 2, error: null });
      const countIn = vi.fn().mockReturnValue({ eq: countEq });
      const select = vi.fn().mockReturnValue({ in: countIn });

      const updateEq = vi.fn().mockResolvedValue({ error: null });
      const updateIn = vi.fn().mockReturnValue({ eq: updateEq });
      const update = vi.fn().mockReturnValue({ in: updateIn });

      mockSupabase.from.mockReturnValue({
        select,
        update,
      } as unknown as ReturnType<typeof mockSupabase.from>);

      const request = new NextRequest('http://localhost/api/transactions/update-categories', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer valid-token',
        },
        body: JSON.stringify({
          updates: [
            { description: 'SWIGGY ORDER #12345', category: 'Food' },
            { description: 'ZOMATO ORDER #11111', category: 'Food' },
          ],
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.updatedCount).toBe(2);
      expect(select).toHaveBeenCalled();
      expect(update).toHaveBeenCalled();
    });
  });

  describe('error handling', () => {
    it('returns 500 when database update fails', async () => {
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: { id: 'user-123' } },
        error: null,
      });

      const countEq = vi.fn().mockResolvedValue({ count: 1, error: null });
      const countIn = vi.fn().mockReturnValue({ eq: countEq });
      const select = vi.fn().mockReturnValue({ in: countIn });

      const updateEq = vi.fn().mockResolvedValue({
        error: new Error('Database error'),
      });
      const updateIn = vi.fn().mockReturnValue({ eq: updateEq });
      const update = vi.fn().mockReturnValue({ in: updateIn });

      mockSupabase.from.mockReturnValue({
        select,
        update,
      } as unknown as ReturnType<typeof mockSupabase.from>);

      const request = new NextRequest('http://localhost/api/transactions/update-categories', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer valid-token',
        },
        body: JSON.stringify({
          updates: [{ description: 'SWIGGY ORDER #12345', category: 'Food' }],
        }),
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(500);
      expect(data.success).toBe(false);
      expect(data.error).toContain('Failed to update category');
    });
  });
});
