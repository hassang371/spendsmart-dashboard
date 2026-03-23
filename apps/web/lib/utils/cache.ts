import { getAppStorage } from './storage';

/**
 * The prefix used for all app-owned cache keys in storage.
 * Used by eviction logic to identify and clean only app-owned entries.
 */
export const APP_CACHE_PREFIX = process.env.NODE_ENV === 'development' ? 'dev:' : 'prod:';

/**
 * Helper to standardise cache keys with environment prefix.
 * Development keys won't collide with Production keys if running on same domain.
 */
export function getCacheKey(key: string): string {
  return `${APP_CACHE_PREFIX}${key}`;
}

/**
 * BUG-010 + FE-1 fix: Evict only app-owned cache keys by prefix.
 * Safe to call on quota exceeded — does NOT touch keys from other origins/apps.
 *
 * @param storage The storage instance to evict from
 */
function evictAppCacheByPrefix(storage: Storage): void {
  const keysToRemove: string[] = [];
  for (let i = 0; i < storage.length; i++) {
    const k = storage.key(i);
    if (k && k.startsWith(APP_CACHE_PREFIX)) {
      keysToRemove.push(k);
    }
  }
  keysToRemove.forEach(k => storage.removeItem(k));
}

/**
 * Intentionally clear ALL app-owned cache entries.
 * Use this for logout/destructive actions. Does NOT clear non-app keys.
 */
export function clearAppCache(): void {
  const storage = getAppStorage();
  if (!storage) return;
  evictAppCacheByPrefix(storage);
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

    // BUG-010 fix: On quota exceeded, evict only app-owned keys.
    // storage.clear() would wipe ALL same-origin storage including session data.
    if (error instanceof DOMException && error.name === 'QuotaExceededError') {
      evictAppCacheByPrefix(storage);
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
