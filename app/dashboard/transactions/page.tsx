"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Papa from "papaparse";
import {
  ChevronDown,
  Download,
  Filter,
  Loader2,
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

function parseDateValue(value: string): string | null {
  const raw = value.trim();
  if (!raw) return null;

  const direct = new Date(raw.replace("Sept", "Sep"));
  if (!Number.isNaN(direct.getTime())) return direct.toISOString();

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

  const slash = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})$/);
  if (slash) {
    const day = Number.parseInt(slash[1], 10);
    const month = Number.parseInt(slash[2], 10) - 1;
    const yearRaw = Number.parseInt(slash[3], 10);
    const year = yearRaw < 100 ? 2000 + yearRaw : yearRaw;
    const date = new Date(year, month, day);
    if (!Number.isNaN(date.getTime())) return date.toISOString();
  }

  const iso = new Date(raw.replace(" ", "T"));
  if (!Number.isNaN(iso.getTime())) return iso.toISOString();
  return null;
}

function guessCategory(description: string): string {
  const source = description.toLowerCase();
  if (source.includes("food") || source.includes("dining") || source.includes("restaurant")) return "Food";
  if (source.includes("shop") || source.includes("mart")) return "Shopping";
  if (source.includes("grocery")) return "Grocery";
  if (source.includes("rent") || source.includes("bill") || source.includes("utility")) return "Utilities";
  if (source.includes("fuel") || source.includes("petrol") || source.includes("transport")) return "Transport";
  if (source.includes("salary") || source.includes("income")) return "Income";
  return "Misc";
}

function categoryIcon(category: string): string {
  const key = category.toLowerCase();
  if (key.includes("food")) return "🍔";
  if (key.includes("shop")) return "🛍️";
  if (key.includes("grocery")) return "🛒";
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

    setTransactions(
      allRows.map((row) => ({
        id: toText(row.id),
        user_id: toText(row.user_id),
        transaction_date: toText(row.transaction_date),
        amount: Number(row.amount ?? 0),
        description: toText(row.description) || null,
        merchant_name: toText(row.merchant_name) || null,
        category: toText(row.category) || "Misc",
        payment_method: toText(row.payment_method) || "unknown",
        status: toText(row.status) || "completed",
        currency: toText(row.currency) || "INR",
      })),
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

  const clearFilters = () => {
    setDraftFilters(defaultFilters);
    setFilters(defaultFilters);
    setIsFilterOpen(false);
  };

  const handleCsvImport = async (file: File) => {
    if (!userId) throw new Error("No authenticated user found.");

    const {
      data: { session },
    } = await supabase.auth.getSession();

    const accessToken = session?.access_token;
    if (!accessToken) {
      throw new Error("Authentication session expired. Please log in again.");
    }

    const preview = await new Promise<Papa.ParseResult<Record<string, unknown>>>((resolve, reject) => {
      Papa.parse<Record<string, unknown>>(file, {
        header: true,
        skipEmptyLines: true,
        preview: 20,
        complete: (result) => resolve(result),
        error: (parseError) => reject(parseError),
      });
    });

    if (preview.errors.length > 0) {
      throw new Error(`CSV parse error: ${preview.errors[0]?.message ?? "Invalid CSV"}`);
    }

    const fields = (preview.meta.fields ?? []).map((f) => normalizeHeader(f));
    const hasGoogle = fields.includes("time") && fields.includes("transactionid") && fields.includes("amount");
    const hasBank = fields.includes("withdrawal") && fields.includes("deposit");
    const hasUpi = fields.includes("timestamp") && fields.includes("merchantcategory") && fields.includes("amountinr");
    const hasGeneric = fields.includes("date") && fields.includes("description") && fields.includes("amount");

    let format: CsvFormat | null = null;
    if (hasGoogle) format = "google";
    else if (hasBank) format = "bank";
    else if (hasUpi) format = "upi";
    else if (hasGeneric) format = "generic";

    if (!format) {
      throw new Error("Unsupported CSV format. Please upload a supported bank/UPI export.");
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

    const mapRowToInsert = (row: Record<string, unknown>): InsertTransaction | null => {
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

        const description = normalized.get("description") || normalized.get("product") || "Imported transaction";
        const merchant = normalized.get("product") || description;

        return {
          user_id: userId,
          transaction_date: date,
          amount: signed,
          currency: "INR",
          description,
          merchant_name: merchant,
          category: guessCategory(`${description} ${merchant}`),
          payment_method: inferPaymentMethod(normalized.get("paymentmethod") ?? ""),
          status,
          raw_data: row,
        };
      }

      if (format === "bank") {
        const withdrawal = parseAmount(normalized.get("withdrawal") ?? "") ?? 0;
        const deposit = parseAmount(normalized.get("deposit") ?? "") ?? 0;
        const date = parseDateValue(normalized.get("date1") ?? "") || parseDateValue(normalized.get("date") ?? "");
        if ((withdrawal <= 0 && deposit <= 0) || !date) return null;

        const category = normalized.get("category") || "Misc";
        const amount = deposit > 0 ? Math.abs(deposit) : -Math.abs(withdrawal);
        const ref = normalized.get("refno") ?? "";

        return {
          user_id: userId,
          transaction_date: date,
          amount,
          currency: "INR",
          description: `${category}${ref ? ` (${ref})` : ""}`,
          merchant_name: category,
          category,
          payment_method: "bank transfer",
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
        const category = normalized.get("merchantcategory") || "Misc";

        return {
          user_id: userId,
          transaction_date: date,
          amount,
          currency: "INR",
          description: `${category} ${normalized.get("transactiontype") ?? "UPI"}`.trim(),
          merchant_name: category,
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
      const description = normalized.get("description") || "Imported transaction";

      return {
        user_id: userId,
        transaction_date: date,
        amount,
        currency: "INR",
        description,
        merchant_name: description,
        category: normalized.get("category") || guessCategory(description),
        payment_method: inferPaymentMethod(normalized.get("paymentmethod") ?? ""),
        status: normalizeStatus(normalized.get("status") ?? "completed"),
        raw_data: row,
      };
    };

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
              const tx = mapRowToInsert(row);
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

    setImportProgress(100);

    if (!sawAnyRows) {
      throw new Error("No rows found in CSV.");
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
      const count = await handleCsvImport(file);
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

      <section className="relative flex flex-col gap-6 rounded-[2.5rem] border border-white/10 bg-gradient-to-br from-[#121b2e] to-[#0d1424] p-8 shadow-2xl">
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
            <h2 className="text-4xl font-black tracking-tight text-white">
              Transactions
              <span className="ml-2 text-lg font-medium text-gray-500">History</span>
            </h2>
            <p className="mt-1 text-sm text-gray-400">View and manage your financial activity.</p>
          </div>

          <div className="flex items-center gap-3 md:flex-nowrap">
            <div className="relative group w-72">
              <Search className="pointer-events-none absolute left-4 top-3 h-4 w-4 text-gray-400 group-focus-within:text-blue-400 transition-colors" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by merchant, category..."
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-10 py-2.5 text-sm text-white outline-none focus:border-blue-500/50 focus:bg-white/10 transition-all placeholder:text-gray-500"
              />
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="button"
              onClick={() => setIsFilterOpen((prev) => !prev)}
              className={`inline-flex items-center gap-2 rounded-2xl border px-5 py-2.5 text-sm font-bold transition-all ${isFilterOpen
                ? "border-blue-500/50 bg-blue-500/10 text-blue-400"
                : "border-white/10 bg-white/5 text-gray-300 hover:bg-white/10"
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
              className="inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-blue-600 to-blue-500 px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-blue-500/20 hover:shadow-blue-500/40 transition-shadow disabled:cursor-not-allowed disabled:opacity-70 disabled:hover:shadow-blue-500/20"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              {saving && importProgress !== null ? `Importing ${importProgress}%` : "Import CSV"}
            </motion.button>
            <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={onSelectFile} disabled={saving} />
          </div>
        </div>

        {/* Tab Selection */}
        <div className="flex p-1 gap-1 bg-black/20 rounded-2xl border border-white/5 w-fit">
          {(["all", "debit", "credit"] as const).map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => setTab(name)}
              className={`relative px-6 py-2 rounded-xl text-sm font-bold transition-all ${tab === name ? "text-white shadow-lg bg-white/10 ring-1 ring-white/10" : "text-gray-400 hover:text-white"
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

        <AnimatePresence>
          {isFilterOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="mt-2 rounded-3xl border border-white/10 bg-black/20 p-6 backdrop-blur-sm">
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
                  {/* Period */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-wider text-gray-500">Period</label>
                    <div className="grid grid-cols-2 gap-2">
                      <select
                        value={draftFilters.year}
                        onChange={(e) => setDraftFilters(p => ({ ...p, year: e.target.value, relative: e.target.value === "all" ? p.relative : "none" }))}
                        className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-blue-500/50"
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
                      className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-blue-500/50"
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
                      className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-blue-500/50"
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
                        className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-blue-500/50"
                      />
                      <span className="text-gray-600">-</span>
                      <input
                        type="number"
                        placeholder="Max"
                        value={draftFilters.maxAmount}
                        onChange={(e) => setDraftFilters(p => ({ ...p, maxAmount: e.target.value }))}
                        className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-blue-500/50"
                      />
                    </div>
                  </div>
                </div>

                <div className="mt-6 flex justify-end gap-3 border-t border-white/5 pt-4">
                  <button
                    onClick={clearFilters}
                    className="px-4 py-2 text-sm font-semibold text-gray-400 hover:text-white"
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
            <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-white/5 border border-white/10">
              <Search className="h-8 w-8 text-gray-400" />
            </div>
            <h3 className="text-xl font-bold text-white">No transactions found</h3>
            <p className="mt-2 text-gray-400 max-w-sm">
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
                className="rounded-[2rem] border border-white/10 bg-[#0B1221] overflow-hidden shadow-lg"
              >
                <div className="flex items-center justify-between bg-gradient-to-r from-blue-900/20 to-transparent px-8 py-5 border-b border-white/5">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-blue-400/80 mb-0.5">{group.year}</p>
                    <h3 className="text-2xl font-black text-white">{monthName(group.month)}</h3>
                  </div>
                  <div className="text-right">
                    <p className="text-xs uppercase font-bold text-gray-500 mb-0.5">{headerLabel}</p>
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
                        whileHover={{ backgroundColor: "rgba(255,255,255,0.03)" }}
                        onClick={() => setSelected(tx)}
                        className="flex cursor-pointer items-center justify-between px-6 py-4 transition-colors group"
                      >
                        <div className="flex items-center gap-5 min-w-0">
                          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/5 text-xl border border-white/5 group-hover:border-white/10 group-hover:bg-white/10 transition-colors">
                            {categoryIcon(tx.category ?? "Misc")}
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-3">
                              <p className="truncate text-base font-bold text-white group-hover:text-blue-400 transition-colors">
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
                            <div className="flex items-center gap-2 mt-0.5">
                              <p className="text-xs font-medium text-gray-500">
                                {new Date(tx.transaction_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", weekday: 'short' })}
                              </p>
                              <span className="h-1 w-1 rounded-full bg-gray-700" />
                              <p className="text-xs font-medium text-gray-500 truncate max-w-[150px]">
                                {tx.category}
                              </p>
                            </div>
                          </div>
                        </div>
                        <div className="text-right pl-4">
                          <p className={`font-mono text-lg font-bold ${isCredit ? "text-emerald-400" : "text-red-400"}`}>
                            {isCredit ? "+" : ""}₹{Math.abs(amount).toLocaleString("en-IN")}
                          </p>
                          <p className="text-[10px] font-bold uppercase text-gray-600 mt-0.5">{tx.payment_method}</p>
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
              className="relative w-full max-w-lg overflow-hidden rounded-[2.5rem] border border-white/10 bg-[#121b2e] shadow-2xl"
            >
              <div className="absolute top-0 right-0 p-6 z-10">
                <button
                  onClick={() => setSelected(null)}
                  className="rounded-full bg-black/20 p-2 text-white/50 hover:text-white hover:bg-black/40 transition-colors"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="flex flex-col items-center pt-10 pb-8 px-6 bg-gradient-to-b from-blue-500/10 to-transparent">
                <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-[2rem] bg-gradient-to-br from-blue-500 to-indigo-600 text-4xl shadow-lg shadow-blue-500/20">
                  {categoryIcon(selected.category ?? "Misc")}
                </div>
                <h3 className="text-center text-2xl font-black text-white px-4 leading-tight">
                  {selected.description || "Transaction"}
                </h3>
                <p className="mt-2 text-sm font-medium text-blue-300/70 uppercase tracking-widest">
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

              <div className="bg-[#0b1221] px-6 py-6 border-t border-white/5 space-y-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500 font-medium">Date & Time</span>
                  <span className="text-white font-bold">
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
