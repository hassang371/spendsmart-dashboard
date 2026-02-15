import { describe, it, expect, vi, beforeEach } from 'vitest';
import { POST } from './route';
import type { NextRequest } from 'next/server';

// Mock Supabase
const mockSupabase: any = {
  auth: {
    getUser: vi.fn().mockResolvedValue({
      data: { user: { id: 'test-user-id' } },
      error: null,
    }),
  },
  from: vi.fn(() => ({
    select: vi.fn().mockReturnThis(),
    insert: vi.fn().mockResolvedValue({ data: null, error: null }),
    update: vi.fn().mockReturnThis(),
    eq: vi.fn().mockReturnThis(),
    single: vi.fn().mockResolvedValue({ data: null, error: null }),
  })),
};

vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => mockSupabase),
}));

describe('POST /api/import', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_SUPABASE_URL = 'http://localhost';
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test-key';
  });

  const createMockRequest = (body: object, token = 'Bearer valid-token') => {
    const headers = new Headers();
    headers.set('authorization', token);

    return {
      method: 'POST',
      headers,
      json: vi.fn().mockResolvedValue(body),
    } as unknown as NextRequest;
  };

  const validTransaction = {
    transaction_date: '2024-01-15',
    amount: 100.5,
    currency: 'USD',
    description: 'Test transaction',
    merchant_name: 'Test Merchant',
    category: 'Food',
    payment_method: 'Card',
    status: 'posted',
    raw_data: {},
  };

  describe('Authentication', () => {
    it('should reject requests without authorization header', async () => {
      const req = {
        method: 'POST',
        headers: new Headers(),
        json: vi.fn().mockResolvedValue({ transactions: [validTransaction] }),
      } as unknown as NextRequest;

      const res = await POST(req);
      const json = await res.json();

      expect(res.status).toBe(401);
      expect(json.error).toBe('Missing bearer token');
    });

    it('should reject requests with invalid bearer token', async () => {
      mockSupabase.auth.getUser.mockResolvedValueOnce({
        data: { user: null },
        error: { message: 'Invalid token' },
      });

      const req = createMockRequest({ transactions: [validTransaction] }, 'Bearer invalid-token');
      const res = await POST(req);
      const json = await res.json();

      expect(res.status).toBe(401);
      expect(json.error).toBe('Invalid bearer token');
    });
  });

  describe('Validation', () => {
    it('should reject invalid transaction data', async () => {
      const invalidBody = {
        transactions: [
          {
            // Missing required fields
            transaction_date: '2024-01-15',
          },
        ],
      };

      const req = createMockRequest(invalidBody);
      const res = await POST(req);
      const json = await res.json();

      expect(res.status).toBe(400);
      expect(json.error).toBeDefined();
    });

    it('should reject empty transactions array', async () => {
      const req = createMockRequest({ transactions: [] });
      const res = await POST(req);

      expect(res.status).toBe(400);
    });

    it('should reject too many transactions', async () => {
      const transactions = Array(5001).fill(validTransaction);
      const req = createMockRequest({ transactions });
      const res = await POST(req);

      expect(res.status).toBe(400);
    });
  });

  describe('Transaction Processing', () => {
    it('should successfully import valid transactions', async () => {
      mockSupabase.from.mockReturnValue({
        insert: vi.fn().mockResolvedValue({ data: null, error: null }),
      });

      const req = createMockRequest({
        transactions: [validTransaction],
        filename: 'test.csv',
        file_hash: 'abc123',
      });

      const res = await POST(req);
      const json = await res.json();

      expect(res.status).toBe(200);
      expect(json.success).toBe(true);
      expect(json.inserted).toBe(1);
    });

    it('should filter out transactions with zero amount', async () => {
      const zeroAmountTx = { ...validTransaction, amount: 0 };

      mockSupabase.from.mockReturnValue({
        insert: vi.fn().mockResolvedValue({ data: null, error: null }),
      });

      const req = createMockRequest({
        transactions: [validTransaction, zeroAmountTx],
      });

      const res = await POST(req);
      const json = await res.json();

      expect(json.inserted).toBe(1);
      expect(json.skipped_zero_amount).toBe(1);
    });

    it('should deduplicate transactions by fingerprint', async () => {
      const duplicateTx = { ...validTransaction };

      mockSupabase.from.mockReturnValue({
        insert: vi.fn().mockResolvedValue({ data: null, error: null }),
      });

      const req = createMockRequest({
        transactions: [validTransaction, duplicateTx],
      });

      const res = await POST(req);
      const json = await res.json();

      expect(json.inserted).toBe(1);
      expect(json.skipped_duplicates).toBe(1);
    });

    it('should handle credit transactions correctly', async () => {
      const creditTx = { ...validTransaction, amount: 100 };

      mockSupabase.from.mockReturnValue({
        insert: vi.fn().mockImplementation(data => {
          expect(data[0].type).toBe('credit');
          return Promise.resolve({ data: null, error: null });
        }),
      });

      const req = createMockRequest({ transactions: [creditTx] });
      await POST(req);

      expect(mockSupabase.from).toHaveBeenCalledWith('transactions');
    });

    it('should handle debit transactions correctly', async () => {
      const debitTx = { ...validTransaction, amount: -100 };

      mockSupabase.from.mockReturnValue({
        insert: vi.fn().mockImplementation(data => {
          expect(data[0].type).toBe('debit');
          return Promise.resolve({ data: null, error: null });
        }),
      });

      const req = createMockRequest({ transactions: [debitTx] });
      await POST(req);
    });

    it('should normalize different date formats', async () => {
      // Use different dates that will normalize to different ISO dates
      // to avoid deduplication (which is based on date|amount|merchant)
      const testCases = [
        { date: '2024-01-15', amount: 100 },
        { date: '15/02/2024', amount: 200 }, // DD/MM/YYYY format, different month
        { date: '20-03-2024', amount: 300 }, // DD-MM-YYYY format, different day/month
      ];

      const transactions = testCases.map(tc => ({
        ...validTransaction,
        transaction_date: tc.date,
        amount: tc.amount,
        description: `Test ${tc.amount}`,
      }));

      mockSupabase.from.mockReturnValue({
        insert: vi.fn().mockResolvedValue({ data: null, error: null }),
      });

      const req = createMockRequest({ transactions });
      const res = await POST(req);
      const json = await res.json();

      expect(json.inserted).toBe(3);
    });
  });

  describe('Batch Processing', () => {
    it('should process transactions in batches of 500', async () => {
      // Create unique transactions to avoid deduplication
      const transactions = Array(750)
        .fill(null)
        .map((_, i) => ({
          ...validTransaction,
          transaction_date: `2024-01-${String((i % 30) + 1).padStart(2, '0')}`,
          amount: validTransaction.amount + i,
          description: `${validTransaction.description} ${i}`,
          merchant_name: `${validTransaction.merchant_name} ${i}`,
        }));

      const insertMock = vi.fn().mockResolvedValue({ data: null, error: null });

      mockSupabase.from.mockReturnValue({ insert: insertMock });

      const req = createMockRequest({ transactions });
      await POST(req);

      // Should be called twice - once for 500, once for 250
      expect(insertMock).toHaveBeenCalledTimes(2);
    });
  });

  describe('File Tracking', () => {
    it('should track uploaded files when filename and hash provided', async () => {
      const fromMock = vi.fn();
      const insertMock = vi.fn().mockResolvedValue({ data: null, error: null });

      fromMock.mockImplementation(table => {
        if (table === 'uploaded_files') {
          return {
            insert: vi.fn().mockImplementation(data => {
              expect(data.user_id).toBe('test-user-id');
              expect(data.filename).toBe('test.csv');
              expect(data.file_hash).toBe('abc123');
              return Promise.resolve({ data: null, error: null });
            }),
          };
        }
        return { insert: insertMock };
      });

      mockSupabase.from = fromMock;

      const req = createMockRequest({
        transactions: [validTransaction],
        filename: 'test.csv',
        file_hash: 'abc123',
      });

      await POST(req);

      expect(fromMock).toHaveBeenCalledWith('uploaded_files');
    });
  });

  describe('Error Handling', () => {
    it('should handle Supabase insert errors', async () => {
      mockSupabase.from.mockReturnValue({
        insert: vi.fn().mockResolvedValue({
          data: null,
          error: { message: 'Database error' },
        }),
      });

      const req = createMockRequest({ transactions: [validTransaction] });
      const res = await POST(req);
      const json = await res.json();

      expect(res.status).toBe(500);
      expect(json.error).toBe('Database error');
    });

    it('should handle JSON parse errors', async () => {
      const req = {
        method: 'POST',
        headers: new Headers({ authorization: 'Bearer valid-token' }),
        json: vi.fn().mockRejectedValue(new Error('Invalid JSON')),
      } as unknown as NextRequest;

      const res = await POST(req);

      expect(res.status).toBe(500);
    });

    it('should handle missing environment variables', async () => {
      delete process.env.NEXT_PUBLIC_SUPABASE_URL;

      const req = createMockRequest({ transactions: [validTransaction] });
      const res = await POST(req);
      const json = await res.json();

      expect(res.status).toBe(500);
      expect(json.error).toContain('NEXT_PUBLIC_SUPABASE_URL is not configured');
    });
  });

  describe('Edge Cases', () => {
    it('should handle all zero amount transactions', async () => {
      const zeroTx = { ...validTransaction, amount: 0 };

      const req = createMockRequest({
        transactions: [zeroTx, zeroTx],
      });

      const res = await POST(req);
      const json = await res.json();

      expect(json.inserted).toBe(0);
      expect(json.skipped_zero_amount).toBe(2);
    });

    it('should handle empty description', async () => {
      const txWithEmptyDesc = { ...validTransaction, description: '' };

      mockSupabase.from.mockReturnValue({
        insert: vi.fn().mockResolvedValue({ data: null, error: null }),
      });

      const req = createMockRequest({ transactions: [txWithEmptyDesc] });
      const res = await POST(req);

      expect(res.status).toBe(400); // Zod validation should fail
    });
  });
});
