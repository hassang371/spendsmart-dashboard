import { describe, it, expect, vi, beforeEach } from 'vitest';

// Set environment variables BEFORE importing the module
process.env.NEXT_PUBLIC_SUPABASE_URL = 'http://localhost:54321';
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key';
import type { NextRequest } from 'next/server';

// Mock createServerClient
const mockGetUser = vi.fn();

vi.mock('@supabase/ssr', () => ({
  createServerClient: vi.fn(() => ({
    auth: {
      getUser: mockGetUser,
    },
  })),
}));

const { updateSession } = await import('./middleware');

describe('Middleware - updateSession', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const createMockRequest = (pathname: string, cookies: Record<string, string> = {}) => {
    const url = new URL(`http://localhost:3000${pathname}`);
    const nextUrl = Object.assign(new URL(url.toString()), {
      clone: () => new URL(url.toString()),
    });
    const headers = new Headers();

    const cookieEntries = Object.entries(cookies).map(([name, value]) => ({
      name,
      value,
    }));

    return {
      nextUrl,
      headers,
      cookies: {
        getAll: vi.fn().mockReturnValue(cookieEntries),
        set: vi.fn(),
      },
      url: url.toString(),
    } as unknown as NextRequest;
  };

  it('should redirect to login when accessing dashboard without auth', async () => {
    mockGetUser.mockResolvedValue({
      data: { user: null },
      error: { message: 'No user' },
    });

    const req = createMockRequest('/dashboard');
    const res = await updateSession(req);

    expect(res.status).toBe(307); // Redirect status
    const location = res.headers.get('location');
    expect(location).toContain('/login');
    expect(location).toContain('next=%2Fdashboard');
  });

  it('should allow access to dashboard when authenticated', async () => {
    mockGetUser.mockResolvedValue({
      data: { user: { id: 'user-123', email: 'test@example.com' } },
      error: null,
    });

    const req = createMockRequest('/dashboard');
    const res = await updateSession(req);

    expect(res.status).toBe(200); // OK, no redirect
  });

  it('should redirect to dashboard when accessing login page while authenticated', async () => {
    mockGetUser.mockResolvedValue({
      data: { user: { id: 'user-123', email: 'test@example.com' } },
      error: null,
    });

    const req = createMockRequest('/login');
    const res = await updateSession(req);

    expect(res.status).toBe(307);
    expect(res.headers.get('location')).toBe('http://localhost:3000/dashboard');
  });

  it('should redirect to dashboard when accessing signup page while authenticated', async () => {
    mockGetUser.mockResolvedValue({
      data: { user: { id: 'user-123', email: 'test@example.com' } },
      error: null,
    });

    const req = createMockRequest('/signup');
    const res = await updateSession(req);

    expect(res.status).toBe(307);
    expect(res.headers.get('location')).toBe('http://localhost:3000/dashboard');
  });

  it('should redirect to dashboard when accessing landing page while authenticated', async () => {
    mockGetUser.mockResolvedValue({
      data: { user: { id: 'user-123', email: 'test@example.com' } },
      error: null,
    });

    const req = createMockRequest('/');
    const res = await updateSession(req);

    expect(res.status).toBe(307);
    expect(res.headers.get('location')).toBe('http://localhost:3000/dashboard');
  });

  it('should allow access to login page without auth', async () => {
    mockGetUser.mockResolvedValue({
      data: { user: null },
      error: { message: 'No user' },
    });

    const req = createMockRequest('/login');
    const res = await updateSession(req);

    expect(res.status).toBe(200);
  });

  it('should allow access to signup page without auth', async () => {
    mockGetUser.mockResolvedValue({
      data: { user: null },
      error: { message: 'No user' },
    });

    const req = createMockRequest('/signup');
    const res = await updateSession(req);

    expect(res.status).toBe(200);
  });

  it('should allow access to landing page without auth', async () => {
    mockGetUser.mockResolvedValue({
      data: { user: null },
      error: { message: 'No user' },
    });

    const req = createMockRequest('/');
    const res = await updateSession(req);

    expect(res.status).toBe(200);
  });

  it('should handle nested dashboard routes', async () => {
    mockGetUser.mockResolvedValue({
      data: { user: null },
      error: { message: 'No user' },
    });

    const req = createMockRequest('/dashboard/transactions');
    const res = await updateSession(req);

    expect(res.status).toBe(307);
    const location = res.headers.get('location');
    expect(location).toContain('/login');
    expect(location).toContain('next=%2Fdashboard%2Ftransactions');
  });

  it('should handle auth callback routes without redirect', async () => {
    mockGetUser.mockResolvedValue({
      data: { user: null },
      error: { message: 'No user' },
    });

    const req = createMockRequest('/auth/callback');
    const res = await updateSession(req);

    // Should not redirect auth callback
    expect(res.status).toBe(200);
  });

  it('should handle public routes without redirect', async () => {
    mockGetUser.mockResolvedValue({
      data: { user: null },
      error: { message: 'No user' },
    });

    const req = createMockRequest('/about');
    const res = await updateSession(req);

    expect(res.status).toBe(200);
  });

  it('should preserve cookies during request', async () => {
    mockGetUser.mockResolvedValue({
      data: { user: { id: 'user-123' } },
      error: null,
    });

    const req = createMockRequest('/dashboard', {
      'sb-access-token': 'test-token',
      'sb-refresh-token': 'refresh-token',
    });

    const res = await updateSession(req);
    expect(res.status).toBe(200);
  });
});
