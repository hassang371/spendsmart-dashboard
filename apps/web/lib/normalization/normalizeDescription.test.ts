/**
 * Tests for transaction description normalization
 *
 * These tests define the expected behavior for normalizing transaction
 * descriptions to reduce duplicate API calls to the classifier.
 *
 * @see docs/plans/2026-02-14-hybrid-import-architecture.md
 */

import { describe, it, expect } from 'vitest';
import { normalizeDescription, normalizeBatch } from './normalizeDescription';

describe('normalizeDescription', () => {
  describe('order number normalization', () => {
    it('normalizes Swiggy order numbers', () => {
      expect(normalizeDescription('SWIGGY ORDER #12345')).toBe('swiggy order #ORDER');
      expect(normalizeDescription('SWIGGY ORDER #67890')).toBe('swiggy order #ORDER');
    });

    it('normalizes Zomato order numbers', () => {
      expect(normalizeDescription('ZOMATO ORDER #12345')).toBe('zomato order #ORDER');
    });

    it('normalizes Amazon order numbers with different formats', () => {
      expect(normalizeDescription('AMAZON ORDER #123-4567890-1234567')).toBe('amazon order #ORDER');
      expect(normalizeDescription('AMAZON ORDER #171-2345678-3456789')).toBe('amazon order #ORDER');
    });
  });

  describe('transaction ID normalization', () => {
    it('normalizes Amazon transaction IDs', () => {
      expect(normalizeDescription('AMAZON IN TXN_12345')).toBe('amazon in txn_XXXXX');
      expect(normalizeDescription('AMAZON IN TXN_67890')).toBe('amazon in txn_XXXXX');
    });

    it('normalizes UPI transaction references', () => {
      expect(normalizeDescription('UPI/PAYTM/123456789')).toBe('upi/paytm/XXXXXXXXX');
      expect(normalizeDescription('UPI/PAYTM/987654321')).toBe('upi/paytm/XXXXXXXXX');
    });
  });

  describe('UPI ID normalization', () => {
    it('normalizes UPI IDs with merchant name', () => {
      expect(normalizeDescription('UPI-SWIGGY-12345@ybl')).toBe('upi-swiggy-XXXXX@ybl');
      expect(normalizeDescription('UPI-ZOMATO-67890@ybl')).toBe('upi-zomato-XXXXX@ybl');
    });

    it('normalizes UPI IDs with different handles', () => {
      expect(normalizeDescription('SWIGGY-12345@okaxis')).toBe('swiggy-XXXXX@okaxis');
      expect(normalizeDescription('ZOMATO-67890@okicici')).toBe('zomato-XXXXX@okicici');
    });
  });

  describe('merchant name preservation', () => {
    it('preserves merchant names in normalized output', () => {
      expect(normalizeDescription('SWIGGY INSTAMART ORDER #12345')).toBe(
        'swiggy instamart order #ORDER'
      );
      expect(normalizeDescription('BIGBASKET ORDER #67890')).toBe('bigbasket order #ORDER');
    });

    it('preserves location information', () => {
      expect(normalizeDescription('SWIGGY BANGALORE ORDER #12345')).toBe(
        'swiggy bangalore order #ORDER'
      );
    });
  });

  describe('edge cases', () => {
    it('handles empty string', () => {
      expect(normalizeDescription('')).toBe('');
    });

    it('handles null input', () => {
      expect(normalizeDescription(null as unknown as string)).toBe('');
    });

    it('handles undefined input', () => {
      expect(normalizeDescription(undefined as unknown as string)).toBe('');
    });

    it('handles whitespace-only input', () => {
      expect(normalizeDescription('   ')).toBe('');
    });

    it('handles descriptions without numbers', () => {
      expect(normalizeDescription('COFFEE SHOP PURCHASE')).toBe('coffee shop purchase');
    });

    it('handles special characters', () => {
      expect(normalizeDescription("MCDONALD'S ORDER #12345")).toBe("mcdonald's order #ORDER");
    });

    it('handles multiple numbers in description', () => {
      expect(normalizeDescription('ORDER 12345 REF 67890')).toBe('order XXXXX ref XXXXX');
    });
  });

  describe('date normalization', () => {
    it('normalizes dates in DD/MM/YYYY format', () => {
      expect(normalizeDescription('PAYMENT 14/02/2026')).toBe('payment DD/MM/YYYY');
    });

    it('normalizes dates in YYYY-MM-DD format', () => {
      expect(normalizeDescription('PAYMENT 2026-02-14')).toBe('payment YYYY-MM-DD');
    });
  });

  describe('amount normalization', () => {
    it('normalizes currency amounts', () => {
      expect(normalizeDescription('PAYMENT RS.1234.56')).toBe('payment rs. XXXX.XX');
      expect(normalizeDescription('PAYMENT INR 5000.00')).toBe('payment inr XXXX.XX');
    });
  });
});

describe('normalizeBatch', () => {
  it('returns unique normalized descriptions with originals', () => {
    const descriptions = [
      'SWIGGY ORDER #12345',
      'SWIGGY ORDER #67890', // Same normalized form
      'ZOMATO ORDER #11111',
      'AMAZON TXN_99999',
    ];

    const result = normalizeBatch(descriptions);

    // Should have 3 unique normalized forms
    expect(result.size).toBe(3);

    // Each normalized form should map to original descriptions
    expect(result.get('swiggy order #ORDER')).toEqual([
      'SWIGGY ORDER #12345',
      'SWIGGY ORDER #67890',
    ]);
    expect(result.get('zomato order #ORDER')).toEqual(['ZOMATO ORDER #11111']);
    expect(result.get('amazon txn_XXXXX')).toEqual(['AMAZON TXN_99999']);
  });

  it('handles empty array', () => {
    const result = normalizeBatch([]);
    expect(result.size).toBe(0);
  });

  it('handles array with empty strings', () => {
    const result = normalizeBatch(['', 'SWIGGY ORDER #12345', '']);
    expect(result.size).toBe(1);
    expect(result.get('swiggy order #ORDER')).toEqual(['SWIGGY ORDER #12345']);
  });
});
