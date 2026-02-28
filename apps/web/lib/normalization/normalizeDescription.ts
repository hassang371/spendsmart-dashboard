/**
 * Transaction description normalization utilities
 *
 * Reduces duplicate API calls to the classifier by normalizing similar
 * descriptions (e.g., "SWIGGY ORDER #12345" and "SWIGGY ORDER #67890"
 * both become "swiggy order #ORDER").
 *
 * @see docs/plans/2026-02-14-hybrid-import-architecture.md
 */

/**
 * Normalization patterns for transaction descriptions
 * Each pattern matches a specific format and replaces with a placeholder
 */
const NORMALIZATION_PATTERNS: Array<{
  pattern: RegExp;
  replacement: string;
}> = [
  // Order numbers: #12345, #123-4567890-1234567
  { pattern: /#\d+[-\d]*/g, replacement: '#ORDER' },

  // Transaction IDs: TXN_12345, txn_67890
  { pattern: /\btxn_\d+/gi, replacement: 'txn_XXXXX' },

  // UPI transaction references: UPI/PAYTM/123456789 -> upi/paytm/XXXXXXXXX
  { pattern: /UPI\/([^/]+)\/\d+/gi, replacement: 'upi/$1/XXXXXXXXX' },

  // UPI IDs with numbers: SWIGGY-12345@ybl, ZOMATO-67890@okaxis
  { pattern: /-\d+@/g, replacement: '-XXXXX@' },

  // Dates: DD/MM/YYYY, DD-MM-YYYY
  { pattern: /\b\d{1,2}[\/-]\d{1,2}[\/-]\d{4}\b/g, replacement: 'DD/MM/YYYY' },

  // Dates: YYYY-MM-DD
  { pattern: /\b\d{4}-\d{2}-\d{2}\b/g, replacement: 'YYYY-MM-DD' },

  // Currency amounts: RS.1234.56, INR 5000.00, ₹1234
  { pattern: /\b(RS\.?|INR|₹)\s*(\d+\.?\d*)/gi, replacement: '$1 XXXX.XX' },

  // Standalone long numbers (5+ digits) - catch-all for IDs
  { pattern: /\b\d{5,}\b/g, replacement: 'XXXXX' },
];

/**
 * Normalizes a transaction description by replacing variable parts
 * with placeholders, enabling grouping of similar transactions.
 *
 * @param description - The raw transaction description
 * @returns Normalized description in lowercase with placeholders
 *
 * @example
 * normalizeDescription('SWIGGY ORDER #12345')
 * // Returns: 'swiggy order #ORDER'
 *
 * @example
 * normalizeDescription('UPI-SWIGGY-12345@ybl')
 * // Returns: 'upi-swiggy-XXXXX@ybl'
 */
export function normalizeDescription(description: string): string {
  // Handle null/undefined/empty
  if (!description || typeof description !== 'string') {
    return '';
  }

  // Trim and lowercase
  let normalized = description.trim().toLowerCase();

  // Handle whitespace-only
  if (!normalized) {
    return '';
  }

  // Apply each normalization pattern
  for (const { pattern, replacement } of NORMALIZATION_PATTERNS) {
    normalized = normalized.replace(pattern, replacement);
  }

  return normalized;
}

/**
 * Normalizes a batch of descriptions and groups them by their normalized form.
 *
 * @param descriptions - Array of raw transaction descriptions
 * @returns Map of normalized description → array of original descriptions
 *
 * @example
 * const descriptions = [
 *   'SWIGGY ORDER #12345',
 *   'SWIGGY ORDER #67890',
 *   'ZOMATO ORDER #11111',
 * ];
 *
 * const result = normalizeBatch(descriptions);
 * // Map {
 * //   'swiggy order #ORDER' => ['SWIGGY ORDER #12345', 'SWIGGY ORDER #67890'],
 * //   'zomato order #ORDER' => ['ZOMATO ORDER #11111'],
 * // }
 */
export function normalizeBatch(descriptions: string[]): Map<string, string[]> {
  const groups = new Map<string, string[]>();

  for (const desc of descriptions) {
    const normalized = normalizeDescription(desc);

    // Skip empty normalized results
    if (!normalized) {
      continue;
    }

    // Add to existing group or create new one
    const existing = groups.get(normalized);
    if (existing) {
      existing.push(desc);
    } else {
      groups.set(normalized, [desc]);
    }
  }

  return groups;
}
