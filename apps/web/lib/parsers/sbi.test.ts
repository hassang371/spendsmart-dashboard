import { describe, it, expect } from 'vitest';
import { parseSbiDescription } from './sbi';

describe('SBI Transaction Parser', () => {
  // 1. UPI Transactions
  describe('UPI Transactions', () => {
    it('parses outgoing UPI debit correctly', () => {
      const raw =
        'WDL TFR UPI/DR/931523643407/SHAIK YA/SBIN/skya smeen1/Paym... AT 04413 PBB NELLORE';
      const result = parseSbiDescription(raw);
      expect(result).toEqual({
        merchant: 'SHAIK YA',
        cleanDescription: 'UPI Transfer to SHAIK YA',
        type: 'upi',
        meta: {
          utr: '931523643407',
          bank: 'SBIN',
          mode: 'DR',
          app: 'Paym',
        },
      });
    });

    it('parses incoming UPI credit correctly', () => {
      const raw =
        'DEP TFR UPI/CR/320278741671/SHAIK YA/SBIN/skya smeen1/Paym... AT 04413 PBB NELLORE';
      const result = parseSbiDescription(raw);
      expect(result).toEqual({
        merchant: 'SHAIK YA',
        cleanDescription: 'UPI Received from SHAIK YA',
        type: 'upi',
        meta: {
          utr: '320278741671',
          bank: 'SBIN',
          mode: 'CR',
          app: 'Paym',
        },
      });
    });
  });

  // 2. POS / Card Transactions
  describe('POS Transactions', () => {
    it('parses POS purchase correctly', () => {
      const raw = 'POS ATM PURCH OTHPG 3155010693 17Pho*PHONEPE RECHARGE BANGALORE';
      const result = parseSbiDescription(raw);
      expect(result).toEqual({
        merchant: 'PhonePe',
        cleanDescription: 'POS Purchase at PhonePe (BANGALORE)',
        type: 'pos',
        meta: {
          ref: '3155010693',
          location: 'BANGALORE',
          gateway: 'OTHPG',
        },
      });
    });
  });

  // 3. ATM Withdrawals
  describe('ATM Withdrawals', () => {
    it('parses ATM withdrawal correctly', () => {
      const raw = 'ATM WDL ATM CASH 1957 SP OFFICE DARGAMITTA, NELLORE';
      const result = parseSbiDescription(raw);
      expect(result).toEqual({
        merchant: 'ATM Withdrawal', // Or "Self"
        cleanDescription: 'ATM Cash Withdrawal at OFFICE DARGAMITTA, NELLORE',
        type: 'atm',
        meta: {
          atmId: '1957 SP',
          location: 'OFFICE DARGAMITTA, NELLORE',
        },
      });
    });
  });

  // 4. Internet Banking
  describe('Internet Banking', () => {
    it('parses INB transfer correctly', () => {
      const raw = 'WDL TFR INB Amazon Seller Services Pv... AT 04413 PBB NELLORE';
      const result = parseSbiDescription(raw);
      expect(result).toEqual({
        merchant: 'Amazon',
        cleanDescription: 'Online Transfer to Amazon',
        type: 'inb',
        meta: {},
      });
    });

    it('parses INB with purpose correctly', () => {
      const raw = 'WDL TFR INB Gift to relatives / Friends... AT 04413 PBB NELLORE';
      const result = parseSbiDescription(raw);
      expect(result).toEqual({
        merchant: 'Gift to relatives / Friends',
        cleanDescription: 'Online Transfer: Gift to relatives / Friends',
        type: 'inb',
        meta: {},
      });
    });
  });

  // 5. Cash Deposits
  describe('Cash Deposits', () => {
    it('parses self cash deposit correctly', () => {
      const raw = 'CASH DEPOSIT SELF AT 04413 PBB NELLORE';
      const result = parseSbiDescription(raw);
      expect(result).toEqual({
        merchant: 'Self Deposit',
        cleanDescription: 'Cash Deposit at 04413 PBB NELLORE',
        type: 'cash_deposit',
        meta: {
          branch: '04413 PBB NELLORE',
        },
      });
    });

    it('parses CDM deposit correctly', () => {
      const raw = 'CEMTEX DEP 00000004413 0 40623';
      const result = parseSbiDescription(raw);
      expect(result).toEqual({
        merchant: 'Cash Deposit Machine',
        cleanDescription: 'CDM Deposit (Ref: 00000004413)',
        type: 'cash_deposit',
        meta: {
          ref: '00000004413',
        },
      });
    });
  });

  // Default Fallback
  describe('Fallback', () => {
    it('handles unknown formats gracefully', () => {
      const raw = 'SOME RANDOM STRING 123';
      const result = parseSbiDescription(raw);
      expect(result).toEqual({
        merchant: 'Unknown',
        cleanDescription: 'SOME RANDOM STRING 123',
        type: 'unknown',
        meta: {},
      });
    });
  });
});
