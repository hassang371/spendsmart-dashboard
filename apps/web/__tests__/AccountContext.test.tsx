import { renderHook } from '@testing-library/react';
import React from 'react';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock storage so tests are isolated and NODE_ENV-agnostic
const mockStorageData: Record<string, string> = {};
const mockStorage = {
  getItem: vi.fn((key: string) => mockStorageData[key] ?? null),
  setItem: vi.fn((key: string, value: string) => { mockStorageData[key] = value; }),
  removeItem: vi.fn((key: string) => { delete mockStorageData[key]; }),
  clear: vi.fn(() => { Object.keys(mockStorageData).forEach(k => delete mockStorageData[k]); }),
};

vi.mock('../lib/utils/storage', () => ({
  getAppStorage: vi.fn(() => mockStorage),
}));

// Prevent real HTTP calls from the accounts-list fetch
vi.mock('../lib/api/client', () => ({
  bankAccountsApi: {
    list: vi.fn().mockResolvedValue([]),
  },
}));

import { AccountProvider, useAccount } from '../lib/contexts/AccountContext';

describe('AccountContext — activeAccountId initialization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset in-memory storage between tests
    Object.keys(mockStorageData).forEach(k => delete mockStorageData[k]);
    // Re-wire mock fns (cleared by clearAllMocks)
    mockStorage.getItem.mockImplementation((key: string) => mockStorageData[key] ?? null);
    mockStorage.setItem.mockImplementation((key: string, value: string) => { mockStorageData[key] = value; });
  });

  it('reads activeAccountId from storage synchronously on first render without waiting for effects', () => {
    // Simulate a returning user whose account preference is already stored
    mockStorageData['scale_active_account_id'] = 'stored-uuid-456';

    const { result } = renderHook(() => useAccount(), {
      wrapper: ({ children }) => (
        <AccountProvider token="">{children}</AccountProvider>
      ),
    });

    // With current code (useState('all') + restore useEffect):
    //   result.current.activeAccountId === 'all' at this point — FAIL
    // After fix (lazy useState initializer that reads storage synchronously):
    //   result.current.activeAccountId === 'stored-uuid-456' — PASS
    expect(result.current.activeAccountId).toBe('stored-uuid-456');
  });
});
