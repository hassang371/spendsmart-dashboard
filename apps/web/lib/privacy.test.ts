import { describe, it, expect } from 'vitest';
import { anonymizeTransaction, anonymizeDataset, Transaction } from './privacy';

describe('Privacy Utilities', () => {
  const mockTransaction: Transaction = {
    id: 'tx-123',
    amount: 150.5,
    transaction_date: '2024-01-15',
    merchant_name: 'Starbucks Coffee',
    description: 'Coffee purchase',
    category: 'Food & Drink',
    user_id: 'user-456',
  };

  describe('anonymizeTransaction', () => {
    it('should strip user_id from transaction', () => {
      const result = anonymizeTransaction(mockTransaction);

      expect(result).not.toHaveProperty('user_id');
      expect(result.amount).toBe(150.5);
      expect(result.category).toBe('Food & Drink');
    });

    it('should keep essential fields', () => {
      const result = anonymizeTransaction(mockTransaction);

      expect(result.amount).toBe(150.5);
      expect(result.date).toBe('2024-01-15');
      expect(result.category).toBe('Food & Drink');
      expect(result.merchant).toBe('Starbucks Coffee');
    });

    it('should mask merchant name when maskMerchant option is true', () => {
      const result = anonymizeTransaction(mockTransaction, { maskMerchant: true });

      expect(result.merchant).toBe('Food & Drink_Merchant');
    });

    it('should not mask merchant name by default', () => {
      const result = anonymizeTransaction(mockTransaction);

      expect(result.merchant).toBe('Starbucks Coffee');
    });

    it('should scrub emails from description', () => {
      const txWithEmail: Transaction = {
        ...mockTransaction,
        description: 'Payment from john.doe@example.com for services',
      };

      const result = anonymizeTransaction(txWithEmail, { scrubDescription: true });

      expect(result.description).toBe('Payment from [EMAIL_REDACTED] for services');
    });

    it('should scrub phone numbers from description', () => {
      const txWithPhone: Transaction = {
        ...mockTransaction,
        description: 'Call 555-123-4567 for details',
      };

      const result = anonymizeTransaction(txWithPhone, { scrubDescription: true });

      expect(result.description).toBe('Call [PHONE_REDACTED] for details');
    });

    it('should scrub both emails and phone numbers', () => {
      const txWithPii: Transaction = {
        ...mockTransaction,
        description: 'Contact jane@company.com or 555.123.4567',
      };

      const result = anonymizeTransaction(txWithPii, { scrubDescription: true });

      expect(result.description).toBe('Contact [EMAIL_REDACTED] or [PHONE_REDACTED]');
    });

    it('should not scrub description when scrubDescription is false', () => {
      const txWithEmail: Transaction = {
        ...mockTransaction,
        description: 'Payment from john.doe@example.com',
      };

      const result = anonymizeTransaction(txWithEmail, { scrubDescription: false });

      expect(result.description).toBe('Payment from john.doe@example.com');
    });

    it('should handle empty description', () => {
      const txWithoutDesc: Transaction = {
        ...mockTransaction,
        description: undefined,
      };

      const result = anonymizeTransaction(txWithoutDesc);

      expect(result.description).toBeUndefined();
    });

    it('should handle description with no PII', () => {
      const result = anonymizeTransaction(mockTransaction, { scrubDescription: true });

      expect(result.description).toBe('Coffee purchase');
    });

    it('should use correct date field mapping', () => {
      const result = anonymizeTransaction(mockTransaction);

      expect(result.date).toBe(mockTransaction.transaction_date);
    });
  });

  describe('anonymizeDataset', () => {
    it('should anonymize multiple transactions', () => {
      const transactions: Transaction[] = [
        mockTransaction,
        {
          ...mockTransaction,
          id: 'tx-124',
          merchant_name: 'Amazon',
          amount: 500,
        },
      ];

      const results = anonymizeDataset(transactions);

      expect(results).toHaveLength(2);
      expect(results[0].merchant).toBe('Starbucks Coffee');
      expect(results[1].merchant).toBe('Amazon');
    });

    it('should apply options to all transactions', () => {
      const transactions: Transaction[] = [
        mockTransaction,
        {
          ...mockTransaction,
          id: 'tx-124',
          merchant_name: 'Amazon',
        },
      ];

      const results = anonymizeDataset(transactions, { maskMerchant: true });

      expect(results[0].merchant).toBe('Food & Drink_Merchant');
      expect(results[1].merchant).toBe('Food & Drink_Merchant');
    });

    it('should handle empty array', () => {
      const results = anonymizeDataset([]);

      expect(results).toEqual([]);
    });

    it('should handle transactions with PII in descriptions', () => {
      const transactions: Transaction[] = [
        {
          ...mockTransaction,
          description: 'Payment to user@example.com',
        },
        {
          ...mockTransaction,
          id: 'tx-125',
          description: 'Call 555-123-4567',
        },
      ];

      const results = anonymizeDataset(transactions, { scrubDescription: true });

      expect(results[0].description).toBe('Payment to [EMAIL_REDACTED]');
      expect(results[1].description).toBe('Call [PHONE_REDACTED]');
    });
  });
});
