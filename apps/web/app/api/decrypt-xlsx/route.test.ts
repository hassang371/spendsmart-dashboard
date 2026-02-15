import { describe, it, expect, vi, beforeEach } from 'vitest';
import { POST } from './route';
import { NextRequest } from 'next/server';

// Mock officecrypto-tool
const mockIsEncrypted = vi.fn();
const mockDecrypt = vi.fn();

vi.mock('officecrypto-tool', () => ({
  default: {
    isEncrypted: (...args: any[]) => mockIsEncrypted(...args),
    decrypt: (...args: any[]) => mockDecrypt(...args),
  },
}));

// Mock Supabase
const mockSupabase = {
  auth: {
    getUser: vi.fn().mockResolvedValue({
      data: { user: { id: 'test-user-id' } },
      error: null,
    }),
  },
};

vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => mockSupabase),
}));

describe('POST /api/decrypt-xlsx', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_SUPABASE_URL = 'http://localhost';
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test-key';
  });

  it('should reject requests without authorization header', async () => {
    const req = {
      method: 'POST',
      headers: new Headers(),
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

    const headers = new Headers();
    headers.set('authorization', 'Bearer invalid-token');

    const req = {
      method: 'POST',
      headers,
    } as unknown as NextRequest;

    const res = await POST(req);
    const json = await res.json();

    expect(res.status).toBe(401);
    expect(json.error).toBe('Invalid bearer token');
  });

  it('should return 400 if file is missing', async () => {
    const headers = new Headers();
    headers.set('authorization', 'Bearer valid-token');

    const req = {
      method: 'POST',
      headers,
      formData: vi.fn().mockResolvedValue(new FormData()),
    } as unknown as NextRequest;

    const res = await POST(req);
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error).toBe('File is required');
  });

  it('should return 400 if password is missing', async () => {
    const formData = new FormData();
    const file = new File(['test'], 'test.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    formData.append('file', file);

    const headers = new Headers();
    headers.set('authorization', 'Bearer valid-token');

    const req = {
      method: 'POST',
      headers,
      formData: vi.fn().mockResolvedValue(formData),
    } as unknown as NextRequest;

    const res = await POST(req);
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error).toBe('Password is required');
  });

  it('should return original file if not encrypted', async () => {
    const mockFile = new File(['test file content'], 'test.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    const formData = {
      get: (key: string) => {
        if (key === 'file') return mockFile;
        if (key === 'password') return 'testpassword';
        return null;
      },
    };

    mockIsEncrypted.mockResolvedValue(false);

    const headers = new Headers();
    headers.set('authorization', 'Bearer valid-token');

    const req = {
      method: 'POST',
      headers,
      formData: vi.fn().mockResolvedValue(formData),
    } as unknown as NextRequest;

    const res = await POST(req);

    expect(res.status).toBe(200);
    expect(res.headers.get('Content-Type')).toBe(
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    );
    expect(mockIsEncrypted).toHaveBeenCalled();
  });

  it('should decrypt file if encrypted', async () => {
    const decryptedBuffer = Buffer.from('decrypted content');

    const mockFile = new File(['encrypted content'], 'test.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    const formData = {
      get: (key: string) => {
        if (key === 'file') return mockFile;
        if (key === 'password') return 'testpassword';
        return null;
      },
    };

    mockIsEncrypted.mockResolvedValue(true);
    mockDecrypt.mockResolvedValue(decryptedBuffer);

    const headers = new Headers();
    headers.set('authorization', 'Bearer valid-token');

    const req = {
      method: 'POST',
      headers,
      formData: vi.fn().mockResolvedValue(formData),
    } as unknown as NextRequest;

    const res = await POST(req);

    expect(res.status).toBe(200);
    expect(mockDecrypt).toHaveBeenCalledWith(expect.any(Buffer), { password: 'testpassword' });
    expect(res.headers.get('Content-Type')).toBe(
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    );
  });

  it('should return 400 if decryption fails', async () => {
    const mockFile = new File(['encrypted content'], 'test.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    const formData = {
      get: (key: string) => {
        if (key === 'file') return mockFile;
        if (key === 'password') return 'wrongpassword';
        return null;
      },
    };

    mockIsEncrypted.mockResolvedValue(true);
    mockDecrypt.mockRejectedValue(new Error('Decryption failed'));

    const headers = new Headers();
    headers.set('authorization', 'Bearer valid-token');

    const req = {
      method: 'POST',
      headers,
      formData: vi.fn().mockResolvedValue(formData),
    } as unknown as NextRequest;

    const res = await POST(req);
    const json = await res.json();

    expect(res.status).toBe(400);
    expect(json.error).toBe('Incorrect password or decryption failed.');
  });

  it('should return 500 if server error occurs', async () => {
    const headers = new Headers();
    headers.set('authorization', 'Bearer valid-token');

    const req = {
      method: 'POST',
      headers,
      formData: vi.fn().mockRejectedValue(new Error('Unexpected error')),
    } as unknown as NextRequest;

    const res = await POST(req);
    const json = await res.json();

    expect(res.status).toBe(500);
    expect(json.error).toBe('Unexpected error');
  });

  it('should return 500 if Supabase is not configured', async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;

    const headers = new Headers();
    headers.set('authorization', 'Bearer valid-token');

    const req = {
      method: 'POST',
      headers,
    } as unknown as NextRequest;

    const res = await POST(req);
    const json = await res.json();

    expect(res.status).toBe(500);
    expect(json.error).toContain('NEXT_PUBLIC_SUPABASE_URL is not configured');
  });
});
