/**
 * Background classification utilities for parallel transaction processing
 *
 * Enables faster UI response by classifying transactions in parallel
 * with database insertion, rather than blocking on classification.
 *
 * @see docs/plans/2026-02-14-hybrid-import-architecture.md
 */

import { apiClassifyDescriptions } from '../api/client';
import { normalizeBatch } from '../normalization/normalizeDescription';

/**
 * Result of a background classification operation
 */
export interface ClassificationResult {
  success: boolean;
  categories: Map<string, string>;
  classifiedCount: number;
  totalCount: number;
  error?: string;
}

/**
 * Payload for updating categories in the database
 */
export interface CategoryUpdatePayload {
  updates: Array<{
    description: string;
    category: string;
  }>;
}

/**
 * Default timeout for classification API calls (30 seconds)
 */
const DEFAULT_CLASSIFICATION_TIMEOUT_MS = 30_000;

/**
 * Classifies transaction descriptions in the background.
 *
 * This function:
 * 1. Normalizes descriptions to reduce API calls
 * 2. Calls the HypCD classifier API
 * 3. Maps categories back to all original descriptions
 *
 * @param descriptions - Array of raw transaction descriptions
 * @param accessToken - Optional auth token for the classify endpoint
 * @param timeoutMs - Timeout for API call (default 30s)
 * @returns Map of original description → category
 *
 * @example
 * const descriptions = [
 *   'SWIGGY ORDER #12345',
 *   'SWIGGY ORDER #67890',
 *   'ZOMATO ORDER #11111',
 * ];
 *
 * const categories = await classifyInBackground(descriptions, accessToken);
 * // categories.get('SWIGGY ORDER #12345') === 'Food'
 * // categories.get('SWIGGY ORDER #67890') === 'Food'
 */
export async function classifyInBackground(
  descriptions: string[],
  accessToken?: string,
  timeoutMs: number = DEFAULT_CLASSIFICATION_TIMEOUT_MS
): Promise<Map<string, string>> {
  const result = new Map<string, string>();

  if (!descriptions.length) {
    return result;
  }

  try {
    // Step 1: Normalize and group descriptions
    const normalizedGroups = normalizeBatch(descriptions);
    const uniqueNormalized = Array.from(normalizedGroups.keys());

    if (!uniqueNormalized.length) {
      return result;
    }

    // Step 2: Call classifier with timeout
    try {
      // apiClassifyDescriptions doesn't support AbortSignal, so we race with timeout
      const categoryMap = await Promise.race([
        apiClassifyDescriptions(uniqueNormalized, accessToken),
        new Promise<Record<string, string>>((_, reject) =>
          setTimeout(() => reject(new Error('Classification timeout')), timeoutMs)
        ),
      ]);

      // Step 3: Map categories back to all original descriptions
      for (const [normalized, originals] of normalizedGroups) {
        const category = categoryMap[normalized];
        if (category) {
          for (const original of originals) {
            result.set(original, category);
          }
        }
      }
    } catch (apiError) {
      // Return empty map on failure - caller should fall back to keyword classifier
      console.warn('Classification API failed:', apiError);
    }

    return result;
  } catch (error) {
    console.error('Background classification error:', error);
    return result;
  }
}

/**
 * Builds a payload for updating categories in the database.
 *
 * @param categoryMap - Map of description → category
 * @returns Payload suitable for POST /api/transactions/update-categories
 *
 * @example
 * const categories = new Map([
 *   ['SWIGGY ORDER #12345', 'Food'],
 *   ['AMAZON TXN_99999', 'Shopping'],
 * ]);
 *
 * const payload = buildCategoryUpdatePayload(categories);
 * // { updates: [{ description: 'SWIGGY ORDER #12345', category: 'Food' }, ...] }
 */
export function buildCategoryUpdatePayload(
  categoryMap: Map<string, string>
): CategoryUpdatePayload {
  const updates: CategoryUpdatePayload['updates'] = [];

  for (const [description, category] of categoryMap) {
    // Skip Uncategorized entries - they don't need to be updated
    if (category && category !== 'Uncategorized') {
      updates.push({ description, category });
    }
  }

  return { updates };
}

/**
 * Performs classification and returns a detailed result.
 *
 * Use this when you need to know how many transactions were classified
 * vs total, or if there was an error.
 *
 * @param descriptions - Array of raw transaction descriptions
 * @param accessToken - Optional auth token for the classify endpoint
 * @param timeoutMs - Timeout for API call (default 30s)
 * @returns Detailed classification result
 */
export async function classifyWithResult(
  descriptions: string[],
  accessToken?: string,
  timeoutMs: number = DEFAULT_CLASSIFICATION_TIMEOUT_MS
): Promise<ClassificationResult> {
  const categories = await classifyInBackground(descriptions, accessToken, timeoutMs);

  return {
    success: categories.size > 0,
    categories,
    classifiedCount: categories.size,
    totalCount: descriptions.length,
    error:
      categories.size === 0 && descriptions.length > 0
        ? 'Classification failed or timed out'
        : undefined,
  };
}
