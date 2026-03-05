import { getAppStorage } from './storage';

/**
 * Helper to standardise cache keys with environment prefix
 * Development keys won't collide with Production keys if running on same domain.
 */
export function getCacheKey(key: string): string {
  const isDev = process.env.NODE_ENV === 'development';
  return isDev ? `dev:${key}` : `prod:${key}`;
}

/**
 * Get item from environment-aware storage with TTL check.
 * Checks timestamp and removes key if expired.
 *
 * @param key The unique identifier for the cache entry
 * @param ttlMs Time-to-live in milliseconds
 * @returns The parsed data or null if expired/missing
 */
export function getCachedData<T>(key: string, ttlMs: number): T | null {
  const storage = getAppStorage();
  if (!storage) return null;

  const fullKey = getCacheKey(key);
  const raw = storage.getItem(fullKey);

  if (!raw) return null;

  try {
    const cached = JSON.parse(raw);

    // Check if the cache object has the expected shape { timestamp: number, data: T }
    if (cached && typeof cached === 'object' && 'timestamp' in cached && 'data' in cached) {
      const now = Date.now();

      // If TTL has expired, clean up and return null
      if (now - cached.timestamp > ttlMs) {
        storage.removeItem(fullKey);
        return null;
      }

      return cached.data as T;
    }

    // Legacy format compatibility (fallback if the cache structure is old)
    return null;
  } catch (error) {
    console.warn(`Failed to parse cache for key ${fullKey}`, error);
    storage.removeItem(fullKey);
    return null;
  }
}

/**
 * Set item into environment-aware storage with timestamp.
 *
 * @param key The unique identifier for the cache entry
 * @param data The data payload to cache
 */
export function setCachedData<T>(key: string, data: T): void {
  const storage = getAppStorage();
  if (!storage) return;

  const fullKey = getCacheKey(key);

  try {
    const payload = {
      timestamp: Date.now(),
      data,
    };
    storage.setItem(fullKey, JSON.stringify(payload));
  } catch (error) {
    console.warn(`Failed to set cache for key ${fullKey}`, error);

    // If quota exceeded, we might want to clear old entries
    if (error instanceof DOMException && error.name === 'QuotaExceededError') {
      storage.clear(); // Extreme approach, could be refined to LRU eviction
    }
  }
}

/**
 * Remove an item from the cache manually.
 */
export function removeCachedData(key: string): void {
  const storage = getAppStorage();
  if (!storage) return;

  storage.removeItem(getCacheKey(key));
}
