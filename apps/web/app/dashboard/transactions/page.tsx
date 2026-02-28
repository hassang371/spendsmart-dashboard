'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';
import {
  Search,
  Filter,
  Download,
  X,
  Check,
  Pencil,
  ShoppingBag,
  Coffee,
  Home,
  Zap,
  Car,
  Plane,
  Utensils,
  HeartPulse,
  GraduationCap,
  Gamepad2,
  Gift,
  Briefcase,
  Film,
  Music,
  Shield,
  HelpCircle,
  Banknote,
  TrendingUp,
  Bus,
  Fuel,
  Hammer,
  Stethoscope,
  Landmark,
  ChevronDown,
  Loader2,
  Lock,
  Users,
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { supabase } from '../../../lib/supabase/client';
import { apiClassifyDescriptions, apiSubmitFeedback } from '../../../lib/api/client';
import { parseSbiDescription } from '../../../lib/parsers/sbi';

type TransactionRow = {
  id: string;
  user_id: string;
  transaction_date: string;
  amount: number;
  description: string;
  category: string;
  original_category?: string | null;
  payment_method: string;
  merchant_name: string;
  status: string;
  type: string;
  created_at: string;
  raw_data?: Record<string, any>;
};

type InsertTransaction = {
  user_id: string;
  transaction_date: string;
  amount: number;
  currency: string;
  description: string;
  merchant_name: string;
  category: string;
  original_category?: string | null;
  payment_method: string;
  status: string;
  raw_data: Record<string, unknown>;
};

type RelativeRange =
  | 'none'
  | 'this_week'
  | 'this_month'
  | 'last_30'
  | 'last_90'
  | 'last_180'
  | 'custom';

type FilterState = {
  year: 'all' | string;
  month: 'all' | string;
  relative: RelativeRange;
  customStart: string;
  customEnd: string;
  category: 'all' | string;
  status: 'all' | string;
  minAmount: string;
  maxAmount: string;
  paymentMethod: 'all' | string;
};

type ImportFileKind = 'csv' | 'excel' | 'json' | 'text' | 'pdf' | 'unknown';

const defaultFilters: FilterState = {
  year: 'all',
  month: 'all',
  relative: 'none',
  customStart: '',
  customEnd: '',
  category: 'all',
  status: 'all',
  minAmount: '',
  maxAmount: '',
  paymentMethod: 'all',
};

const monthLookup: Record<string, number> = {
  jan: 0,
  feb: 1,
  mar: 2,
  apr: 3,
  may: 4,
  jun: 5,
  jul: 6,
  aug: 7,
  sep: 8,
  sept: 8,
  oct: 9,
  nov: 10,
  dec: 11,
};

const FETCH_PAGE_SIZE = 1000;
const MAX_FETCH_PAGES = 10;
const MAX_FETCH_ROWS = 10000;
const FETCH_REQUEST_TIMEOUT_MS = 12000;
const MAX_FETCH_DURATION_MS = 45000;
const TRANSACTIONS_CACHE_TTL_MS = 60 * 1000;
const INITIAL_VISIBLE_COUNT = 50;
const LOAD_MORE_STEP = 50;

async function withTimeout<T>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | null = null;
  try {
    return await Promise.race([
      promise,
      new Promise<T>((_, reject) => {
        timer = setTimeout(
          () => reject(new Error(`${label} timed out. Please try again.`)),
          timeoutMs
        );
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function normalizeHeader(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, '');
}

function toText(value: unknown): string {
  if (value === null || value === undefined) return '';
  return String(value).trim();
}

function parseAmount(value: string): number | null {
  const cleaned = value
    .replace(/INR/gi, '')
    .replace(/[₹,\s\u00a0]/g, '')
    .replace(/[()]/g, '');
  if (!cleaned) return null;
  const parsed = Number.parseFloat(cleaned);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeStatus(value: string): string {
  const status = value.trim().toLowerCase();
  if (status.includes('refund')) return 'refunded';
  if (status.includes('cancel')) return 'cancelled';
  if (status.includes('fail')) return 'failed';
  if (status.includes('complete') || status.includes('success')) return 'completed';
  return status || 'completed';
}

function toTitleCase(value: string): string {
  return value
    .toLowerCase()
    .split(' ')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

const knownMerchants: [string, string[]][] = [
  ['Swiggy Instamart', ['swiggy instamart', 'instamart']],
  ['Swiggy', ['swiggy']],
  ['Zomato', ['zomato', 'zomatofo']],
  ['Uber', ['uber', 'uber india']],
  ['Ola', ['ola', 'olacabs']],
  ['Rapido', ['rapido']],
  ['Blinkit', ['blinkit', 'grofers']],
  ['Zepto', ['zepto']],
  ['BigBasket', ['bigbasket', 'big basket']],
  ['Amazon', ['amazon', 'amzn']],
  ['Flipkart', ['flipkart']],
  ['Myntra', ['myntra']],
  ['Ajio', ['ajio']],
  ['Netflix', ['netflix']],
  ['Spotify', ['spotify']],
  ['Youtube', ['youtube', 'google oct']],
  ['Apple', ['apple.com', 'itunes']],
  ['Google', ['google']],
  ['Jio', ['jio', 'reliance jio']],
  ['Airtel', ['airtel']],
  ['Vodafone', ['vi', 'vodafone']],
  ['Mcdonalds', ['mcdonalds', 'mcdonald']],
  ['Starbucks', ['starbucks']],
  ['KFC', ['kfc']],
  ['Burger King', ['burger king']],
  ["Domino's", ['dominos', "domino's"]],
  ['Pizza Hut', ['pizza hut']],
  ['Subway', ['subway']],
];

// Keyword-based category classifier (client-side fallback when HypCD API is unavailable)
const categoryKeywords: [string, string[]][] = [
  [
    'Food',
    [
      'swiggy',
      'zomato',
      'food',
      'restaurant',
      'dining',
      'blinkit',
      'zepto',
      'bigbasket',
      'grofers',
      'mcdonalds',
      'starbucks',
      'kfc',
      'burger king',
      'dominos',
      'pizza hut',
      'subway',
      'grocery',
      'groceries',
    ],
  ],
  [
    'Transport',
    [
      'uber',
      'ola',
      'rapido',
      'taxi',
      'cab',
      'bus',
      'train',
      'metro',
      'fuel',
      'petrol',
      'diesel',
      'parking',
    ],
  ],
  [
    'Utilities',
    [
      'electricity',
      'water',
      'gas',
      'airtel',
      'jio',
      'vodafone',
      'broadband',
      'wifi',
      'bescom',
      'bill',
      'recharge',
    ],
  ],
  ['Shopping', ['amazon', 'flipkart', 'myntra', 'ajio', 'shopping', 'clothing', 'meesho']],
  [
    'Entertainment',
    [
      'netflix',
      'spotify',
      'youtube',
      'hotstar',
      'prime video',
      'movie',
      'cinema',
      'gaming',
      'xbox',
      'playstation',
    ],
  ],
  ['Health', ['medical', 'doctor', 'pharmacy', 'hospital', 'gym', 'apollo', 'health']],
  ['Education', ['course', 'tuition', 'school', 'college', 'udemy', 'coursera', 'education']],
  ['Finance', ['investment', 'loan', 'insurance', 'mutual fund', 'zerodha', 'groww', 'emi', 'sip']],
  [
    'People',
    ['sent to', 'received from', 'upi transfer', 'upi received', 'transfer to', 'friend', 'family'],
  ],
];

function classifyByKeywords(description: string, merchant: string): string {
  const text = `${description} ${merchant}`.toLowerCase();
  for (const [category, keywords] of categoryKeywords) {
    for (const kw of keywords) {
      if (kw.length <= 4 ? new RegExp(`\\b${kw}\\b`).test(text) : text.includes(kw)) {
        return category;
      }
    }
  }
  return 'Uncategorized';
}

function isNoiseSegment(value: string): boolean {
  const cleaned = value.trim();
  if (!cleaned) return true;
  const upper = cleaned.toUpperCase();

  if (/^[A-Z0-9._-]{10,}$/.test(upper)) return true;
  if (/^[0-9]{6,}$/.test(upper)) return true;
  if (/^ICI[A-Z0-9]+$/.test(upper)) return true;
  if (/^[A-Z]{2,5}\d{6,}$/.test(upper)) return true;

  const noiseWords = [
    'UPI',
    'IMPS',
    'NEFT',
    'RTGS',
    'ACH',
    'NACH',
    'CREDIT',
    'DEBIT',
    'PAYMENT',
    'TRANSFER',
    'BANK',
    'AXIS BANK',
    'HDFC BANK',
    'SBI',
    'ICICI',
    'YES BANK',
    'KOTAK',
    'WDL',
    'TFR',
    'POS',
    'MB',
  ];
  return noiseWords.includes(upper);
}

function extractReadableDescription(raw: string): string {
  const source = raw.trim();
  if (!source) return 'Imported transaction';

  const lower = source.toLowerCase();

  // Strategy 1: Known Merchant Matching (Highest Priority)
  for (const [official, aliases] of knownMerchants) {
    if (aliases.some(alias => lower.includes(alias))) {
      return official;
    }
  }

  const normalizedSource = source.replace(/\s+/g, ' ').trim();

  // Strategy 2: Specific UPI/P2P Patterns (High Precision)
  // Pattern: WDL TFR UPI/DR/{digits}/{NAME}/{BANK}/...
  const upiMatch = normalizedSource.match(
    /(?:UPI|UPVDR|UPS|IMPS|NEFT)(?:\/|-)(?:DR|CR)?(?:\/|-)?\d+(?:\/|-)([^/]+)(?:\/|-)/i
  );
  if (upiMatch && upiMatch[1]) {
    const potentialName = upiMatch[1].trim();
    const cleanName = potentialName.replace(/[0-9._-]+$/, '').trim();
    if (cleanName.length > 2 && !/^\d+$/.test(cleanName)) {
      // Check known merchants first
      const ln = cleanName.toLowerCase();
      for (const [official, aliases] of knownMerchants) {
        if (aliases.some(a => ln.includes(a))) return official;
      }
      return toTitleCase(cleanName);
    }
  }

  // Strategy 2.5: POS ATM PURCH patterns (SBI specific)
  // "POS ATM PURCH OTHPG 3157043273 36Swiggy 911311221" → "Swiggy"
  const posMatch = normalizedSource.match(
    /POS\s+ATM\s+PURCH\s+\w+\s+\d+\s*\n?\s*\d*([A-Za-z*]+[A-Za-z\s]*)/i
  );
  if (posMatch && posMatch[1]) {
    let merchant = posMatch[1].replace(/^\d+/, '').replace(/\*/g, '').trim();
    // Remove trailing numeric IDs
    merchant = merchant.replace(/\s+\d+$/, '').trim();
    if (merchant.length > 2) {
      const lm = merchant.toLowerCase();
      for (const [official, aliases] of knownMerchants) {
        if (aliases.some(a => lm.includes(a))) return official;
      }
      return toTitleCase(merchant);
    }
  }

  // Strategy 2.6: DEP TFR VISA-IN-RMT patterns (SBI refund)
  // "DEP TFR VISA-IN-RMT:300710245915SWIGGY" → "Swiggy"
  const depMatch = normalizedSource.match(/DEP\s+TFR\s+VISA-IN-RMT:[0-9]+([A-Za-z]+)/i);
  if (depMatch && depMatch[1]) {
    const name = depMatch[1].trim();
    const ln = name.toLowerCase();
    for (const [official, aliases] of knownMerchants) {
      if (aliases.some(a => ln.includes(a))) return official;
    }
    if (name.length > 2) return toTitleCase(name);
  }

  // Strategy 2.7: ATM WDL patterns
  // "ATM WDL ATM CASH 1957 SP OFFICE DARGAMITTA, NELLORE" → "ATM Withdrawal"
  if (/ATM\s+WDL/i.test(normalizedSource)) {
    return 'ATM Withdrawal';
  }

  // Strategy 2.8: CASH DEPOSIT / CEMTEX DEP patterns
  if (/CASH\s+DEPOSIT/i.test(normalizedSource)) {
    return 'Cash Deposit';
  }
  if (/CEMTEX\s+DEP/i.test(normalizedSource)) {
    // "CEMTEX DEP 00000004413 040623 PHONEPE RECHARGE" → try to find merchant after IDs
    const cemtexClean = normalizedSource
      .replace(/CEMTEX\s+DEP/i, '')
      .replace(/\b\d+\b/g, '')
      .trim();
    if (cemtexClean.length > 2) {
      const lc = cemtexClean.toLowerCase();
      for (const [official, aliases] of knownMerchants) {
        if (aliases.some(a => lc.includes(a))) return official;
      }
      return toTitleCase(cemtexClean);
    }
    return 'Cash Deposit';
  }

  // Strategy 2.9: INB (Internet Banking) patterns
  // "WDL TFR INB Amazon Seller Services..." → "Amazon"
  if (/\bINB\b/i.test(normalizedSource)) {
    const inbClean = normalizedSource
      .replace(/\b(WDL|TFR|INB)\b/gi, '')
      .replace(/\bAT\s+\d+.*/i, '')
      .trim();
    if (inbClean.length > 2) {
      const lc = inbClean.toLowerCase();
      for (const [official, aliases] of knownMerchants) {
        if (aliases.some(a => lc.includes(a))) return official;
      }
      return toTitleCase(inbClean);
    }
  }

  // Strategy 3: Heuristic Cleaning
  if (normalizedSource.includes('/')) {
    const parts = normalizedSource
      .split(/[\/|>]/)
      .map(part => part.trim())
      .filter(Boolean);

    for (const part of parts) {
      if (isNoiseSegment(part)) continue;
      if (part.length < 3) continue;
      if (/@/.test(part)) continue;
      return toTitleCase(part.replace(/[._-]+/g, ' '));
    }
  }

  if (/^[A-Z]{2,5}\.[A-Z0-9-]{8,}$/i.test(normalizedSource)) {
    return 'Card/UPI transaction';
  }

  // Strategy 4: Aggressive Cleaning
  const trimmed = normalizedSource
    .replace(
      /\b(UPI|IMPS|NEFT|RTGS|ACH|NACH|WDL|TFR|POS|MB|DR|CR|DEP|OTHPG|SBIPG|PURCH|ATM)\b/gi,
      ''
    )
    .replace(/[0-9]+/g, ' ')
    .replace(/[^a-zA-Z\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  if (!trimmed) return 'Imported transaction';
  if (trimmed.length <= 64) return toTitleCase(trimmed);
  return `${toTitleCase(trimmed.slice(0, 61).trim())}...`;
}

function parseDateValue(value: string): string | null {
  const raw = value.trim();
  if (!raw) return null;

  const slashDateTime = raw.match(
    /^\s*(\d{1,2})\/(\d{1,2})\/(\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$/
  );
  if (slashDateTime) {
    const day = Number.parseInt(slashDateTime[1], 10);
    const month = Number.parseInt(slashDateTime[2], 10) - 1;
    const yearRaw = Number.parseInt(slashDateTime[3], 10);
    const year = yearRaw < 100 ? 2000 + yearRaw : yearRaw;
    const hour = Number.parseInt(slashDateTime[4] ?? '0', 10);
    const minute = Number.parseInt(slashDateTime[5] ?? '0', 10);
    const second = Number.parseInt(slashDateTime[6] ?? '0', 10);
    const date = new Date(year, month, day, hour, minute, second);
    if (!Number.isNaN(date.getTime())) return date.toISOString();
  }

  const dashDateTime = raw.match(
    /^\s*(\d{1,2})-(\d{1,2})-(\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$/
  );
  if (dashDateTime) {
    const day = Number.parseInt(dashDateTime[1], 10);
    const month = Number.parseInt(dashDateTime[2], 10) - 1;
    const yearRaw = Number.parseInt(dashDateTime[3], 10);
    const year = yearRaw < 100 ? 2000 + yearRaw : yearRaw;
    const hour = Number.parseInt(dashDateTime[4] ?? '0', 10);
    const minute = Number.parseInt(dashDateTime[5] ?? '0', 10);
    const second = Number.parseInt(dashDateTime[6] ?? '0', 10);
    const date = new Date(year, month, day, hour, minute, second);
    if (!Number.isNaN(date.getTime())) return date.toISOString();
  }

  const googleLike = raw.match(/^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4}),\s*(\d{1,2}):(\d{2})$/);
  if (googleLike) {
    const day = Number.parseInt(googleLike[1], 10);
    const monthName = googleLike[2].toLowerCase();
    const year = Number.parseInt(googleLike[3], 10);
    const hour = Number.parseInt(googleLike[4], 10);
    const minute = Number.parseInt(googleLike[5], 10);
    const month = monthLookup[monthName.slice(0, 4)] ?? monthLookup[monthName.slice(0, 3)];
    if (month !== undefined) {
      const date = new Date(year, month, day, hour, minute);
      if (!Number.isNaN(date.getTime())) return date.toISOString();
    }
  }

  const direct = new Date(raw.replace('Sept', 'Sep'));
  if (!Number.isNaN(direct.getTime())) return direct.toISOString();

  const iso = new Date(raw.replace(' ', 'T').replace('Sept', 'Sep'));
  if (!Number.isNaN(iso.getTime())) return iso.toISOString();
  return null;
}

function detectImportFileKind(fileName: string): ImportFileKind {
  const extension = fileName.split('.').pop()?.toLowerCase() ?? '';
  if (extension === 'csv' || extension === 'tsv') return 'csv';
  if (extension === 'xls' || extension === 'xlsx' || extension === 'xlsm') return 'excel';
  if (extension === 'json') return 'json';
  if (extension === 'txt') return 'text';
  if (extension === 'pdf') return 'pdf';
  return 'unknown';
}

function normalizeSpreadsheetRows(rows: Record<string, unknown>[]): Record<string, unknown>[] {
  if (!rows.length) return rows;

  // Known header keywords that indicate a real data header row
  const HEADER_KEYWORDS = [
    'date',
    'txn',
    'transaction',
    'value',
    'description',
    'narration',
    'debit',
    'credit',
    'amount',
    'withdrawal',
    'deposit',
    'balance',
    'ref',
    'chq',
    'cheque',
    'particulars',
    'remark',
  ];

  const looksLikeHeaderValue = (val: string): boolean => {
    const lower = val.toLowerCase().trim();
    return HEADER_KEYWORDS.some(kw => lower.includes(kw));
  };

  const firstKeys = Object.keys(rows[0]);
  const allKeysEmpty = firstKeys.length > 0 && firstKeys.every(key => key.startsWith('__EMPTY'));

  // Check if XLSX already extracted good headers (no __EMPTY, and keys look like real headers)
  const existingHeadersLookGood = !allKeysEmpty && firstKeys.some(key => looksLikeHeaderValue(key));

  if (existingHeadersLookGood) return rows;

  // Headers are bad (all __EMPTY or metadata-as-headers like bank name / customer name).
  // Scan through rows to find the actual header row by looking for known keywords in cell values.
  let headerRowIndex = -1;
  const maxScanRows = Math.min(rows.length, 30); // Don't scan beyond first 30 rows

  for (let i = 0; i < maxScanRows; i++) {
    const row = rows[i];
    const values = Object.values(row).map(v => toText(v));
    const headerMatchCount = values.filter(v => looksLikeHeaderValue(v)).length;
    // At least 2 header-looking values → this is likely the header row
    if (headerMatchCount >= 2) {
      headerRowIndex = i;
      break;
    }
  }

  if (headerRowIndex === -1) {
    // Fallback: if all keys are __EMPTY, use the first row values as headers (original behavior)
    if (allKeysEmpty) {
      const dynamicHeaders = firstKeys.map((key, index) => {
        const value = toText(rows[0][key]);
        return value || `column_${index + 1}`;
      });
      return rows
        .slice(1)
        .map(row => {
          const normalized: Record<string, unknown> = {};
          firstKeys.forEach((key, index) => {
            normalized[dynamicHeaders[index]] = row[key];
          });
          return normalized;
        })
        .filter(row => Object.values(row).some(value => toText(value) !== ''));
    }
    return rows;
  }

  // Found the header row — use its values as column names
  const headerRow = rows[headerRowIndex];
  const newHeaders = firstKeys.map((key, index) => {
    const value = toText(headerRow[key]);
    return value || `column_${index + 1}`;
  });

  // Everything after the header row is data
  return rows
    .slice(headerRowIndex + 1)
    .map(row => {
      const normalized: Record<string, unknown> = {};
      firstKeys.forEach((key, index) => {
        normalized[newHeaders[index]] = row[key];
      });
      return normalized;
    })
    .filter(row => Object.values(row).some(value => toText(value) !== ''));
}

function parseTableText(text: string): Record<string, unknown>[] {
  const lines = text
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean);

  if (!lines.length) return [];

  const delimiters = [',', '\t', '|', ';'];
  let selectedDelimiter = ',';
  let bestScore = -1;
  const headerLine = lines[0];
  for (const delimiter of delimiters) {
    const score = headerLine.split(delimiter).length;
    if (score > bestScore) {
      bestScore = score;
      selectedDelimiter = delimiter;
    }
  }

  const parsed = Papa.parse<Record<string, unknown>>(lines.join('\n'), {
    header: true,
    skipEmptyLines: true,
    delimiter: selectedDelimiter,
  });

  return parsed.data;
}

async function parseFileRows(
  file: File
): Promise<{ rows: Record<string, unknown>[]; fileKind: ImportFileKind }> {
  const fileKind = detectImportFileKind(file.name);

  if (fileKind === 'csv') {
    const text = await file.text();
    const rows = parseTableText(text);
    return { rows, fileKind };
  }

  if (fileKind === 'excel') {
    const buffer = await file.arrayBuffer();
    const workbook = XLSX.read(buffer, { type: 'array', cellDates: false, raw: false });
    const sheetName = workbook.SheetNames[0];
    if (!sheetName) return { rows: [], fileKind };

    const worksheet = workbook.Sheets[sheetName];
    const rawRows = XLSX.utils.sheet_to_json<Record<string, unknown>>(worksheet, {
      defval: '',
      raw: false,
    });
    return { rows: normalizeSpreadsheetRows(rawRows), fileKind };
  }

  if (fileKind === 'json') {
    const text = await file.text();
    let json: unknown;
    try {
      json = JSON.parse(text);
    } catch {
      throw new Error('Invalid JSON file. Please check the file format.');
    }

    let rawRows: unknown[] = [];
    if (Array.isArray(json)) {
      rawRows = json;
    } else if (
      json &&
      typeof json === 'object' &&
      Array.isArray((json as { transactions?: unknown[] }).transactions)
    ) {
      rawRows = (json as { transactions: unknown[] }).transactions;
    }

    // Validate that each row is a plain object
    const validRows = rawRows.filter(
      (row): row is Record<string, unknown> =>
        row !== null && typeof row === 'object' && !Array.isArray(row)
    );

    if (rawRows.length > 0 && validRows.length === 0) {
      throw new Error('JSON file contains no valid transaction objects.');
    }

    return { rows: validRows, fileKind };
  }

  if (fileKind === 'text' || fileKind === 'pdf') {
    const text = await file.text();
    return { rows: parseTableText(text), fileKind };
  }

  return { rows: [], fileKind };
}

function categoryIcon(category: string) {
  const cat = category.toLowerCase().trim();

  // Income / Business
  if (cat === 'income' || cat === 'salary')
    return <Banknote className="h-4 w-4 text-emerald-500" />;
  if (cat.includes('business') || cat.includes('freelance'))
    return <Briefcase className="h-4 w-4 text-blue-500" />;
  if (cat.includes('invest')) return <TrendingUp className="h-4 w-4 text-purple-500" />;

  // Essentials
  if (cat === 'food' || cat.includes('grocer'))
    return <Utensils className="h-4 w-4 text-orange-500" />;
  if (cat.includes('dining') || cat.includes('restaurant'))
    return <Coffee className="h-4 w-4 text-orange-600" />;
  if (cat === 'housing' || cat === 'rent') return <Home className="h-4 w-4 text-indigo-500" />;
  if (cat.includes('utility') || cat.includes('bill') || cat.includes('electric'))
    return <Zap className="h-4 w-4 text-yellow-500" />;

  // Transportation
  if (cat === 'transport' || cat.includes('taxi') || cat.includes('uber'))
    return <Car className="h-4 w-4 text-blue-400" />;
  if (cat.includes('fuel') || cat.includes('gas')) return <Fuel className="h-4 w-4 text-red-400" />;
  if (cat.includes('flight') || cat.includes('travel'))
    return <Plane className="h-4 w-4 text-sky-500" />;
  if (cat.includes('bus') || cat.includes('train'))
    return <Bus className="h-4 w-4 text-blue-300" />;

  // Shopping & Entertainment
  if (cat === 'shopping' || cat.includes('cloth'))
    return <ShoppingBag className="h-4 w-4 text-pink-500" />;
  if (cat.includes('entertainment') || cat.includes('movie'))
    return <Film className="h-4 w-4 text-purple-400" />;
  if (cat.includes('game') || cat.includes('steam'))
    return <Gamepad2 className="h-4 w-4 text-violet-500" />;
  if (cat.includes('music') || cat.includes('spotify'))
    return <Music className="h-4 w-4 text-green-500" />;
  if (cat.includes('gift') || cat.includes('donation'))
    return <Gift className="h-4 w-4 text-rose-400" />;
  if (cat === 'people' || cat.includes('friend') || cat.includes('family'))
    return <Users className="h-4 w-4 text-pink-500" />;

  // Health & Education
  if (cat === 'health' || cat.includes('medical') || cat.includes('doctor'))
    return <Stethoscope className="h-4 w-4 text-red-500" />;
  if (cat.includes('fitness') || cat.includes('gym'))
    return <HeartPulse className="h-4 w-4 text-rose-500" />;
  if (cat === 'education' || cat.includes('course') || cat.includes('book'))
    return <GraduationCap className="h-4 w-4 text-blue-600" />;

  // Finance & Misc
  if (cat.includes('bank') || cat.includes('transfer'))
    return <Landmark className="h-4 w-4 text-slate-500" />;
  if (cat.includes('insurance')) return <Shield className="h-4 w-4 text-teal-500" />;
  if (cat.includes('service') || cat.includes('subscription'))
    return <Hammer className="h-4 w-4 text-gray-500" />;
  if (cat.includes('repair')) return <Hammer className="h-4 w-4 text-amber-600" />;

  return <HelpCircle className="h-4 w-4 text-muted-foreground" />;
}

function inRelativeRange(date: Date, filters: FilterState): boolean {
  if (filters.relative === 'none') return true;
  const now = new Date();
  const start = new Date();
  start.setHours(0, 0, 0, 0);

  if (filters.relative === 'this_week') {
    const day = start.getDay() || 7;
    start.setDate(start.getDate() - (day - 1));
    return date >= start && date <= now;
  }
  if (filters.relative === 'this_month') {
    start.setDate(1);
    return date >= start && date <= now;
  }
  if (filters.relative === 'last_30') {
    start.setDate(now.getDate() - 30);
    return date >= start && date <= now;
  }
  if (filters.relative === 'last_90') {
    start.setDate(now.getDate() - 90);
    return date >= start && date <= now;
  }
  if (filters.relative === 'last_180') {
    start.setDate(now.getDate() - 180);
    return date >= start && date <= now;
  }
  if (filters.relative === 'custom') {
    if (!filters.customStart || !filters.customEnd) return true;
    const customStart = new Date(filters.customStart);
    const customEnd = new Date(filters.customEnd);
    customStart.setHours(0, 0, 0, 0);
    customEnd.setHours(23, 59, 59, 999);
    return date >= customStart && date <= customEnd;
  }
  return true;
}

function monthName(index: number): string {
  return [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ][index];
}

export default function TransactionsPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [importProgress, setImportProgress] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Password Handling
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [passwordInput, setPasswordInput] = useState('');
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [transactions, setTransactions] = useState<TransactionRow[]>([]);
  const [userId, setUserId] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState<'all' | 'debit' | 'credit'>('all');
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [draftFilters, setDraftFilters] = useState<FilterState>(defaultFilters);
  const [filters, setFilters] = useState<FilterState>(defaultFilters);
  const [selected, setSelected] = useState<TransactionRow | null>(null);

  const [editingCategoryTxId, setEditingCategoryTxId] = useState<string | null>(null);
  const [editingCategoryValue, setEditingCategoryValue] = useState<string>('Misc');
  const [updatingCategory, setUpdatingCategory] = useState(false);
  const [reclassifyTarget, setReclassifyTarget] = useState<TransactionRow | null>(null);
  const [reclassifySimilar, setReclassifySimilar] = useState<TransactionRow[]>([]);
  const [reclassifyCategory, setReclassifyCategory] = useState<string>('Misc');
  const [reclassifying, setReclassifying] = useState(false);
  const [consumedOpenTxId, setConsumedOpenTxId] = useState<string | null>(null);
  const [spotlightTxId, setSpotlightTxId] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(INITIAL_VISIBLE_COUNT);

  // Reset pagination when filters change
  useEffect(() => {
    setVisibleCount(INITIAL_VISIBLE_COUNT);
    listRef.current?.scrollTo({ top: 0, behavior: 'auto' });
  }, [tab, search, filters]);

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => setMessage(null), 3500);
    return () => clearTimeout(timer);
  }, [message]);

  useEffect(() => {
    if (!error) return;
    const timer = setTimeout(() => setError(null), 4500);
    return () => clearTimeout(timer);
  }, [error]);

  // Scroll to top when tab changes
  useEffect(() => {
    listRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }, [tab]);

  // After refetch/import, reset list viewport so rows are visible immediately.
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      if (listRef.current) {
        listRef.current.scrollTop = 0;
      }
    });

    return () => cancelAnimationFrame(frame);
  }, [transactions.length]);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (!target) return;

      if (isFilterOpen) {
        const insideFilter = target.closest('[data-filter-panel="true"]');
        const filterTrigger = target.closest('[data-filter-trigger="true"]');
        if (!insideFilter && !filterTrigger) {
          setIsFilterOpen(false);
        }
      }

      if (editingCategoryTxId) {
        const insideCategoryEditor = target.closest('[data-category-editor="true"]');
        const categoryEditTrigger = target.closest('[data-category-edit-trigger="true"]');
        if (!insideCategoryEditor && !categoryEditTrigger) {
          setEditingCategoryTxId(null);
        }
      }
    };

    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [isFilterOpen, editingCategoryTxId]);

  const fetchTransactions = useCallback(async () => {
    const userLookup = await withTimeout<{
      data: { user: { id: string } | null };
      error: { message?: string } | null;
    }>(
      supabase.auth
        .getUser()
        .then(
          (result: {
            data: { user: { id: string } | null };
            error: { message: string } | null;
          }) => ({
            data: { user: result.data.user ? { id: result.data.user.id } : null },
            error: result.error ? { message: result.error.message } : null,
          })
        ),
      8000,
      'User session lookup'
    );

    const {
      data: { user },
      error: userError,
    } = userLookup;

    if (userError || !user) {
      router.replace('/login');
      return;
    }

    setUserId(user.id);

    const cacheKey = `transactions-cache:${user.id}`;
    const cachedRaw = sessionStorage.getItem(cacheKey);
    if (cachedRaw) {
      try {
        const cached = JSON.parse(cachedRaw) as { timestamp: number; rows: TransactionRow[] };
        if (
          Date.now() - cached.timestamp < TRANSACTIONS_CACHE_TTL_MS &&
          Array.isArray(cached.rows)
        ) {
          setTransactions(cached.rows);
          setLoading(false);
        }
      } catch {
        // ignore JSON parse error
      }
    }

    const allRows: Record<string, unknown>[] = [];
    const seenIds = new Set<string>();
    const seenPageSignatures = new Set<string>();
    const startedAt = Date.now();
    let from = 0;
    let pagesFetched = 0;
    let truncated = false;

    while (true) {
      if (pagesFetched >= MAX_FETCH_PAGES || allRows.length >= MAX_FETCH_ROWS) {
        truncated = true;
        break;
      }

      if (Date.now() - startedAt > MAX_FETCH_DURATION_MS) {
        truncated = true;
        break;
      }

      const to = from + FETCH_PAGE_SIZE - 1;
      const pageResponse = await withTimeout<{
        data: Record<string, unknown>[];
        errorMessage: string | null;
      }>(
        supabase
          .from('transactions')
          .select(
            'id,user_id,transaction_date,amount,description,merchant_name,category,original_category,payment_method,status,currency,type,created_at,raw_data'
          )
          .eq('user_id', user.id)
          .order('transaction_date', { ascending: false })
          .range(from, to)
          .then((response: { data: unknown[] | null; error: { message: string } | null }) => ({
            data: (response.data ?? []) as Record<string, unknown>[],
            errorMessage: response.error?.message ?? null,
          })),
        FETCH_REQUEST_TIMEOUT_MS,
        'Transactions fetch'
      );

      const txError = pageResponse.errorMessage;

      if (txError) throw new Error(txError);

      const pageRows = pageResponse.data;
      if (!pageRows.length) break;

      const firstId = toText(pageRows[0]?.id);
      const lastId = toText(pageRows[pageRows.length - 1]?.id);
      const pageSignature = `${firstId}|${lastId}|${pageRows.length}`;
      if (seenPageSignatures.has(pageSignature)) {
        break;
      }
      seenPageSignatures.add(pageSignature);

      let newRowsAdded = 0;
      for (const row of pageRows) {
        const rowId = toText(row.id);
        if (rowId && seenIds.has(rowId)) continue;
        if (rowId) seenIds.add(rowId);
        allRows.push(row);
        newRowsAdded += 1;
      }

      if (newRowsAdded === 0 || pageRows.length < FETCH_PAGE_SIZE) break;

      from += FETCH_PAGE_SIZE;
      pagesFetched += 1;
    }

    const mappedTransactions = allRows.map(row => {
      const merchantName = toText(row.merchant_name);
      const rawDescription = toText(row.description) || merchantName || 'Imported transaction';
      // Trust the merchant_name if it exists (set by API with proper extraction)
      // Only run extractReadableDescription on raw description as fallback
      const displayDescription = merchantName || extractReadableDescription(rawDescription);

      return {
        id: toText(row.id) ?? '',
        user_id: toText(row.user_id) ?? '',
        transaction_date: toText(row.transaction_date) ?? new Date().toISOString(),
        amount: Number(row.amount) || 0,
        description: displayDescription,
        merchant_name: merchantName || 'Unknown Merchant',
        category: toText(row.category) || 'Uncategorized',
        original_category: toText(row.original_category),
        payment_method: toText(row.payment_method) || 'Cash',
        status: toText(row.status) || 'completed',
        type: toText(row.type) || (Number(row.amount) >= 0 ? 'credit' : 'debit'),
        created_at: toText(row.created_at) || new Date().toISOString(),
        raw_data: (row.raw_data as Record<string, any>) || {},
      };
    });

    setTransactions(mappedTransactions);
    sessionStorage.setItem(
      cacheKey,
      JSON.stringify({
        timestamp: Date.now(),
        rows: mappedTransactions,
      })
    );

    if (truncated) {
      setMessage(
        `Loaded ${allRows.length.toLocaleString(
          'en-IN'
        )} recent transactions. Narrow filters or refresh to load more.`
      );
    }
  }, [router]);

  useEffect(() => {
    let mounted = true;
    let finished = false;
    const spinnerGuard = setTimeout(() => {
      if (!mounted || finished) return;
      setError(
        'Loading transactions is taking longer than expected. Please refresh and try again.'
      );
      setLoading(false);
    }, 20000);

    (async () => {
      try {
        await fetchTransactions();
      } catch (fetchError) {
        if (mounted) {
          setError(
            fetchError instanceof Error ? fetchError.message : 'Unable to load transactions.'
          );
        }
      } finally {
        finished = true;
        if (mounted) setLoading(false);
      }
    })();

    return () => {
      mounted = false;
      clearTimeout(spinnerGuard);
    };
  }, [fetchTransactions]);

  const categories = useMemo(() => {
    const values = new Set<string>();
    for (const tx of transactions) {
      if (tx.category) values.add(tx.category);
    }
    return ['all', ...Array.from(values).sort((a, b) => a.localeCompare(b))];
  }, [transactions]);

  const categoryOptions = useMemo(() => {
    const defaults = [
      'Food',
      'Grocery',
      'Shopping',
      'Transport',
      'Utilities',
      'Subscriptions',
      'Healthcare',
      'Education',
      'Entertainment',
      'Finance',
      'Income',
      'People',
      'Misc',
    ];
    const set = new Set(defaults);
    for (const tx of transactions) {
      if (tx.category) set.add(tx.category);
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [transactions]);

  const years = useMemo(() => {
    const values = new Set<string>();
    for (const tx of transactions) {
      const d = new Date(tx.transaction_date);
      if (!Number.isNaN(d.getTime())) values.add(String(d.getFullYear()));
    }
    return ['all', ...Array.from(values).sort((a, b) => Number(b) - Number(a))];
  }, [transactions]);

  const filteredBase = useMemo(() => {
    return transactions.filter(tx => {
      const date = new Date(tx.transaction_date);
      if (Number.isNaN(date.getTime())) return false;

      const q = search.trim().toLowerCase();
      if (q) {
        const haystack = [
          tx.description,
          tx.merchant_name,
          tx.category,
          tx.payment_method,
          tx.status,
        ]
          .map(v => (v ?? '').toLowerCase())
          .join(' ');
        if (!haystack.includes(q)) return false;
      }

      if (filters.year !== 'all' && String(date.getFullYear()) !== filters.year) return false;
      if (
        filters.year !== 'all' &&
        filters.month !== 'all' &&
        String(date.getMonth()) !== filters.month
      )
        return false;
      if (!inRelativeRange(date, filters)) return false;
      if (filters.category !== 'all' && (tx.category ?? '') !== filters.category) return false;
      if (filters.status !== 'all' && normalizeStatus(tx.status ?? '') !== filters.status)
        return false;
      if (filters.paymentMethod !== 'all' && (tx.payment_method ?? '') !== filters.paymentMethod)
        return false;

      const absAmount = Math.abs(Number(tx.amount || 0));
      const min = filters.minAmount ? Number.parseFloat(filters.minAmount) : null;
      const max = filters.maxAmount ? Number.parseFloat(filters.maxAmount) : null;
      if (min !== null && Number.isFinite(min) && absAmount < min) return false;
      if (max !== null && Number.isFinite(max) && absAmount > max) return false;
      return true;
    });
  }, [transactions, search, filters]);

  const tabCounts = useMemo(() => {
    const debit = filteredBase.filter(tx => Number(tx.amount) < 0).length;
    const credit = filteredBase.filter(tx => Number(tx.amount) >= 0).length;
    return { all: filteredBase.length, debit, credit };
  }, [filteredBase]);

  const filteredTransactions = useMemo(() => {
    if (tab === 'debit') return filteredBase.filter(tx => Number(tx.amount) < 0);
    if (tab === 'credit') return filteredBase.filter(tx => Number(tx.amount) >= 0);
    return filteredBase;
  }, [filteredBase, tab]);

  const groupedTransactions = useMemo(() => {
    const map = new Map<string, TransactionRow[]>();
    for (const tx of filteredTransactions) {
      const d = new Date(tx.transaction_date);
      const key = `${d.getFullYear()}-${d.getMonth()}`;
      const existing = map.get(key) ?? [];
      existing.push(tx);
      map.set(key, existing);
    }

    return Array.from(map.entries())
      .map(([key, rows]) => {
        const [yearRaw, monthRaw] = key.split('-');
        const year = Number(yearRaw);
        const month = Number(monthRaw);
        const spent = rows
          .filter(r => Number(r.amount) < 0)
          .reduce((sum, r) => sum + Math.abs(Number(r.amount)), 0);
        const credited = rows
          .filter(r => Number(r.amount) >= 0)
          .reduce((sum, r) => sum + Number(r.amount), 0);
        const net = rows.reduce((sum, r) => sum + Number(r.amount), 0);
        rows.sort(
          (a, b) => new Date(b.transaction_date).getTime() - new Date(a.transaction_date).getTime()
        );
        return { key, year, month, spent, credited, net, rows };
      })
      .sort((a, b) => (a.year !== b.year ? b.year - a.year : b.month - a.month));
  }, [filteredTransactions]);

  const visibleGroups = useMemo(() => {
    let currentCount = 0;
    const result = [];

    for (const group of groupedTransactions) {
      if (currentCount >= visibleCount) break;

      const remaining = visibleCount - currentCount;
      if (remaining >= group.rows.length) {
        result.push(group);
        currentCount += group.rows.length;
      } else {
        result.push({ ...group, rows: group.rows.slice(0, remaining) });
        currentCount += remaining;
      }
    }
    return result;
  }, [groupedTransactions, visibleCount]);

  const applyFilters = () => {
    setFilters(draftFilters);
    setIsFilterOpen(false);
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const openTxId = params.get('openTx') || params.get('highlight');
    if (!openTxId || openTxId === consumedOpenTxId || transactions.length === 0) return;

    const match = transactions.find(tx => tx.id === openTxId);
    if (!match) return;

    setTab('all');
    setSearch('');
    setFilters(defaultFilters);
    setDraftFilters(defaultFilters);
    setSelected(match);
    setSpotlightTxId(openTxId);
    scrollToTransactionRow(openTxId);
    setConsumedOpenTxId(openTxId);
    router.replace('/dashboard/transactions', { scroll: false });
  }, [transactions, consumedOpenTxId, router]);

  useEffect(() => {
    if (!spotlightTxId) return;
    const timer = window.setTimeout(() => setSpotlightTxId(null), 2500);
    return () => window.clearTimeout(timer);
  }, [spotlightTxId]);

  const clearFilters = () => {
    setDraftFilters(defaultFilters);
    setFilters(defaultFilters);
    setIsFilterOpen(false);
  };

  const startCategoryEdit = (tx: TransactionRow) => {
    setEditingCategoryTxId(tx.id);
    setEditingCategoryValue(tx.category || 'Misc');
  };

  const findSimilarTransactions = (tx: TransactionRow): TransactionRow[] => {
    return transactions.filter(
      t =>
        t.id !== tx.id &&
        (t.description === tx.description ||
          (t.merchant_name &&
            t.merchant_name === tx.merchant_name &&
            t.merchant_name !== 'Unknown'))
    );
  };

  const handleReclassify = async () => {
    if (!reclassifyTarget || !userId) return;
    setReclassifying(true);
    try {
      const allTxs = [reclassifyTarget, ...reclassifySimilar];
      const ids = allTxs.map(t => t.id);

      for (const tx of allTxs) {
        const updates: { category: string; amount?: number; original_category?: string } = {
          category: reclassifyCategory,
        };
        if (!tx.original_category) updates.original_category = tx.category;
        if (reclassifyCategory.toLowerCase() === 'income' && tx.amount < 0) {
          updates.amount = Math.abs(tx.amount);
        } else if (
          reclassifyCategory.toLowerCase() !== 'income' &&
          tx.amount > 0 &&
          tx.category?.toLowerCase() === 'income'
        ) {
          updates.amount = -Math.abs(tx.amount);
        }
        await supabase.from('transactions').update(updates).eq('id', tx.id).eq('user_id', userId);
      }

      const idSet = new Set(ids);
      setTransactions(prev =>
        prev.map(t => (idSet.has(t.id) ? { ...t, category: reclassifyCategory } : t))
      );

      // Send feedback to HypCD
      const corrections: Record<string, string> = {};
      for (const tx of allTxs) {
        if (tx.category !== reclassifyCategory) {
          corrections[tx.description] = reclassifyCategory;
        }
      }
      if (Object.keys(corrections).length > 0) {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        apiSubmitFeedback(corrections, session?.access_token).catch(err =>
          console.warn('Feedback failed:', err)
        );
      }

      // Log to training_corrections
      const trainingData = allTxs
        .filter(tx => tx.category !== reclassifyCategory)
        .map(tx => ({
          user_id: userId,
          transaction_id: tx.id,
          description: tx.description,
          original_category: tx.category,
          corrected_category: reclassifyCategory,
        }));
      if (trainingData.length > 0) {
        supabase
          .from('training_corrections')
          .insert(trainingData)
          .then(({ error }: { error: any }) => {
            if (error) console.warn('Failed to log corrections:', error);
          });
      }

      setMessage(`Reclassified ${allTxs.length} transaction(s).`);
      setReclassifyTarget(null);
      setReclassifySimilar([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reclassify transactions.');
    } finally {
      setReclassifying(false);
    }
  };

  const saveCategoryEdit = async () => {
    if (!editingCategoryTxId || !userId) return;
    setUpdatingCategory(true);
    try {
      const tx = transactions.find(t => t.id === editingCategoryTxId);
      if (!tx) throw new Error('Transaction not found');

      const isIncome = editingCategoryValue.toLowerCase() === 'income';
      const currentAmount = tx.amount;

      // Auto-flip logic
      let newAmount = currentAmount;
      if (isIncome && currentAmount < 0) {
        newAmount = Math.abs(currentAmount); // Convert to positive
      } else if (!isIncome && currentAmount > 0 && tx.category?.toLowerCase() === 'income') {
        newAmount = -Math.abs(currentAmount); // Convert to negative if moving AWAY from income
      }

      const updates: { category: string; amount?: number; original_category?: string } = {
        category: editingCategoryValue,
      };

      // If original_category is missing (e.g. older tx), backfill it with the *current* category before changing it.
      // Actually, if it's null, it implies the *current* value IS the original (or we missed backfilling).
      // The migration backfilled it. So we rely on it being there.
      // But if it's somehow null, we should probably set it to the OLD category value.
      if (!tx.original_category) {
        updates.original_category = tx.category;
      }

      if (newAmount !== currentAmount) {
        updates.amount = newAmount;
      }

      const { error: updateError } = await supabase
        .from('transactions')
        .update(updates)
        .eq('id', editingCategoryTxId)
        .eq('user_id', userId);

      if (updateError) throw updateError;

      setTransactions(prev =>
        prev.map(t =>
          t.id === editingCategoryTxId
            ? {
                ...t,
                category: editingCategoryValue,
                amount: newAmount,
              }
            : t
        )
      );

      setMessage('Category updated.');
      setEditingCategoryTxId(null);

      // Active Learning: Log correction asynchronously
      if (tx && tx.category !== editingCategoryValue) {
        supabase
          .from('training_corrections')
          .insert({
            user_id: userId,
            transaction_id: editingCategoryTxId,
            description: tx.description,
            original_category: tx.category,
            corrected_category: editingCategoryValue,
          })
          .then(({ error }: { error: any }) => {
            if (error) console.warn('Failed to log training correction:', error);
          });

        // Send feedback to HypCD
        const {
          data: { session },
        } = await supabase.auth.getSession();
        apiSubmitFeedback({ [tx.description]: editingCategoryValue }, session?.access_token).catch(
          err => console.warn('Feedback failed:', err)
        );
      }

      // Prompt reclassification of similar transactions
      const similar = findSimilarTransactions(tx);
      if (similar.length > 0) {
        setReclassifyTarget({ ...tx, category: editingCategoryValue });
        setReclassifySimilar(similar);
        setReclassifyCategory(editingCategoryValue);
      }
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : 'Unable to update category.');
    } finally {
      setUpdatingCategory(false);
    }
  };

  const scrollToTransactionRow = (txId: string) => {
    if (typeof window === 'undefined') return;
    let attempts = 0;
    const maxAttempts = 12;

    const tryScroll = () => {
      attempts += 1;
      const selector = `[data-tx-row-id="${txId.replace(/"/g, '\\"')}"]`;
      const row = document.querySelector(selector) as HTMLElement | null;
      if (row) {
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
      }

      if (attempts < maxAttempts) {
        window.setTimeout(tryScroll, 80);
      }
    };

    window.setTimeout(tryScroll, 0);
  };

  /* Consolidated handleDataImport */
  const handleDataImport = async (
    file: File,
    password?: string
  ): Promise<number> => {
    if (!userId) throw new Error('No authenticated user found.');

    // Auth Check
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) throw new Error('Session expired.');
    const accessToken = session.access_token;

    // Compute hash
    const fileBuffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', fileBuffer);
    const fileHash = Array.from(new Uint8Array(hashBuffer))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');

    // Detect format & Parse locally
    let parsedRows: Record<string, unknown>[] = [];
    let fileToProcess = file;

    // Server-side decrypt for password-protected Excel files
    if (password && detectImportFileKind(file.name) === 'excel') {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('password', password);

      const resp = await fetch('/api/decrypt-xlsx', {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}` },
        body: formData,
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        // Throw with specific message to trigger password modal logic if needed,
        // though here we likely already HAVE a password if we are in this block.
        // If password was wrong, API returns 400.
        throw new Error(err.error || 'Failed to decrypt file');
      }

      const decryptedBlob = await resp.blob();
      fileToProcess = new File([decryptedBlob], file.name, { type: file.type });
    }

    try {
      const parsed = await parseFileRows(fileToProcess);
      parsedRows = parsed.rows;
    } catch (err: any) {
      if (
        err.message &&
        (err.message.toLowerCase().includes('password') ||
          err.message.toLowerCase().includes('encrypted'))
      ) {
        // If we already tried with a password, it means the password was wrong
        if (password) {
          throw new Error('Incorrect password. Please try again.');
        }
        // Otherwise, we need to ask for one
        setPendingFile(file);
        setIsPasswordModalOpen(true);
        throw err;
      }
      throw err;
    }

    if (!parsedRows.length) throw new Error(`No rows found in ${file.name}`);

    // Helper: Map Row
    const mapRowToInsert = (row: Record<string, unknown>): InsertTransaction | null => {
      const normalized = new Map<string, string>();
      for (const [key, value] of Object.entries(row))
        normalized.set(normalizeHeader(key), toText(value));

      const amountRaw = parseAmount(normalized.get('amount') ?? '');
      const date =
        parseDateValue(normalized.get('date') ?? '') ||
        parseDateValue(normalized.get('transactiondate') ?? '');
      if (!date) return null;

      const type = (normalized.get('type') ?? 'expense').toLowerCase();
      const withdrawal =
        parseAmount(normalized.get('withdrawal') ?? '') ||
        parseAmount(normalized.get('debit') ?? '') ||
        0;
      const deposit =
        parseAmount(normalized.get('deposit') ?? '') ||
        parseAmount(normalized.get('credit') ?? '') ||
        0;

      let amount = amountRaw;
      if (withdrawal > 0 || deposit > 0) {
        amount = deposit > 0 ? Math.abs(deposit) : -Math.abs(withdrawal);
      } else if (/income|credit|deposit/.test(type)) {
        amount = Math.abs(amount || 0);
      } else {
        amount = -Math.abs(amount || 0);
      }

      const rawDescRaw =
        toText(normalized.get('description')) || toText(normalized.get('details')) || 'Imported';
      // Collapse newlines and excess whitespace (SBI statements embed \n in descriptions)
      const rawDesc = rawDescRaw
        .replace(/\s*\n\s*/g, ' ')
        .replace(/\s{2,}/g, ' ')
        .trim();

      // Merchant: check multiple possible column names
      const rawMerchant =
        toText(normalized.get('merchant')) ||
        toText(normalized.get('merchantname')) ||
        toText(normalized.get('product')) ||
        toText(normalized.get('merchantcategory')) ||
        toText(normalized.get('seller')) ||
        toText(normalized.get('vendor'));

      // Payment method: check column directly
      const rawPaymentMethod =
        toText(normalized.get('paymentmethod')) ||
        toText(normalized.get('mode')) ||
        toText(normalized.get('paymenttype'));

      // *** SBI PARSER ***
      const sbiResult = parseSbiDescription(rawDesc);

      // Description: Use clean description from parser, or fallback to readable
      const cleanDesc =
        sbiResult.type !== 'unknown'
          ? sbiResult.cleanDescription
          : extractReadableDescription(rawDesc) || rawDesc;

      // Merchant: Use parser merchant if known, else column, else extract from description
      let merchant = sbiResult.merchant !== 'Unknown' ? sbiResult.merchant : rawMerchant || '';
      if (!merchant) {
        // Try to extract merchant from the clean description using known merchant list
        const descLower = cleanDesc.toLowerCase();
        for (const [official, aliases] of knownMerchants) {
          if (aliases.some(a => descLower.includes(a))) {
            merchant = official;
            break;
          }
        }
        if (!merchant) merchant = 'Unknown';
      }

      // Payment method: prefer column value, then SBI parser, then infer from description
      let paymentMethod = rawPaymentMethod || (sbiResult.type !== 'unknown' ? sbiResult.type : '');
      if (!paymentMethod) {
        const descLower = rawDesc.toLowerCase();
        if (/\bupi\b|upvdr|upi\//.test(descLower)) paymentMethod = 'upi';
        else if (/\bpos\b|pos atm/.test(descLower)) paymentMethod = 'pos';
        else if (/\batm\b|atm wdl|atm cash/.test(descLower)) paymentMethod = 'atm';
        else if (/\bneft\b/.test(descLower)) paymentMethod = 'neft';
        else if (/\bimps\b/.test(descLower)) paymentMethod = 'imps';
        else if (/\binb\b|internet banking/.test(descLower)) paymentMethod = 'inb';
        else if (/visa|mastercard|rupay/.test(descLower)) paymentMethod = 'card';
        else paymentMethod = 'unknown';
      }

      const category = 'Uncategorized';

      return {
        user_id: userId,
        transaction_date: date,
        amount: amount || 0,
        currency: 'INR',
        description: cleanDesc,
        merchant_name: merchant,
        category: category,
        original_category: null,
        payment_method: paymentMethod,
        status: 'completed',
        raw_data: {
          ...row,
          ...sbiResult.meta,
          sbi_type: sbiResult.type,
        },
      };
    };

    // Build Batch & Fingerprints
    const existingFingerprints = new Set(
      transactions.map(
        t =>
          `${t.transaction_date.slice(0, 19)}|${Number(t.amount).toFixed(2)}|${(
            t.description || ''
          ).toLowerCase()}|${(t.merchant_name || '').toLowerCase()}`
      )
    );
    const newFingerprints = new Set<string>();
    const batch: InsertTransaction[] = [];
    let importedCount = 0;

    for (const row of parsedRows) {
      const tx = mapRowToInsert(row);
      if (!tx) continue;

      const fp = `${tx.transaction_date.slice(0, 19)}|${Number(tx.amount).toFixed(2)}|${(
        tx.description || ''
      ).toLowerCase()}|${(tx.merchant_name || '').toLowerCase()}`;
      if (existingFingerprints.has(fp) || newFingerprints.has(fp)) continue;
      newFingerprints.add(fp);
      batch.push(tx);
    }

    // Classify descriptions using HypCD, fall back to keyword classifier
    if (batch.length > 0) {
      let usedApi = false;
      try {
        const uniqueDescs = [...new Set(batch.map(tx => tx.description).filter(Boolean))];
        if (uniqueDescs.length > 0) {
          const categoryMap = await apiClassifyDescriptions(uniqueDescs, accessToken);
          for (const tx of batch) {
            const predicted = categoryMap[tx.description];
            if (predicted) tx.category = predicted;
          }
          usedApi = true;
        }
      } catch (classifyErr) {
        console.warn('HypCD API unavailable, using keyword classifier:', classifyErr);
      }

      // Fallback: keyword classifier for any still-Uncategorized transactions
      if (!usedApi) {
        for (const tx of batch) {
          if (tx.category === 'Uncategorized') {
            tx.category = classifyByKeywords(tx.description, tx.merchant_name);
          }
        }
      }
    }

    // Insert Batch
    const insertBatch = async (batchToWrite: InsertTransaction[]) => {
      if (!batchToWrite.length) return;

      const response = await fetch('/api/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify({
          transactions: batchToWrite,
          filename: file.name,
          file_hash: fileHash,
        }),
      });

      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        console.error('[insertBatch] Import failed:', response.status, errBody);
        throw new Error(errBody?.error || `Batch import failed (${response.status})`);
      }

      const body = await response.json().catch(() => ({}));
      importedCount += typeof body?.inserted === 'number' ? body.inserted : 0;
    };

    // Chunking & Upload
    const CHUNK_SIZE = 2500;
    const CONCURRENCY = 3;
    const chunks = [];
    for (let i = 0; i < batch.length; i += CHUNK_SIZE) {
      chunks.push(batch.slice(i, i + CHUNK_SIZE));
    }

    setImportProgress(10); // Start
    for (let i = 0; i < chunks.length; i += CONCURRENCY) {
      const activeBatch = chunks.slice(i, i + CONCURRENCY);
      await Promise.all(
        activeBatch.map(async chunk => {
          await insertBatch(chunk);
        })
      );
      const processedCount = Math.min((i + CONCURRENCY) * CHUNK_SIZE, batch.length);
      setImportProgress(10 + Math.round((processedCount / batch.length) * 90));
    }

    return importedCount;
  };

  const onSelectFile: React.ChangeEventHandler<HTMLInputElement> = async event => {
    console.log('onSelectFile triggered', event.target.files);
    if (saving) {
      event.target.value = '';
      return;
    }

    const file = event.target.files?.[0];
    if (!file) return;

    // fileKind check removed as handled by parseFileRows logic later

    setSaving(true);
    setImportProgress(0);
    setError(null);
    setMessage(null);
    try {
      const count = await handleDataImport(file);
      await fetchTransactions();
      setTab('all');
      listRef.current?.scrollTo({ top: 0, behavior: 'auto' });
      setMessage(`Imported ${count} transactions from ${file.name}.`);
      setSaving(false);
      setImportProgress(null);
      event.target.value = '';
    } catch (importError) {
      const msg = importError instanceof Error ? importError.message : 'Import failed.';

      setSaving(false);
      setImportProgress(null);

      if (msg.toLowerCase().includes('password') || msg.toLowerCase().includes('encrypted')) {
        // Password modal is already open from handleDataImport
        event.target.value = '';
      } else {
        setError(msg);
        event.target.value = '';
      }
    }
  };

  const handlePasswordSubmit = async () => {
    if (!pendingFile || !passwordInput) return;

    // Capture values and close modal IMMEDIATELY
    const file = pendingFile;
    const password = passwordInput;
    setIsPasswordModalOpen(false);
    setPendingFile(null);
    setPasswordInput('');

    // Run import in background — modal is already closed
    setSaving(true);
    setError(null);
    setImportProgress(0);

    try {
      const count = await handleDataImport(file, password);
      await fetchTransactions();
      setMessage(`Imported ${count} transactions.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import failed');
    } finally {
      setSaving(false);
      setImportProgress(null);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[55vh] items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex h-full min-h-0 flex-col gap-6"
    >
      <div className="pointer-events-none fixed right-8 top-8 z-[80] flex w-[min(520px,calc(100vw-2rem))] flex-col gap-3">
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.98 }}
              className="pointer-events-auto rounded-2xl border border-red-500/30 bg-red-500/15 px-6 py-4 text-sm text-red-200 backdrop-blur-md shadow-lg shadow-red-900/20"
            >
              {error}
            </motion.div>
          )}
          {message && (
            <motion.div
              initial={{ opacity: 0, y: -12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.98 }}
              className="pointer-events-auto rounded-2xl border border-emerald-500/30 bg-emerald-500/15 px-6 py-4 text-sm text-emerald-200 backdrop-blur-md shadow-lg shadow-emerald-900/20"
            >
              {message}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <section className="relative flex flex-col gap-6 rounded-[2.5rem] border border-border bg-card p-8 shadow-xl">
        {saving && !isPasswordModalOpen && (
          <div className="absolute inset-0 z-30 flex items-center justify-center rounded-[2.5rem] bg-[#0b1324]/75 backdrop-blur-sm">
            <div className="flex flex-col items-center gap-3 rounded-2xl border border-white/10 bg-black/30 px-6 py-5 text-center">
              <Loader2 className="h-6 w-6 animate-spin text-blue-400" />
              <p className="text-sm font-semibold text-white">
                {importProgress !== null
                  ? `Import in progress: ${importProgress}%`
                  : 'Import in progress'}
              </p>
              <p className="text-xs text-gray-300">
                Please wait. Controls are locked until import completes.
              </p>
            </div>
          </div>
        )}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-4xl font-black tracking-tight text-foreground">
              Transactions
              <span className="ml-2 text-lg font-medium text-muted-foreground">History</span>
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              View and manage your financial activity.
            </p>
          </div>

          <div className="flex items-center gap-3 md:flex-nowrap">
            <div className="relative group w-72">
              <Search className="pointer-events-none absolute left-4 top-3 h-4 w-4 text-gray-400 group-focus-within:text-blue-400 transition-colors" />
              <input
                value={search}
                onChange={event => setSearch(event.target.value)}
                placeholder="Search by merchant, category..."
                name="search"
                id="search-transactions"
                className="w-full rounded-2xl border border-border bg-secondary/30 px-10 py-2.5 text-sm text-foreground outline-none focus:border-primary focus:bg-secondary transition-all placeholder:text-muted-foreground"
              />
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="button"
              data-filter-trigger="true"
              onClick={() => setIsFilterOpen(prev => !prev)}
              className={`inline-flex items-center gap-2 rounded-2xl border px-5 py-2.5 text-sm font-bold transition-all ${
                isFilterOpen
                  ? 'border-primary/50 bg-primary/10 text-primary'
                  : 'border-border bg-secondary/30 text-muted-foreground hover:bg-secondary'
              }`}
            >
              <Filter className="h-4 w-4" />
              <span>Filters</span>
              <ChevronDown
                className={`h-4 w-4 transition-transform ${isFilterOpen ? 'rotate-180' : ''}`}
              />
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="button"
              onClick={() => {
                console.log('Import Data clicked');
                if (saving) return;
                fileInputRef.current?.click();
              }}
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-2xl bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground shadow-lg shadow-primary/20 hover:shadow-primary/40 transition-shadow disabled:cursor-not-allowed disabled:opacity-70 disabled:hover:shadow-primary/20"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              {saving && importProgress !== null ? `Importing ${importProgress}%` : 'Import Data'}
            </motion.button>
            <input
              ref={fileInputRef}
              type="file"
              name="file-upload"
              id="file-upload"
              accept=".csv,.tsv,.xls,.xlsx,.xlsm,.json,.txt,.pdf"
              className="hidden"
              onChange={onSelectFile}
              disabled={saving}
            />
          </div>
        </div>

        {/* Tab Selection */}
        <div className="flex flex-nowrap items-center gap-3 overflow-x-auto no-scrollbar pb-1">
          <div className="flex p-1 gap-1 bg-muted/30 rounded-2xl border border-border w-fit">
            {(['all', 'debit', 'credit'] as const).map(name => (
              <button
                key={name}
                type="button"
                onClick={() => setTab(name)}
                className={`relative px-6 py-2 rounded-xl text-sm font-bold transition-all ${
                  tab === name
                    ? 'text-foreground shadow-sm bg-background ring-1 ring-border'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {tab === name && (
                  <motion.div
                    layoutId="activeTab"
                    className="absolute inset-0 bg-white/5 rounded-xl"
                    initial={false}
                    transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                  />
                )}
                <span className="relative z-10 capitalize flex items-center gap-2">
                  {name}
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      tab === name ? 'bg-white/20' : 'bg-white/5'
                    }`}
                  >
                    {tabCounts[name]}
                  </span>
                </span>
              </button>
            ))}
          </div>

          {reclassifyTarget && (
            <div className="flex items-center gap-2 rounded-2xl border border-blue-500/30 bg-blue-500/10 px-4 py-2">
              <span className="text-xs font-semibold text-foreground">
                Reclassify this and {reclassifySimilar.length} similar transaction
                {reclassifySimilar.length !== 1 ? 's' : ''}?
              </span>
              <select
                name="reclassify-category"
                value={reclassifyCategory}
                onChange={event => setReclassifyCategory(event.target.value)}
                className="rounded-lg border border-border bg-secondary/50 px-3 py-1.5 text-xs font-semibold text-foreground outline-none"
                disabled={reclassifying}
              >
                {categoryOptions.map(option => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={handleReclassify}
                disabled={reclassifying}
                className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {reclassifying ? 'Updating...' : 'Apply'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setReclassifyTarget(null);
                  setReclassifySimilar([]);
                }}
                className="rounded-lg border border-border bg-secondary/50 px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-secondary"
              >
                Dismiss
              </button>
            </div>
          )}
        </div>

        <AnimatePresence>
          {isFilterOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div
                data-filter-panel="true"
                className="mt-2 rounded-3xl border border-border bg-card/95 p-6 backdrop-blur-sm shadow-xl"
              >
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
                  {/* Period */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-wider text-gray-500">
                      Period
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      <select
                        name="filter-year"
                        id="filter-year"
                        value={draftFilters.year}
                        onChange={e =>
                          setDraftFilters(p => ({
                            ...p,
                            year: e.target.value,
                            relative: e.target.value === 'all' ? p.relative : 'none',
                          }))
                        }
                        className="w-full rounded-xl border border-border bg-secondary/30 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                      >
                        {years.map(y => (
                          <option key={y} value={y}>
                            {y === 'all' ? 'All Years' : y}
                          </option>
                        ))}
                      </select>
                      <select
                        name="filter-month"
                        id="filter-month"
                        value={draftFilters.month}
                        onChange={e => setDraftFilters(p => ({ ...p, month: e.target.value }))}
                        disabled={draftFilters.year === 'all'}
                        className="w-full rounded-xl border border-border bg-secondary/30 px-3 py-2 text-sm text-foreground outline-none disabled:opacity-50"
                      >
                        <option value="all">All Months</option>
                        {Array.from({ length: 12 }).map((_, i) => (
                          <option key={i} value={String(i)}>
                            {monthName(i)}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Relative */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-wider text-gray-500">
                      Quick Range
                    </label>
                    <select
                      name="filter-relative"
                      id="filter-relative"
                      value={draftFilters.relative}
                      onChange={e =>
                        setDraftFilters(p => ({
                          ...p,
                          relative: e.target.value as RelativeRange,
                          year: e.target.value === 'none' ? p.year : 'all',
                          month: 'all',
                        }))
                      }
                      className="w-full rounded-xl border border-border bg-secondary/30 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                    >
                      <option value="none">Custom / None</option>
                      <option value="this_month">This Month</option>
                      <option value="last_30">Last 30 Days</option>
                      <option value="last_90">Last 3 Months</option>
                    </select>
                  </div>

                  {/* Category */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-wider text-gray-500">
                      Category
                    </label>
                    <select
                      name="filter-category"
                      id="filter-category"
                      value={draftFilters.category}
                      onChange={e => setDraftFilters(p => ({ ...p, category: e.target.value }))}
                      className="w-full rounded-xl border border-border bg-secondary/30 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                    >
                      {categories.map(c => (
                        <option key={c} value={c}>
                          {c === 'all' ? 'All Categories' : c}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Status */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-wider text-gray-500">
                      Status
                    </label>
                    <select
                      name="filter-status"
                      id="filter-status"
                      value={draftFilters.status}
                      onChange={e => setDraftFilters(p => ({ ...p, status: e.target.value }))}
                      className="w-full rounded-xl border border-border bg-secondary/30 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                    >
                      <option value="all">All Statuses</option>
                      <option value="completed">Completed</option>
                      <option value="cancelled">Cancelled</option>
                      <option value="refunded">Refunded</option>
                      <option value="failed">Failed</option>
                    </select>
                  </div>

                  {/* Amount Range */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-wider text-gray-500">
                      Amount Range
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        name="min-amount"
                        id="min-amount"
                        placeholder="Min"
                        value={draftFilters.minAmount}
                        onChange={e => setDraftFilters(p => ({ ...p, minAmount: e.target.value }))}
                        className="w-full rounded-xl border border-border bg-secondary/30 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                      />
                      <span className="text-muted-foreground">-</span>
                      <input
                        type="number"
                        name="max-amount"
                        id="max-amount"
                        placeholder="Max"
                        value={draftFilters.maxAmount}
                        onChange={e => setDraftFilters(p => ({ ...p, maxAmount: e.target.value }))}
                        className="w-full rounded-xl border border-border bg-secondary/30 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                      />
                    </div>
                  </div>
                </div>

                <div className="mt-6 flex justify-end gap-3 border-t border-white/5 pt-4">
                  <button
                    onClick={clearFilters}
                    className="px-4 py-2 text-sm font-semibold text-muted-foreground hover:text-foreground"
                  >
                    Reset Defaults
                  </button>
                  <button
                    onClick={applyFilters}
                    className="rounded-xl bg-blue-600 px-6 py-2 text-sm font-bold text-white shadow-lg shadow-blue-600/20 hover:bg-blue-500"
                  >
                    Apply Filters
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      {/* Transactions List */}
      <div
        ref={listRef}
        key={tab}
        className="min-h-0 flex-1 overflow-y-auto pr-2 custom-scrollbar space-y-6 pb-20"
      >
        {visibleGroups.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center py-20 text-center"
          >
            <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-muted/30 border border-border">
              <Search className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="text-xl font-bold text-foreground">No transactions found</h3>
            <p className="mt-2 text-muted-foreground max-w-sm">
              Try adjusting your filters or import a new statement to get started.
            </p>
            <button onClick={clearFilters} className="mt-6 text-blue-400 font-bold hover:underline">
              Clear all filters
            </button>
          </motion.div>
        ) : (
          <>
            {visibleGroups.map(group => {
              const headerLabel =
                tab === 'credit' ? 'Total Credited' : tab === 'debit' ? 'Total Spent' : 'Net Total';
              const headerValue =
                tab === 'credit' ? group.credited : tab === 'debit' ? group.spent : group.net;
              const headerColor =
                tab === 'credit'
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : tab === 'debit'
                    ? 'text-red-600 dark:text-red-400'
                    : headerValue >= 0
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : 'text-red-600 dark:text-red-400';

              return (
                <div
                  key={group.key}
                  className="rounded-[2rem] border border-border bg-card overflow-hidden shadow-lg"
                >
                  <div className="flex items-center justify-between bg-muted/30 px-8 py-5 border-b border-border">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-primary/80 mb-0.5">
                        {group.year}
                      </p>
                      <h3 className="text-2xl font-black text-foreground">
                        {monthName(group.month)}
                      </h3>
                    </div>
                    <div className="text-right">
                      <p className="text-xs uppercase font-bold text-muted-foreground mb-0.5">
                        {headerLabel}
                      </p>
                      <p className={`text-2xl font-mono font-bold ${headerColor}`}>
                        {tab === 'all' && headerValue > 0 ? '+' : ''}
                        {tab === 'all' && headerValue < 0 ? '-' : ''}₹
                        {Math.abs(headerValue).toLocaleString('en-IN')}
                      </p>
                    </div>
                  </div>
                  <div className="divide-y divide-border">
                    {group.rows.map(tx => {
                      const amount = Number(tx.amount || 0);
                      const isCredit = amount >= 0;
                      const status = normalizeStatus(tx.status ?? 'completed');
                      return (
                        <motion.div
                          key={tx.id}
                          data-tx-row-id={tx.id}
                          onClick={() => setSelected(tx)}
                          className={`flex cursor-pointer items-center justify-between px-6 py-4 transition-colors hover:bg-muted/40 group ${
                            spotlightTxId === tx.id ? 'ring-1 ring-blue-400/50 bg-blue-500/10' : ''
                          }`}
                        >
                          <div className="flex items-center gap-5 min-w-0">
                            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-muted/30 text-xl border border-border/50 group-hover:border-border group-hover:bg-muted/50 transition-colors">
                              {categoryIcon(tx.category ?? 'Misc')}
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-3">
                                <p className="truncate text-base font-bold text-foreground group-hover:text-primary transition-colors">
                                  {tx.description || 'Transaction'}
                                </p>
                                {status !== 'completed' && (
                                  <span
                                    className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wide border ${
                                      status === 'failed'
                                        ? 'bg-red-500/10 text-red-500 border-red-500/20'
                                        : status === 'cancelled'
                                          ? 'bg-amber-500/10 text-amber-600 border-amber-500/20'
                                          : status === 'refunded'
                                            ? 'bg-blue-500/10 text-blue-500 border-blue-500/20'
                                            : 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20'
                                    }`}
                                  >
                                    {status}
                                  </span>
                                )}
                              </div>
                              <div className="mt-0.5 flex items-center gap-2">
                                <p className="text-xs font-medium text-muted-foreground">
                                  {new Date(tx.transaction_date).toLocaleDateString('en-IN', {
                                    day: 'numeric',
                                    month: 'short',
                                    weekday: 'short',
                                  })}
                                </p>
                                <span className="h-1 w-1 rounded-full bg-muted-foreground/30" />
                                {editingCategoryTxId === tx.id ? (
                                  <div
                                    data-category-editor="true"
                                    className="flex items-center gap-1"
                                    onClick={event => event.stopPropagation()}
                                  >
                                    <select
                                      name={`category-edit-${tx.id}`}
                                      id={`category-edit-${tx.id}`}
                                      value={editingCategoryValue}
                                      onChange={event =>
                                        setEditingCategoryValue(event.target.value)
                                      }
                                      className="rounded-lg border border-border bg-secondary/80 px-2 py-1 text-[11px] font-medium text-foreground outline-none"
                                      disabled={updatingCategory}
                                    >
                                      {categoryOptions.map(option => (
                                        <option key={option} value={option}>
                                          {option}
                                        </option>
                                      ))}
                                    </select>
                                    <button
                                      type="button"
                                      onClick={saveCategoryEdit}
                                      disabled={updatingCategory}
                                      className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-1 text-emerald-500 hover:bg-emerald-500/20 disabled:opacity-60"
                                      title="Save category"
                                    >
                                      <Check className="h-3.5 w-3.5" />
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => setEditingCategoryTxId(null)}
                                      disabled={updatingCategory}
                                      className="rounded-md border border-border bg-secondary/50 p-1 text-muted-foreground hover:bg-secondary disabled:opacity-60"
                                      title="Cancel"
                                    >
                                      <X className="h-3.5 w-3.5" />
                                    </button>
                                  </div>
                                ) : (
                                  <>
                                    <p className="max-w-[140px] truncate text-xs font-medium text-gray-500">
                                      {tx.category}
                                    </p>
                                    <button
                                      type="button"
                                      onClick={event => {
                                        event.stopPropagation();
                                        startCategoryEdit(tx);
                                      }}
                                      data-category-edit-trigger="true"
                                      className="rounded-md border border-transparent hover:border-border hover:bg-secondary/50 p-1 text-muted-foreground hover:text-foreground"
                                      title="Edit category"
                                    >
                                      <Pencil className="h-3 w-3" />
                                    </button>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                          <div className="text-right pl-4">
                            <p
                              className={`font-mono text-lg font-bold ${
                                isCredit
                                  ? 'text-emerald-600 dark:text-emerald-400'
                                  : 'text-red-600 dark:text-red-400'
                              }`}
                            >
                              {isCredit ? '+' : ''}₹{Math.abs(amount).toLocaleString('en-IN')}
                            </p>
                            <p className="text-[10px] font-bold uppercase text-muted-foreground mt-0.5">
                              {tx.payment_method}
                            </p>
                          </div>
                        </motion.div>
                      );
                    })}
                  </div>
                </div>
              );
            })}

            {filteredTransactions.length > visibleCount && (
              <div className="flex justify-center py-4">
                <button
                  onClick={() => setVisibleCount(prev => prev + LOAD_MORE_STEP)}
                  className="rounded-xl border border-border bg-secondary/50 px-6 py-2 text-sm font-bold text-foreground hover:bg-secondary transition-colors"
                >
                  Load More
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Detail Modal */}
      <AnimatePresence>
        {selected && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelected(null)}
              className="absolute inset-0 bg-black/80 backdrop-blur-sm"
            />
            <motion.div
              layoutId={`tx-${selected.id}`}
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="relative w-full max-w-lg overflow-hidden rounded-[2.5rem] border border-border bg-card shadow-2xl"
            >
              <div className="absolute top-0 right-0 p-6 z-10">
                <button
                  onClick={() => setSelected(null)}
                  className="rounded-full bg-muted/50 p-2 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="flex flex-col items-center pt-10 pb-8 px-6 bg-gradient-to-b from-primary/10 to-transparent">
                <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-[2rem] bg-gradient-to-br from-blue-500 to-indigo-600 text-4xl shadow-lg shadow-blue-500/20">
                  {categoryIcon(selected.category ?? 'Misc')}
                </div>
                <h3 className="text-center text-2xl font-black text-foreground px-4 leading-tight">
                  {selected.description || 'Transaction'}
                </h3>
                <p className="mt-2 text-sm font-medium text-primary/70 uppercase tracking-widest">
                  {selected.category || 'Uncategorized'}
                </p>
                <h2
                  className={`mt-6 font-mono text-5xl font-black tracking-tighter ${
                    Number(selected.amount) >= 0
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : 'text-red-600 dark:text-red-400'
                  }`}
                >
                  {Number(selected.amount) >= 0 ? '+' : ''}₹
                  {Math.abs(Number(selected.amount)).toLocaleString('en-IN')}
                </h2>
                <div className="mt-4 flex gap-2">
                  <span className="px-3 py-1 rounded-full bg-secondary/50 border border-border text-xs font-bold text-muted-foreground uppercase">
                    {normalizeStatus(selected.status ?? 'completed')}
                  </span>
                  <span className="px-3 py-1 rounded-full bg-secondary/50 border border-border text-xs font-bold text-muted-foreground uppercase">
                    {selected.payment_method || 'Unknown Method'}
                  </span>
                </div>
              </div>

              <div className="bg-muted/20 px-6 py-6 border-t border-border space-y-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground font-medium">Date & Time</span>
                  <span className="text-foreground font-bold">
                    {new Date(selected.transaction_date).toLocaleString('en-IN', {
                      weekday: 'short',
                      day: 'numeric',
                      month: 'long',
                      year: 'numeric',
                      hour: 'numeric',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
                <div className="h-px bg-border w-full" />
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground font-medium">Merchant / Ref</span>
                  <span className="text-foreground font-bold truncate max-w-[200px]">
                    {selected.merchant_name || selected.description || '-'}
                  </span>
                </div>

                {/* Structured Data Section */}
                {selected.raw_data && (
                  <>
                    {selected.raw_data.method && (
                      <>
                        <div className="h-px bg-border w-full" />
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground font-medium">Payment Method</span>
                          <span className="text-foreground font-bold">
                            {selected.raw_data.method}
                          </span>
                        </div>
                      </>
                    )}
                    {selected.raw_data.location && (
                      <>
                        <div className="h-px bg-border w-full" />
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground font-medium">Location</span>
                          <span className="text-foreground font-bold">
                            {selected.raw_data.location}
                          </span>
                        </div>
                      </>
                    )}
                    {selected.raw_data.ref && (
                      <>
                        <div className="h-px bg-border w-full" />
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground font-medium">Reference No.</span>
                          <span className="text-foreground font-mono text-xs">
                            {selected.raw_data.ref}
                          </span>
                        </div>
                      </>
                    )}
                  </>
                )}
                <div className="h-px bg-border w-full" />
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground font-medium">Transaction ID</span>
                  <span
                    className="text-muted-foreground/70 font-mono text-xs truncate max-w-[180px]"
                    title={selected.id}
                  >
                    {selected.id}
                  </span>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Password Modal */}
      <AnimatePresence>
        {isPasswordModalOpen && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-md overflow-hidden rounded-3xl bg-[#0b1324] border border-white/10 shadow-2xl"
            >
              <div className="p-6">
                <div className="flex items-center gap-4 mb-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-500/20 text-blue-400">
                    <Lock className="h-6 w-6" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-white">Password Protected</h3>
                    <p className="text-sm text-gray-400">This file is encrypted.</p>
                  </div>
                </div>

                <p className="text-sm text-gray-300 mb-4">
                  Please enter the password to decrypt <strong>{pendingFile?.name}</strong>.
                </p>

                <input
                  type="password"
                  value={passwordInput}
                  onChange={e => setPasswordInput(e.target.value)}
                  placeholder="Enter file password"
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none focus:border-blue-500 transition-colors mb-6"
                  autoFocus
                  onKeyDown={e => e.key === 'Enter' && handlePasswordSubmit()}
                />

                <div className="flex gap-3 justify-end">
                  <button
                    onClick={() => {
                      setIsPasswordModalOpen(false);
                      setPendingFile(null);
                      setPasswordInput('');
                    }}
                    className="px-4 py-2 text-sm font-semibold text-gray-400 hover:text-white transition-colors"
                    disabled={saving}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handlePasswordSubmit}
                    disabled={!passwordInput || saving}
                    className="rounded-xl bg-blue-600 px-6 py-2 text-sm font-bold text-white hover:bg-blue-500 transition-colors disabled:opacity-50 flex items-center gap-2"
                  >
                    {saving && <Loader2 className="h-4 w-4 animate-spin" />}
                    {saving ? 'Decrypting...' : 'Unlock & Import'}
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
