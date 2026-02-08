"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Papa from "papaparse";
import * as XLSX from "xlsx";
import {
  Check,
  ChevronDown,
  Download,
  Filter,
  Loader2,
  Pencil,
  Search,
  X,
} from "lucide-react";
import { AnimatePresence, motion, Variants } from "framer-motion";
import { useRouter } from "next/navigation";
import { supabase } from "../../../lib/supabase/client";

type TransactionRow = {
  id: string;
  user_id: string;
  transaction_date: string;
  amount: number;
  description: string | null;
  merchant_name: string | null;
  category: string | null;
  payment_method: string | null;
  status: string | null;
  currency: string | null;
};

type InsertTransaction = {
  user_id: string;
  transaction_date: string;
  amount: number;
  currency: string;
  description: string;
  merchant_name: string;
  category: string;
  payment_method: string;
  status: string;
  raw_data: Record<string, unknown>;
};

type RelativeRange =
  | "none"
  | "this_week"
  | "this_month"
  | "last_30"
  | "last_90"
  | "last_180"
  | "custom";

type FilterState = {
  year: "all" | string;
  month: "all" | string;
  relative: RelativeRange;
  customStart: string;
  customEnd: string;
  category: "all" | string;
  status: "all" | string;
  minAmount: string;
  maxAmount: string;
  paymentMethod: "all" | string;
};

type CsvFormat = "google" | "bank" | "upi" | "generic";
type ImportFileKind = "csv" | "excel" | "json" | "text" | "pdf" | "unknown";

const defaultFilters: FilterState = {
  year: "all",
  month: "all",
  relative: "none",
  customStart: "",
  customEnd: "",
  category: "all",
  status: "all",
  minAmount: "",
  maxAmount: "",
  paymentMethod: "all",
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
const MAX_FETCH_PAGES = 500;
const MAX_FETCH_ROWS = 100000;
const FETCH_REQUEST_TIMEOUT_MS = 12000;
const MAX_FETCH_DURATION_MS = 45000;
const INSERT_BATCH_SIZE = 2000;
const INSERT_CONCURRENCY = 4;
const PARSE_CHUNK_SIZE = 1024 * 1024;
const TRANSACTIONS_CACHE_TTL_MS = 60 * 1000;

async function withTimeout<T>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | null = null;
  try {
    return await Promise.race([
      promise,
      new Promise<T>((_, reject) => {
        timer = setTimeout(() => reject(new Error(`${label} timed out. Please try again.`)), timeoutMs);
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function normalizeHeader(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function toText(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value).trim();
}

function parseAmount(value: string): number | null {
  const cleaned = value
    .replace(/INR/gi, "")
    .replace(/[₹,\s\u00a0]/g, "")
    .replace(/[()]/g, "");
  if (!cleaned) return null;
  const parsed = Number.parseFloat(cleaned);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeStatus(value: string): string {
  const status = value.trim().toLowerCase();
  if (status.includes("refund")) return "refunded";
  if (status.includes("cancel")) return "cancelled";
  if (status.includes("fail")) return "failed";
  if (status.includes("complete") || status.includes("success")) return "completed";
  return status || "completed";
}

function inferPaymentMethod(value: string): string {
  const method = value.trim().toLowerCase();
  if (!method) return "unknown";
  if (method.includes("upi")) return "upi";
  if (method.includes("visa") || method.includes("master") || method.includes("card")) return "card";
  if (method.includes("net") || method.includes("bank")) return "netbanking";
  return method;
}

function toTitleCase(value: string): string {
  return value
    .toLowerCase()
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
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
    "UPI",
    "IMPS",
    "NEFT",
    "RTGS",
    "ACH",
    "NACH",
    "CREDIT",
    "DEBIT",
    "PAYMENT",
    "TRANSFER",
    "BANK",
    "AXIS BANK",
    "HDFC BANK",
    "SBI",
    "ICICI",
    "YES BANK",
    "KOTAK",
  ];
  return noiseWords.includes(upper);
}

function extractReadableDescription(raw: string): string {
  const source = raw.trim();
  if (!source) return "Imported transaction";

  const normalizedSource = source.replace(/\s+/g, " ").trim();

  if (normalizedSource.includes("/")) {
    const parts = normalizedSource
      .split(/[\/|>]/)
      .map((part) => part.trim())
      .filter(Boolean);

    for (const part of parts) {
      if (isNoiseSegment(part)) continue;
      if (part.length < 3) continue;
      if (/@/.test(part)) continue;
      return toTitleCase(part.replace(/[._-]+/g, " "));
    }
  }

  if (/^[A-Z]{2,5}\.[A-Z0-9-]{8,}$/i.test(normalizedSource)) {
    return "Card/UPI transaction";
  }

  const trimmed = normalizedSource
    .replace(/\b(UPI|IMPS|NEFT|RTGS|ACH|NACH)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();

  if (!trimmed) return "Imported transaction";
  if (trimmed.length <= 64) return toTitleCase(trimmed);
  return `${toTitleCase(trimmed.slice(0, 61).trim())}...`;
}

function parseDateValue(value: string): string | null {
  const raw = value.trim();
  if (!raw) return null;

  const slashDateTime = raw.match(/^\s*(\d{1,2})\/(\d{1,2})\/(\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$/);
  if (slashDateTime) {
    const day = Number.parseInt(slashDateTime[1], 10);
    const month = Number.parseInt(slashDateTime[2], 10) - 1;
    const yearRaw = Number.parseInt(slashDateTime[3], 10);
    const year = yearRaw < 100 ? 2000 + yearRaw : yearRaw;
    const hour = Number.parseInt(slashDateTime[4] ?? "0", 10);
    const minute = Number.parseInt(slashDateTime[5] ?? "0", 10);
    const second = Number.parseInt(slashDateTime[6] ?? "0", 10);
    const date = new Date(year, month, day, hour, minute, second);
    if (!Number.isNaN(date.getTime())) return date.toISOString();
  }

  const dashDateTime = raw.match(/^\s*(\d{1,2})-(\d{1,2})-(\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$/);
  if (dashDateTime) {
    const day = Number.parseInt(dashDateTime[1], 10);
    const month = Number.parseInt(dashDateTime[2], 10) - 1;
    const yearRaw = Number.parseInt(dashDateTime[3], 10);
    const year = yearRaw < 100 ? 2000 + yearRaw : yearRaw;
    const hour = Number.parseInt(dashDateTime[4] ?? "0", 10);
    const minute = Number.parseInt(dashDateTime[5] ?? "0", 10);
    const second = Number.parseInt(dashDateTime[6] ?? "0", 10);
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

  const direct = new Date(raw.replace("Sept", "Sep"));
  if (!Number.isNaN(direct.getTime())) return direct.toISOString();

  const iso = new Date(raw.replace(" ", "T").replace("Sept", "Sep"));
  if (!Number.isNaN(iso.getTime())) return iso.toISOString();
  return null;
}

function detectImportFileKind(fileName: string): ImportFileKind {
  const extension = fileName.split(".").pop()?.toLowerCase() ?? "";
  if (extension === "csv" || extension === "tsv") return "csv";
  if (extension === "xls" || extension === "xlsx" || extension === "xlsm") return "excel";
  if (extension === "json") return "json";
  if (extension === "txt") return "text";
  if (extension === "pdf") return "pdf";
  return "unknown";
}

function normalizeSpreadsheetRows(rows: Record<string, unknown>[]): Record<string, unknown>[] {
  if (!rows.length) return rows;

  const firstRow = rows[0];
  const firstKeys = Object.keys(firstRow);
  const looksLikeEmptyHeaders = firstKeys.length > 0 && firstKeys.every((key) => key.startsWith("__EMPTY"));
  if (!looksLikeEmptyHeaders) return rows;

  const dynamicHeaders = firstKeys.map((key, index) => {
    const value = toText(firstRow[key]);
    return value || `column_${index + 1}`;
  });

  return rows
    .slice(1)
    .map((row) => {
      const normalized: Record<string, unknown> = {};
      firstKeys.forEach((key, index) => {
        normalized[dynamicHeaders[index]] = row[key];
      });
      return normalized;
    })
    .filter((row) => Object.values(row).some((value) => toText(value) !== ""));
}

function parseTableText(text: string): Record<string, unknown>[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (!lines.length) return [];

  const delimiters = [",", "\t", "|", ";"];
  let selectedDelimiter = ",";
  let bestScore = -1;
  const headerLine = lines[0];
  for (const delimiter of delimiters) {
    const score = headerLine.split(delimiter).length;
    if (score > bestScore) {
      bestScore = score;
      selectedDelimiter = delimiter;
    }
  }

  const parsed = Papa.parse<Record<string, unknown>>(lines.join("\n"), {
    header: true,
    skipEmptyLines: true,
    delimiter: selectedDelimiter,
  });

  return parsed.data;
}

async function parseFileRows(file: File): Promise<{ rows: Record<string, unknown>[]; fileKind: ImportFileKind }> {
  const fileKind = detectImportFileKind(file.name);

  if (fileKind === "csv") {
    return { rows: [], fileKind };
  }

  if (fileKind === "excel") {
    const buffer = await file.arrayBuffer();
    const workbook = XLSX.read(buffer, { type: "array", cellDates: false, raw: false });
    const sheetName = workbook.SheetNames[0];
    if (!sheetName) return { rows: [], fileKind };

    const worksheet = workbook.Sheets[sheetName];
    const rawRows = XLSX.utils.sheet_to_json<Record<string, unknown>>(worksheet, { defval: "", raw: false });
    return { rows: normalizeSpreadsheetRows(rawRows), fileKind };
  }

  if (fileKind === "json") {
    const text = await file.text();
    const json = JSON.parse(text);
    if (Array.isArray(json)) {
      return { rows: json as Record<string, unknown>[], fileKind };
    }
    if (json && Array.isArray((json as { transactions?: unknown[] }).transactions)) {
      return { rows: (json as { transactions: Record<string, unknown>[] }).transactions, fileKind };
    }
    return { rows: [], fileKind };
  }

  if (fileKind === "text" || fileKind === "pdf") {
    const text = await file.text();
    return { rows: parseTableText(text), fileKind };
  }

  return { rows: [], fileKind };
}

function guessCategory(description: string): string {
  const source = description.toLowerCase();

  if (/(salary|income|interest|refund|cashback|credited|deposit)/.test(source)) return "Income";
  if (/(subscription|membership|monthly|renewal|google one|youtube premium|netflix|spotify|prime video|hotstar|apple music|icloud)/.test(source)) return "Subscriptions";
  if (/(swiggy|zomato|restaurant|cafe|coffee|food|dining|eat)/.test(source)) return "Food";
  if (/(blinkit|zepto|bigbasket|grocery|supermarket|mart|dmart)/.test(source)) return "Grocery";
  if (/(amazon|flipkart|myntra|ajio|meesho|shopping|store|mall|retail)/.test(source)) return "Shopping";
  if (/(uber|ola|rapido|metro|irctc|rail|bus|flight|petrol|diesel|fuel|transport|parking|toll)/.test(source)) return "Transport";
  if (/(electricity|water|gas|broadband|wifi|mobile|recharge|postpaid|utility|bill)/.test(source)) return "Utilities";
  if (/(hospital|clinic|pharma|medicine|health|doctor|lab)/.test(source)) return "Healthcare";
  if (/(school|college|course|tuition|education|udemy|coursera)/.test(source)) return "Education";
  if (/(movie|netflix|spotify|youtube|prime|hotstar|entertainment|gaming)/.test(source)) return "Entertainment";
  if (/(insurance|mutual|sip|investment|loan|emi|credit card)/.test(source)) return "Finance";
  return "Misc";
}

function categoryIcon(category: string): string {
  const key = category.toLowerCase();
  if (key.includes("food")) return "🍔";
  if (key.includes("shop")) return "🛍️";
  if (key.includes("grocery")) return "🛒";
  if (key.includes("subscription")) return "🔁";
  if (key.includes("utility")) return "📄";
  if (key.includes("transport") || key.includes("fuel")) return "🚕";
  if (key.includes("income")) return "💰";
  return "📄";
}

function inRelativeRange(date: Date, filters: FilterState): boolean {
  if (filters.relative === "none") return true;
  const now = new Date();
  const start = new Date();
  start.setHours(0, 0, 0, 0);

  if (filters.relative === "this_week") {
    const day = start.getDay() || 7;
    start.setDate(start.getDate() - (day - 1));
    return date >= start && date <= now;
  }
  if (filters.relative === "this_month") {
    start.setDate(1);
    return date >= start && date <= now;
  }
  if (filters.relative === "last_30") {
    start.setDate(now.getDate() - 30);
    return date >= start && date <= now;
  }
  if (filters.relative === "last_90") {
    start.setDate(now.getDate() - 90);
    return date >= start && date <= now;
  }
  if (filters.relative === "last_180") {
    start.setDate(now.getDate() - 180);
    return date >= start && date <= now;
  }
  if (filters.relative === "custom") {
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
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ][index];
}

export default function TransactionsPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [transactions, setTransactions] = useState<TransactionRow[]>([]);
  const [userId, setUserId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<"all" | "debit" | "credit">("all");
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [draftFilters, setDraftFilters] = useState<FilterState>(defaultFilters);
  const [filters, setFilters] = useState<FilterState>(defaultFilters);
  const [selected, setSelected] = useState<TransactionRow | null>(null);
  const [importProgress, setImportProgress] = useState<number | null>(null);
  const [editingCategoryTxId, setEditingCategoryTxId] = useState<string | null>(null);
  const [editingCategoryValue, setEditingCategoryValue] = useState<string>("Misc");
  const [updatingCategory, setUpdatingCategory] = useState(false);
  const [selectedTxIds, setSelectedTxIds] = useState<Set<string>>(new Set());
  const [bulkCategoryValue, setBulkCategoryValue] = useState<string>("Misc");
  const [bulkUpdatingCategory, setBulkUpdatingCategory] = useState(false);
  const [bulkMode, setBulkMode] = useState(false);
  const [consumedOpenTxId, setConsumedOpenTxId] = useState<string | null>(null);
  const [spotlightTxId, setSpotlightTxId] = useState<string | null>(null);

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
    listRef.current?.scrollTo({ top: 0, behavior: "smooth" });
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
    setSelectedTxIds((prev) => {
      if (prev.size === 0) return prev;
      const valid = new Set(transactions.map((tx) => tx.id));
      const next = new Set<string>();
      prev.forEach((id) => {
        if (valid.has(id)) next.add(id);
      });
      return next;
    });
  }, [transactions]);

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

    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [isFilterOpen, editingCategoryTxId]);

  const fetchTransactions = useCallback(async () => {
    const userLookup = await withTimeout<{ data: { user: { id: string } | null }; error: { message?: string } | null }>(
      supabase.auth.getUser().then((result: {
        data: { user: { id: string } | null };
        error: { message: string } | null;
      }) => ({
        data: { user: result.data.user ? { id: result.data.user.id } : null },
        error: result.error ? { message: result.error.message } : null,
      })),
      8000,
      "User session lookup",
    );

    const {
      data: { user },
      error: userError,
    } = userLookup;

    if (userError || !user) {
      router.replace("/login");
      return;
    }

    setUserId(user.id);

    const cacheKey = `transactions-cache:${user.id}`;
    const cachedRaw = sessionStorage.getItem(cacheKey);
    if (cachedRaw) {
      try {
        const cached = JSON.parse(cachedRaw) as { timestamp: number; rows: TransactionRow[] };
        if (Date.now() - cached.timestamp < TRANSACTIONS_CACHE_TTL_MS && Array.isArray(cached.rows)) {
          setTransactions(cached.rows);
          setLoading(false);
        }
      } catch {
        // Ignore bad cache and continue network fetch.
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
      const pageResponse = await withTimeout<{ data: Record<string, unknown>[]; errorMessage: string | null }>(
        supabase
          .from("transactions")
          .select(
            "id,user_id,transaction_date,amount,description,merchant_name,category,payment_method,status,currency",
          )
          .eq("user_id", user.id)
          .order("transaction_date", { ascending: false })
          .range(from, to)
          .then((response: { data: unknown[] | null; error: { message: string } | null }) => ({
            data: ((response.data ?? []) as Record<string, unknown>[]),
            errorMessage: response.error?.message ?? null,
          })),
        FETCH_REQUEST_TIMEOUT_MS,
        "Transactions fetch",
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

    const mappedTransactions = allRows.map((row) => {
      const rawDescription = toText(row.description) || toText(row.merchant_name) || "Imported transaction";
      const displayDescription = extractReadableDescription(rawDescription);
      const rawCategory = toText(row.category);

      return {
        id: toText(row.id),
        user_id: toText(row.user_id),
        transaction_date: toText(row.transaction_date),
        amount: Number(row.amount ?? 0),
        description: displayDescription,
        merchant_name: extractReadableDescription(toText(row.merchant_name) || rawDescription),
        category: rawCategory && rawCategory.toLowerCase() !== "misc" ? rawCategory : guessCategory(rawDescription),
        payment_method: toText(row.payment_method) || "unknown",
        status: toText(row.status) || "completed",
        currency: toText(row.currency) || "INR",
      };
    });

    setTransactions(mappedTransactions);
    sessionStorage.setItem(
      cacheKey,
      JSON.stringify({
        timestamp: Date.now(),
        rows: mappedTransactions,
      }),
    );

    if (truncated) {
      setMessage(`Loaded ${allRows.length.toLocaleString("en-IN")} recent transactions. Narrow filters or refresh to load more.`);
    }
  }, [router]);

  useEffect(() => {
    let mounted = true;
    let finished = false;
    const spinnerGuard = setTimeout(() => {
      if (!mounted || finished) return;
      setError("Loading transactions is taking longer than expected. Please refresh and try again.");
      setLoading(false);
    }, 20000);

    (async () => {
      try {
        await fetchTransactions();
      } catch (fetchError) {
        if (mounted) {
          setError(fetchError instanceof Error ? fetchError.message : "Unable to load transactions.");
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
    return ["all", ...Array.from(values).sort((a, b) => a.localeCompare(b))];
  }, [transactions]);

  const categoryOptions = useMemo(() => {
    const defaults = [
      "Food",
      "Grocery",
      "Shopping",
      "Transport",
      "Utilities",
      "Subscriptions",
      "Healthcare",
      "Education",
      "Entertainment",
      "Finance",
      "Income",
      "Misc",
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
    return ["all", ...Array.from(values).sort((a, b) => Number(b) - Number(a))];
  }, [transactions]);

  const filteredBase = useMemo(() => {
    return transactions.filter((tx) => {
      const date = new Date(tx.transaction_date);
      if (Number.isNaN(date.getTime())) return false;

      const q = search.trim().toLowerCase();
      if (q) {
        const haystack = [tx.description, tx.merchant_name, tx.category, tx.payment_method, tx.status]
          .map((v) => (v ?? "").toLowerCase())
          .join(" ");
        if (!haystack.includes(q)) return false;
      }

      if (filters.year !== "all" && String(date.getFullYear()) !== filters.year) return false;
      if (filters.year !== "all" && filters.month !== "all" && String(date.getMonth()) !== filters.month) return false;
      if (!inRelativeRange(date, filters)) return false;
      if (filters.category !== "all" && (tx.category ?? "") !== filters.category) return false;
      if (filters.status !== "all" && normalizeStatus(tx.status ?? "") !== filters.status) return false;
      if (filters.paymentMethod !== "all" && (tx.payment_method ?? "") !== filters.paymentMethod) return false;

      const absAmount = Math.abs(Number(tx.amount || 0));
      const min = filters.minAmount ? Number.parseFloat(filters.minAmount) : null;
      const max = filters.maxAmount ? Number.parseFloat(filters.maxAmount) : null;
      if (min !== null && Number.isFinite(min) && absAmount < min) return false;
      if (max !== null && Number.isFinite(max) && absAmount > max) return false;
      return true;
    });
  }, [transactions, search, filters]);

  const tabCounts = useMemo(() => {
    const debit = filteredBase.filter((tx) => Number(tx.amount) < 0).length;
    const credit = filteredBase.filter((tx) => Number(tx.amount) >= 0).length;
    return { all: filteredBase.length, debit, credit };
  }, [filteredBase]);

  const filteredTransactions = useMemo(() => {
    if (tab === "debit") return filteredBase.filter((tx) => Number(tx.amount) < 0);
    if (tab === "credit") return filteredBase.filter((tx) => Number(tx.amount) >= 0);
    return filteredBase;
  }, [filteredBase, tab]);

  const selectedCount = selectedTxIds.size;
  const visibleTransactionIds = useMemo(() => filteredTransactions.map((tx) => tx.id), [filteredTransactions]);

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
        const [yearRaw, monthRaw] = key.split("-");
        const year = Number(yearRaw);
        const month = Number(monthRaw);
        const spent = rows.filter((r) => Number(r.amount) < 0).reduce((sum, r) => sum + Math.abs(Number(r.amount)), 0);
        const credited = rows.filter((r) => Number(r.amount) >= 0).reduce((sum, r) => sum + Number(r.amount), 0);
        const net = rows.reduce((sum, r) => sum + Number(r.amount), 0);
        rows.sort((a, b) => new Date(b.transaction_date).getTime() - new Date(a.transaction_date).getTime());
        return { key, year, month, spent, credited, net, rows };
      })
      .sort((a, b) => (a.year !== b.year ? b.year - a.year : b.month - a.month));
  }, [filteredTransactions]);

  const applyFilters = () => {
    setFilters(draftFilters);
    setIsFilterOpen(false);
  };

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const openTxId = params.get("openTx") || params.get("highlight");
    if (!openTxId || openTxId === consumedOpenTxId || transactions.length === 0) return;

    const match = transactions.find((tx) => tx.id === openTxId);
    if (!match) return;

    setTab("all");
    setSearch("");
    setFilters(defaultFilters);
    setDraftFilters(defaultFilters);
    setSelected(match);
    setSpotlightTxId(openTxId);
    scrollToTransactionRow(openTxId);
    setConsumedOpenTxId(openTxId);
    router.replace("/dashboard/transactions", { scroll: false });
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
    setEditingCategoryValue(tx.category || "Misc");
  };

  const saveCategoryEdit = async () => {
    if (!editingCategoryTxId || !userId) return;
    setUpdatingCategory(true);
    try {
      const { error: updateError } = await supabase
        .from("transactions")
        .update({ category: editingCategoryValue })
        .eq("id", editingCategoryTxId)
        .eq("user_id", userId);

      if (updateError) throw updateError;

      setTransactions((prev) =>
        prev.map((tx) =>
          tx.id === editingCategoryTxId
            ? {
              ...tx,
              category: editingCategoryValue,
            }
            : tx,
        ),
      );

      setMessage("Category updated.");
      setEditingCategoryTxId(null);
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Unable to update category.");
    } finally {
      setUpdatingCategory(false);
    }
  };

  const toggleTransactionSelection = (txId: string) => {
    setSelectedTxIds((prev) => {
      const next = new Set(prev);
      if (next.has(txId)) next.delete(txId);
      else next.add(txId);
      return next;
    });
  };

  const selectVisibleTransactions = () => {
    setSelectedTxIds(new Set(visibleTransactionIds));
  };

  const clearSelection = () => {
    setSelectedTxIds(new Set());
  };

  const applyBulkCategoryUpdate = async () => {
    if (!userId || selectedTxIds.size === 0) return;
    const ids = Array.from(selectedTxIds);
    setBulkUpdatingCategory(true);
    try {
      const { error: updateError } = await supabase
        .from("transactions")
        .update({ category: bulkCategoryValue })
        .eq("user_id", userId)
        .in("id", ids);

      if (updateError) throw updateError;

      setTransactions((prev) =>
        prev.map((tx) =>
          selectedTxIds.has(tx.id)
            ? {
              ...tx,
              category: bulkCategoryValue,
            }
            : tx,
        ),
      );
      setMessage(`Updated category for ${ids.length} transactions.`);
      clearSelection();
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Unable to update selected transactions.");
    } finally {
      setBulkUpdatingCategory(false);
    }
  };

  const toggleBulkMode = () => {
    setBulkMode((prev) => {
      if (prev) {
        clearSelection();
      }
      return !prev;
    });
  };

  const scrollToTransactionRow = (txId: string) => {
    if (typeof window === "undefined") return;
    let attempts = 0;
    const maxAttempts = 12;

    const tryScroll = () => {
      attempts += 1;
      const selector = `[data-tx-row-id="${txId.replace(/"/g, "\\\"")}"]`;
      const row = document.querySelector(selector) as HTMLElement | null;
      if (row) {
        row.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }

      if (attempts < maxAttempts) {
        window.setTimeout(tryScroll, 80);
      }
    };

    window.setTimeout(tryScroll, 0);
  };

  const handleDataImport = async (file: File) => {
    if (!userId) throw new Error("No authenticated user found.");

    const {
      data: { session },
    } = await supabase.auth.getSession();

    const accessToken = session?.access_token;
    if (!accessToken) {
      throw new Error("Authentication session expired. Please log in again.");
    }

    const detectStatementFormat = (fields: string[]): CsvFormat | null => {
      const hasGoogle = fields.includes("time") && fields.includes("transactionid") && fields.includes("amount");
      const hasBankClassic = fields.some((field) => field.includes("withdrawal")) && fields.some((field) => field.includes("deposit"));
      const hasBankRemarks =
        (fields.includes("withdrawalamountinr") || fields.includes("debitamount") || fields.includes("debit")) &&
        (fields.includes("depositamountinr") || fields.includes("creditamount") || fields.includes("credit"));
      const hasUpi = fields.includes("timestamp") && fields.includes("merchantcategory") && fields.includes("amountinr");
      const hasGeneric = fields.includes("date") && fields.includes("description") && fields.includes("amount");

      if (hasGoogle) return "google";
      if (hasUpi) return "upi";
      if (hasBankClassic || hasBankRemarks) return "bank";
      if (hasGeneric) return "generic";
      return null;
    };

    const mapRowToInsert = (row: Record<string, unknown>, format: CsvFormat): InsertTransaction | null => {
      const normalized = new Map<string, string>();
      for (const [key, value] of Object.entries(row)) {
        normalized.set(normalizeHeader(key), toText(value));
      }

      if (format === "google") {
        const status = normalizeStatus(normalized.get("status") ?? "completed");
        const amountRaw = parseAmount(normalized.get("amount") ?? "");
        const date = parseDateValue(normalized.get("time") ?? "");
        if (amountRaw === null || amountRaw === 0 || !date) return null;

        let signed = -Math.abs(amountRaw);
        if (status === "refunded") signed = Math.abs(amountRaw);

        const rawDescription = normalized.get("description") || normalized.get("product") || "Imported transaction";
        const description = extractReadableDescription(rawDescription);
        const merchant = extractReadableDescription(normalized.get("product") || rawDescription);

        return {
          user_id: userId,
          transaction_date: date,
          amount: signed,
          currency: "INR",
          description,
          merchant_name: merchant,
          category: guessCategory(`${rawDescription} ${merchant}`),
          payment_method: inferPaymentMethod(normalized.get("paymentmethod") ?? ""),
          status,
          raw_data: row,
        };
      }

      if (format === "bank") {
        const withdrawal =
          parseAmount(normalized.get("withdrawal") ?? "") ??
          parseAmount(normalized.get("withdrawalamountinr") ?? "") ??
          parseAmount(normalized.get("debit") ?? "") ??
          parseAmount(normalized.get("debitamount") ?? "") ??
          0;

        const deposit =
          parseAmount(normalized.get("deposit") ?? "") ??
          parseAmount(normalized.get("depositamountinr") ?? "") ??
          parseAmount(normalized.get("credit") ?? "") ??
          parseAmount(normalized.get("creditamount") ?? "") ??
          0;

        const date =
          parseDateValue(normalized.get("transactiondate") ?? "") ||
          parseDateValue(normalized.get("valuedate") ?? "") ||
          parseDateValue(normalized.get("date1") ?? "") ||
          parseDateValue(normalized.get("date") ?? "");

        if ((withdrawal <= 0 && deposit <= 0) || !date) return null;

        const rawDescription =
          normalized.get("transactionremarks") ||
          normalized.get("remarks") ||
          normalized.get("narration") ||
          normalized.get("description") ||
          "Imported bank transaction";

        const description = extractReadableDescription(rawDescription);

        const amount = deposit > 0 ? Math.abs(deposit) : -Math.abs(withdrawal);

        return {
          user_id: userId,
          transaction_date: date,
          amount,
          currency: "INR",
          description,
          merchant_name: description,
          category: guessCategory(rawDescription),
          payment_method: inferPaymentMethod(rawDescription),
          status: "completed",
          raw_data: row,
        };
      }

      if (format === "upi") {
        const amountRaw = parseAmount(normalized.get("amountinr") ?? "");
        const date = parseDateValue(normalized.get("timestamp") ?? "");
        const status = normalizeStatus(normalized.get("transactionstatus") ?? "completed");
        if (amountRaw === null || amountRaw === 0 || !date) return null;

        const typeText = (normalized.get("transactiontype") ?? "").toLowerCase();
        const isCredit = /credit|refund|receive|received|salary|deposit/.test(typeText);
        const amount = isCredit ? Math.abs(amountRaw) : -Math.abs(amountRaw);
        const rawDescription =
          normalized.get("description") ||
          normalized.get("merchant") ||
          normalized.get("merchantname") ||
          `${normalized.get("merchantcategory") || "UPI"} ${normalized.get("transactiontype") ?? ""}`;
        const description = extractReadableDescription(rawDescription);
        const inferredCategory = guessCategory(rawDescription);
        const category = normalized.get("merchantcategory") || (inferredCategory === "Misc" ? "UPI" : inferredCategory);

        return {
          user_id: userId,
          transaction_date: date,
          amount,
          currency: "INR",
          description,
          merchant_name: description,
          category,
          payment_method: "upi",
          status,
          raw_data: row,
        };
      }

      const amountRaw = parseAmount(normalized.get("amount") ?? "");
      const date = parseDateValue(normalized.get("date") ?? "");
      if (amountRaw === null || amountRaw === 0 || !date) return null;

      const type = (normalized.get("type") ?? "expense").toLowerCase();
      const amount = /income|credit|deposit/.test(type) ? Math.abs(amountRaw) : -Math.abs(amountRaw);
      const rawDescription = normalized.get("description") || "Imported transaction";
      const description = extractReadableDescription(rawDescription);

      return {
        user_id: userId,
        transaction_date: date,
        amount,
        currency: "INR",
        description,
        merchant_name: description,
        category: normalized.get("category") || guessCategory(rawDescription),
        payment_method: inferPaymentMethod(normalized.get("paymentmethod") ?? ""),
        status: normalizeStatus(normalized.get("status") ?? "completed"),
        raw_data: row,
      };
    };

    const fileKind = detectImportFileKind(file.name);

    let format: CsvFormat | null = null;
    let nonCsvRows: Record<string, unknown>[] = [];

    if (fileKind === "csv") {
      const preview = await new Promise<Papa.ParseResult<Record<string, unknown>>>((resolve, reject) => {
        Papa.parse<Record<string, unknown>>(file, {
          header: true,
          skipEmptyLines: true,
          preview: 30,
          complete: (result) => resolve(result),
          error: (parseError) => reject(parseError),
        });
      });

      if (preview.errors.length > 0) {
        throw new Error(`CSV parse error: ${preview.errors[0]?.message ?? "Invalid CSV"}`);
      }

      const fields = (preview.meta.fields ?? []).map((f) => normalizeHeader(f));
      format = detectStatementFormat(fields);
    } else {
      const parsed = await parseFileRows(file);
      nonCsvRows = parsed.rows;
      const fields = Object.keys(nonCsvRows[0] ?? {}).map((key) => normalizeHeader(key));
      format = detectStatementFormat(fields);
    }

    if (!format) {
      throw new Error("Unsupported statement format. Try CSV/XLS/XLSX/JSON or export statement as tabular data.");
    }

    const existingFingerprints = new Set(
      transactions.map((t) => {
        const day = t.transaction_date.slice(0, 19);
        return `${day}|${Number(t.amount).toFixed(2)}|${(t.description ?? "").toLowerCase()}`;
      }),
    );

    const newFingerprints = new Set<string>();
    let importedCount = 0;
    let sawAnyRows = false;

    const insertBatch = async (batch: InsertTransaction[]) => {
      if (!batch.length) return;

      for (let i = 0; i < batch.length; i += INSERT_BATCH_SIZE * INSERT_CONCURRENCY) {
        const requests: Promise<number>[] = [];

        for (let j = i; j < Math.min(i + INSERT_BATCH_SIZE * INSERT_CONCURRENCY, batch.length); j += INSERT_BATCH_SIZE) {
          const chunk = batch.slice(j, j + INSERT_BATCH_SIZE);
          requests.push((async () => {
            const payload = chunk.map((item) => ({
              transaction_date: item.transaction_date,
              amount: item.amount,
              currency: item.currency,
              description: item.description,
              merchant_name: item.merchant_name,
              category: item.category,
              payment_method: item.payment_method,
              status: item.status,
              raw_data: item.raw_data,
            }));
            const response = await fetch("/api/import", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${accessToken}`,
              },
              body: JSON.stringify({ transactions: payload }),
            });

            const json = (await response.json().catch(() => null)) as { error?: string; inserted?: number } | null;
            if (!response.ok) {
              throw new Error(json?.error ?? "Batch import failed.");
            }

            return Number(json?.inserted ?? chunk.length);
          })());
        }

        const insertedNow = await Promise.all(requests);
        importedCount += insertedNow.reduce((sum, count) => sum + count, 0);
      }
    };

    if (fileKind === "csv") {
      await new Promise<void>((resolve, reject) => {
        let settled = false;
        let parseComplete = false;
        let queue: Promise<void> = Promise.resolve();

        const fail = (error: unknown) => {
          if (settled) return;
          settled = true;
          reject(error);
        };

        const finishIfDone = () => {
          if (!parseComplete || settled) return;
          queue
            .then(() => {
              if (settled) return;
              settled = true;
              resolve();
            })
            .catch(fail);
        };

        Papa.parse<Record<string, unknown>>(file, {
          header: true,
          skipEmptyLines: true,
          worker: true,
          chunkSize: PARSE_CHUNK_SIZE,
          chunk: (results) => {
            queue = queue.then(async () => {
              if (results.errors.length > 0) {
                throw new Error(`CSV parse error: ${results.errors[0]?.message ?? "Invalid CSV"}`);
              }

              const chunkRows = results.data;
              if (chunkRows.length > 0) sawAnyRows = true;

              const inserts: InsertTransaction[] = [];
              for (const row of chunkRows) {
                const tx = mapRowToInsert(row, format);
                if (!tx) continue;

                const fingerprint = `${tx.transaction_date.slice(0, 19)}|${tx.amount.toFixed(2)}|${tx.description.toLowerCase()}`;
                if (existingFingerprints.has(fingerprint) || newFingerprints.has(fingerprint)) continue;

                newFingerprints.add(fingerprint);
                inserts.push(tx);
              }

              await insertBatch(inserts);

              const cursor = Number(results.meta.cursor ?? 0);
              if (file.size > 0 && Number.isFinite(cursor) && cursor > 0) {
                setImportProgress(Math.min(99, Math.round((cursor / file.size) * 100)));
              }
            });

            queue.catch(fail);
          },
          complete: () => {
            parseComplete = true;
            finishIfDone();
          },
          error: (parseError) => fail(parseError),
        });
      });
    } else {
      const rows = nonCsvRows;
      if (!rows.length) {
        throw new Error("No rows found in file. If this is a PDF, export it as CSV/Excel for better accuracy.");
      }

      let processed = 0;
      for (let i = 0; i < rows.length; i += INSERT_BATCH_SIZE) {
        const sourceChunk = rows.slice(i, i + INSERT_BATCH_SIZE);
        const inserts: InsertTransaction[] = [];

        for (const row of sourceChunk) {
          const tx = mapRowToInsert(row, format);
          if (!tx) continue;

          const fingerprint = `${tx.transaction_date.slice(0, 19)}|${tx.amount.toFixed(2)}|${tx.description.toLowerCase()}`;
          if (existingFingerprints.has(fingerprint) || newFingerprints.has(fingerprint)) continue;

          newFingerprints.add(fingerprint);
          inserts.push(tx);
        }

        if (sourceChunk.length > 0) sawAnyRows = true;
        await insertBatch(inserts);

        processed += sourceChunk.length;
        setImportProgress(Math.min(99, Math.round((processed / rows.length) * 100)));
      }
    }

    setImportProgress(100);

    if (!sawAnyRows) {
      throw new Error("No rows found in file.");
    }

    if (!importedCount) {
      throw new Error("No transactions found to import (all rows were invalid or already imported).");
    }

    return importedCount;
  };

  const onSelectFile: React.ChangeEventHandler<HTMLInputElement> = async (event) => {
    if (saving) {
      event.target.value = "";
      return;
    }

    const file = event.target.files?.[0];
    if (!file) return;

    setSaving(true);
    setImportProgress(0);
    setError(null);
    setMessage(null);
    try {
      const count = await handleDataImport(file);
      await fetchTransactions();
      setTab("all");
      listRef.current?.scrollTo({ top: 0, behavior: "auto" });
      setMessage(`Imported ${count} transactions from ${file.name}.`);
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : "Import failed.");
    } finally {
      event.target.value = "";
      setSaving(false);
      setImportProgress(null);
    }
  };

  // Animation variants
  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.05 }
    }
  };

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: 10 },
    visible: { opacity: 1, y: 0 }
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
        {saving && (
          <div className="absolute inset-0 z-30 flex items-center justify-center rounded-[2.5rem] bg-[#0b1324]/75 backdrop-blur-sm">
            <div className="flex flex-col items-center gap-3 rounded-2xl border border-white/10 bg-black/30 px-6 py-5 text-center">
              <Loader2 className="h-6 w-6 animate-spin text-blue-400" />
              <p className="text-sm font-semibold text-white">
                {importProgress !== null ? `Import in progress: ${importProgress}%` : "Import in progress"}
              </p>
              <p className="text-xs text-gray-300">Please wait. Controls are locked until import completes.</p>
            </div>
          </div>
        )}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-4xl font-black tracking-tight text-foreground">
              Transactions
              <span className="ml-2 text-lg font-medium text-muted-foreground">History</span>
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">View and manage your financial activity.</p>
          </div>

          <div className="flex items-center gap-3 md:flex-nowrap">
            <div className="relative group w-72">
              <Search className="pointer-events-none absolute left-4 top-3 h-4 w-4 text-gray-400 group-focus-within:text-blue-400 transition-colors" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by merchant, category..."
                className="w-full rounded-2xl border border-border bg-secondary/30 px-10 py-2.5 text-sm text-foreground outline-none focus:border-primary focus:bg-secondary transition-all placeholder:text-muted-foreground"
              />
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="button"
              data-filter-trigger="true"
              onClick={() => setIsFilterOpen((prev) => !prev)}
              className={`inline-flex items-center gap-2 rounded-2xl border px-5 py-2.5 text-sm font-bold transition-all ${isFilterOpen
                ? "border-primary/50 bg-primary/10 text-primary"
                : "border-border bg-secondary/30 text-muted-foreground hover:bg-secondary"
                }`}
            >
              <Filter className="h-4 w-4" />
              <span>Filters</span>
              <ChevronDown className={`h-4 w-4 transition-transform ${isFilterOpen ? "rotate-180" : ""}`} />
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="button"
              onClick={() => {
                if (saving) return;
                fileInputRef.current?.click();
              }}
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-2xl bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground shadow-lg shadow-primary/20 hover:shadow-primary/40 transition-shadow disabled:cursor-not-allowed disabled:opacity-70 disabled:hover:shadow-primary/20"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              {saving && importProgress !== null ? `Importing ${importProgress}%` : "Import Data"}
            </motion.button>
            <input ref={fileInputRef} type="file" accept=".csv,.tsv,.xls,.xlsx,.xlsm,.json,.txt,.pdf" className="hidden" onChange={onSelectFile} disabled={saving} />
          </div>
        </div>

        {/* Tab Selection */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex p-1 gap-1 bg-muted/30 rounded-2xl border border-border w-fit">
            {(["all", "debit", "credit"] as const).map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => setTab(name)}
                className={`relative px-6 py-2 rounded-xl text-sm font-bold transition-all ${tab === name ? "text-foreground shadow-sm bg-background ring-1 ring-border" : "text-muted-foreground hover:text-foreground"
                  }`}
              >
                {tab === name && (
                  <motion.div
                    layoutId="activeTab"
                    className="absolute inset-0 bg-white/5 rounded-xl"
                    initial={false}
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                  />
                )}
                <span className="relative z-10 capitalize flex items-center gap-2">
                  {name}
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${tab === name ? "bg-white/20" : "bg-white/5"}`}>
                    {tabCounts[name]}
                  </span>
                </span>
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 rounded-2xl border border-border bg-muted/30 px-3 py-2">
            {!bulkMode ? (
              <button
                type="button"
                onClick={toggleBulkMode}
                className="rounded-lg border border-border bg-secondary/30 px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-secondary"
              >
                Bulk Actions
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={selectVisibleTransactions}
                  className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-gray-200 hover:bg-white/10"
                >
                  Select Visible ({visibleTransactionIds.length})
                </button>
                <button
                  type="button"
                  onClick={clearSelection}
                  disabled={selectedCount === 0}
                  className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-gray-300 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Clear
                </button>
                <span className="text-xs font-semibold text-blue-300">{selectedCount} selected</span>
                <select
                  value={bulkCategoryValue}
                  onChange={(event) => setBulkCategoryValue(event.target.value)}
                  className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-white outline-none"
                  disabled={selectedCount === 0 || bulkUpdatingCategory}
                >
                  {categoryOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={applyBulkCategoryUpdate}
                  disabled={selectedCount === 0 || bulkUpdatingCategory}
                  className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {bulkUpdatingCategory ? "Updating..." : "Apply"}
                </button>
                <button
                  type="button"
                  onClick={toggleBulkMode}
                  className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-gray-300 hover:bg-white/10"
                >
                  Done
                </button>
              </>
            )}
          </div>
        </div>

        <AnimatePresence>
          {isFilterOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div data-filter-panel="true" className="mt-2 rounded-3xl border border-border bg-card/95 p-6 backdrop-blur-sm shadow-xl">
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
                  {/* Period */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-wider text-gray-500">Period</label>
                    <div className="grid grid-cols-2 gap-2">
                      <select
                        value={draftFilters.year}
                        onChange={(e) => setDraftFilters(p => ({ ...p, year: e.target.value, relative: e.target.value === "all" ? p.relative : "none" }))}
                        className="w-full rounded-xl border border-border bg-secondary/30 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                      >
                        {years.map(y => <option key={y} value={y}>{y === "all" ? "All Years" : y}</option>)}
                      </select>
                      <select
                        value={draftFilters.month}
                        onChange={(e) => setDraftFilters(p => ({ ...p, month: e.target.value }))}
                        disabled={draftFilters.year === "all"}
                        className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none disabled:opacity-50"
                      >
                        <option value="all">All Months</option>
                        {Array.from({ length: 12 }).map((_, i) => <option key={i} value={String(i)}>{monthName(i)}</option>)}
                      </select>
                    </div>
                  </div>

                  {/* Relative */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-wider text-gray-500">Quick Range</label>
                    <select
                      value={draftFilters.relative}
                      onChange={(e) => setDraftFilters(p => ({ ...p, relative: e.target.value as RelativeRange, year: e.target.value === "none" ? p.year : "all", month: "all" }))}
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
                    <label className="text-xs font-bold uppercase tracking-wider text-gray-500">Category</label>
                    <select
                      value={draftFilters.category}
                      onChange={(e) => setDraftFilters(p => ({ ...p, category: e.target.value }))}
                      className="w-full rounded-xl border border-border bg-secondary/30 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                    >
                      {categories.map(c => <option key={c} value={c}>{c === "all" ? "All Categories" : c}</option>)}
                    </select>
                  </div>

                  {/* Amount Range */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-wider text-gray-500">Amount Range</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        placeholder="Min"
                        value={draftFilters.minAmount}
                        onChange={(e) => setDraftFilters(p => ({ ...p, minAmount: e.target.value }))}
                        className="w-full rounded-xl border border-border bg-secondary/30 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                      />
                      <span className="text-muted-foreground">-</span>
                      <input
                        type="number"
                        placeholder="Max"
                        value={draftFilters.maxAmount}
                        onChange={(e) => setDraftFilters(p => ({ ...p, maxAmount: e.target.value }))}
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
      <motion.div
        ref={listRef}
        key={tab}
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="min-h-0 flex-1 overflow-y-auto pr-2 custom-scrollbar space-y-6 pb-20"
      >
        {groupedTransactions.length === 0 ? (
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
            <button onClick={clearFilters} className="mt-6 text-blue-400 font-bold hover:underline">Clear all filters</button>
          </motion.div>
        ) : (
          groupedTransactions.map((group) => {
            const headerLabel = tab === "credit" ? "Total Credited" : tab === "debit" ? "Total Spent" : "Net Total";
            const headerValue = tab === "credit" ? group.credited : tab === "debit" ? group.spent : group.net;
            const headerColor =
              tab === "credit" ? "text-emerald-400" :
                tab === "debit" ? "text-red-400" :
                  headerValue >= 0 ? "text-emerald-400" : "text-red-400";

            return (
              <motion.div
                key={group.key}
                variants={itemVariants}
                className="rounded-[2rem] border border-border bg-card overflow-hidden shadow-lg"
              >
                <div className="flex items-center justify-between bg-muted/30 px-8 py-5 border-b border-border">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-primary/80 mb-0.5">{group.year}</p>
                    <h3 className="text-2xl font-black text-foreground">{monthName(group.month)}</h3>
                  </div>
                  <div className="text-right">
                    <p className="text-xs uppercase font-bold text-muted-foreground mb-0.5">{headerLabel}</p>
                    <p className={`text-2xl font-mono font-bold ${headerColor}`}>
                      {tab === "all" && headerValue > 0 ? "+" : ""}
                      {tab === "all" && headerValue < 0 ? "-" : ""}
                      ₹{Math.abs(headerValue).toLocaleString("en-IN")}
                    </p>
                  </div>
                </div>
                <div className="divide-y divide-white/5">
                  {group.rows.map((tx) => {
                    const amount = Number(tx.amount || 0);
                    const isCredit = amount >= 0;
                    const status = normalizeStatus(tx.status ?? "completed");
                    return (
                      <motion.div
                        key={tx.id}
                        data-tx-row-id={tx.id}
                        whileHover={{ backgroundColor: "var(--accent)" }}
                        onClick={() => setSelected(tx)}
                        className={`flex cursor-pointer items-center justify-between px-6 py-4 transition-colors group ${bulkMode && selectedTxIds.has(tx.id) ? "bg-blue-500/10" : ""} ${spotlightTxId === tx.id ? "ring-1 ring-blue-400/50 bg-blue-500/10" : ""}`}
                      >
                        <div className="flex items-center gap-5 min-w-0">
                          {bulkMode && (
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                toggleTransactionSelection(tx.id);
                              }}
                              className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${selectedTxIds.has(tx.id)
                                ? "border-blue-400 bg-blue-500 text-white"
                                : "border-white/20 bg-white/5 text-transparent hover:border-blue-400"
                                }`}
                              title={selectedTxIds.has(tx.id) ? "Deselect transaction" : "Select transaction"}
                            >
                              <Check className="h-3.5 w-3.5" />
                            </button>
                          )}
                          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-muted/30 text-xl border border-border/50 group-hover:border-border group-hover:bg-muted/50 transition-colors">
                            {categoryIcon(tx.category ?? "Misc")}
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-3">
                              <p className="truncate text-base font-bold text-foreground group-hover:text-primary transition-colors">
                                {tx.description || "Transaction"}
                              </p>
                              {status !== "completed" && (
                                <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wide border ${status === "failed" ? "bg-red-500/10 text-red-500 border-red-500/20" :
                                  "bg-yellow-500/10 text-yellow-500 border-yellow-500/20"
                                  }`}>
                                  {status}
                                </span>
                              )}
                            </div>
                            <div className="mt-0.5 flex items-center gap-2">
                              <p className="text-xs font-medium text-muted-foreground">
                                {new Date(tx.transaction_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", weekday: 'short' })}
                              </p>
                              <span className="h-1 w-1 rounded-full bg-muted-foreground/30" />
                              {editingCategoryTxId === tx.id ? (
                                <div
                                  data-category-editor="true"
                                  className="flex items-center gap-1"
                                  onClick={(event) => event.stopPropagation()}
                                >
                                  <select
                                    value={editingCategoryValue}
                                    onChange={(event) => setEditingCategoryValue(event.target.value)}
                                    className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[11px] font-medium text-white outline-none"
                                    disabled={updatingCategory}
                                  >
                                    {categoryOptions.map((option) => (
                                      <option key={option} value={option}>
                                        {option}
                                      </option>
                                    ))}
                                  </select>
                                  <button
                                    type="button"
                                    onClick={saveCategoryEdit}
                                    disabled={updatingCategory}
                                    className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-1 text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-60"
                                    title="Save category"
                                  >
                                    <Check className="h-3.5 w-3.5" />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setEditingCategoryTxId(null)}
                                    disabled={updatingCategory}
                                    className="rounded-md border border-white/15 bg-white/5 p-1 text-gray-300 hover:bg-white/10 disabled:opacity-60"
                                    title="Cancel"
                                  >
                                    <X className="h-3.5 w-3.5" />
                                  </button>
                                </div>
                              ) : (
                                <>
                                  <p className="max-w-[140px] truncate text-xs font-medium text-gray-500">{tx.category}</p>
                                  <button
                                    type="button"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      startCategoryEdit(tx);
                                    }}
                                    data-category-edit-trigger="true"
                                    className="rounded-md border border-white/10 bg-white/5 p-1 text-gray-400 hover:border-blue-500/30 hover:bg-blue-500/10 hover:text-blue-300"
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
                          <p className={`font-mono text-lg font-bold ${isCredit ? "text-emerald-400" : "text-red-400"}`}>
                            {isCredit ? "+" : ""}₹{Math.abs(amount).toLocaleString("en-IN")}
                          </p>
                          <p className="text-[10px] font-bold uppercase text-muted-foreground mt-0.5">{tx.payment_method}</p>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              </motion.div>
            );
          })
        )}
      </motion.div>

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
                  {categoryIcon(selected.category ?? "Misc")}
                </div>
                <h3 className="text-center text-2xl font-black text-foreground px-4 leading-tight">
                  {selected.description || "Transaction"}
                </h3>
                <p className="mt-2 text-sm font-medium text-primary/70 uppercase tracking-widest">
                  {selected.category || "Uncategorized"}
                </p>
                <h2 className={`mt-6 font-mono text-5xl font-black tracking-tighter ${Number(selected.amount) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {Number(selected.amount) >= 0 ? "+" : ""}₹{Math.abs(Number(selected.amount)).toLocaleString("en-IN")}
                </h2>
                <div className="mt-4 flex gap-2">
                  <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-bold text-gray-400 uppercase">
                    {normalizeStatus(selected.status ?? "completed")}
                  </span>
                  <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-bold text-gray-400 uppercase">
                    {selected.payment_method || "Unknown Method"}
                  </span>
                </div>
              </div>

              <div className="bg-muted/20 px-6 py-6 border-t border-border space-y-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground font-medium">Date & Time</span>
                  <span className="text-foreground font-bold">
                    {new Date(selected.transaction_date).toLocaleString("en-IN", {
                      weekday: "short",
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                <div className="h-px bg-white/5 w-full" />
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500 font-medium">Merchant / Ref</span>
                  <span className="text-white font-bold truncate max-w-[200px]">
                    {selected.merchant_name || selected.description || "-"}
                  </span>
                </div>
                <div className="h-px bg-white/5 w-full" />
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500 font-medium">Transaction ID</span>
                  <span className="text-gray-400 font-mono text-xs truncate max-w-[180px]" title={selected.id}>{selected.id}</span>
                </div>

              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
