"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Papa from "papaparse";
import {
  Calendar,
  ChevronDown,
  Download,
  Filter,
  Loader2,
  Search,
  X,
} from "lucide-react";
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

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => setMessage(null), 3500);
    return () => clearTimeout(timer);
  }, [message]);

  const fetchTransactions = useCallback(async () => {
    const {
      data: { user },
      error: userError,
    } = await supabase.auth.getUser();

    if (userError || !user) {
      router.replace("/login");
      return;
    }

    setUserId(user.id);

    const { data, error: txError } = await supabase
      .from("transactions")
      .select(
        "id,user_id,transaction_date,amount,description,merchant_name,category,payment_method,status,currency",
      )
      .eq("user_id", user.id)
      .order("transaction_date", { ascending: false })
      .limit(3000);

    if (txError) throw txError;

    setTransactions(
      ((data ?? []) as Record<string, unknown>[]).map((row) => ({
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
  }, [router]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        await fetchTransactions();
      } catch (fetchError) {
        if (mounted) {
          setError(fetchError instanceof Error ? fetchError.message : "Unable to load transactions.");
        }
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [fetchTransactions]);

  const categories = useMemo(() => {
    const values = new Set<string>();
    for (const tx of transactions) {
      if (tx.category) values.add(tx.category);
    }
    return ["all", ...Array.from(values).sort((a, b) => a.localeCompare(b))];
  }, [transactions]);

  const paymentMethods = useMemo(() => {
    const values = new Set<string>();
    for (const tx of transactions) {
      if (tx.payment_method) values.add(tx.payment_method);
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

    const text = await file.text();
    const parsed = Papa.parse<Record<string, unknown>>(text, { header: true, skipEmptyLines: true });

    if (parsed.errors.length > 0) {
      throw new Error(`CSV parse error: ${parsed.errors[0]?.message ?? "Invalid CSV"}`);
    }

    const rawRows = parsed.data;
    if (!rawRows.length) throw new Error("No rows found in CSV.");

    const fields = (parsed.meta.fields ?? []).map((f) => normalizeHeader(f));
    const hasGoogle = fields.includes("time") && fields.includes("transactionid") && fields.includes("amount");
    const hasBank = fields.includes("withdrawal") && fields.includes("deposit");
    const hasUpi = fields.includes("timestamp") && fields.includes("merchantcategory") && fields.includes("amountinr");
    const hasGeneric = fields.includes("date") && fields.includes("description") && fields.includes("amount");

    if (!hasGoogle && !hasBank && !hasUpi && !hasGeneric) {
      throw new Error("Unsupported CSV format. Please upload a supported bank/UPI export.");
    }

    const existingFingerprints = new Set(
      transactions.map((t) => {
        const day = t.transaction_date.slice(0, 19);
        return `${day}|${Number(t.amount).toFixed(2)}|${(t.description ?? "").toLowerCase()}`;
      }),
    );

    const inserts: InsertTransaction[] = [];
    const newFingerprints = new Set<string>();

    for (const row of rawRows) {
      const normalized = new Map<string, string>();
      for (const [key, value] of Object.entries(row)) {
        normalized.set(normalizeHeader(key), toText(value));
      }

      let tx: InsertTransaction | null = null;

      if (hasGoogle) {
        const status = normalizeStatus(normalized.get("status") ?? "completed");
        const amountRaw = parseAmount(normalized.get("amount") ?? "");
        const date = parseDateValue(normalized.get("time") ?? "");
        if (amountRaw !== null && amountRaw !== 0 && date) {
          let signed = -Math.abs(amountRaw);
          if (status === "refunded") signed = Math.abs(amountRaw);
          const description = normalized.get("description") || normalized.get("product") || "Imported transaction";
          const merchant = normalized.get("product") || description;
          tx = {
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
      } else if (hasBank) {
        const withdrawal = parseAmount(normalized.get("withdrawal") ?? "") ?? 0;
        const deposit = parseAmount(normalized.get("deposit") ?? "") ?? 0;
        const date = parseDateValue(normalized.get("date1") ?? "") || parseDateValue(normalized.get("date") ?? "");
        if ((withdrawal > 0 || deposit > 0) && date) {
          const category = normalized.get("category") || "Misc";
          const amount = deposit > 0 ? Math.abs(deposit) : -Math.abs(withdrawal);
          const ref = normalized.get("refno") ?? "";
          tx = {
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
      } else if (hasUpi) {
        const amountRaw = parseAmount(normalized.get("amountinr") ?? "");
        const date = parseDateValue(normalized.get("timestamp") ?? "");
        const status = normalizeStatus(normalized.get("transactionstatus") ?? "completed");
        if (amountRaw !== null && amountRaw !== 0 && date) {
          const typeText = (normalized.get("transactiontype") ?? "").toLowerCase();
          const isCredit = /credit|refund|receive|received|salary|deposit/.test(typeText);
          const amount = isCredit ? Math.abs(amountRaw) : -Math.abs(amountRaw);
          const category = normalized.get("merchantcategory") || "Misc";
          tx = {
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
      } else if (hasGeneric) {
        const amountRaw = parseAmount(normalized.get("amount") ?? "");
        const date = parseDateValue(normalized.get("date") ?? "");
        if (amountRaw !== null && amountRaw !== 0 && date) {
          const type = (normalized.get("type") ?? "expense").toLowerCase();
          const amount = /income|credit|deposit/.test(type) ? Math.abs(amountRaw) : -Math.abs(amountRaw);
          const description = normalized.get("description") || "Imported transaction";
          tx = {
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
        }
      }

      if (!tx) continue;

      const fingerprint = `${tx.transaction_date.slice(0, 19)}|${tx.amount.toFixed(2)}|${tx.description.toLowerCase()}`;
      if (existingFingerprints.has(fingerprint) || newFingerprints.has(fingerprint)) continue;

      newFingerprints.add(fingerprint);
      inserts.push(tx);
    }

    if (!inserts.length) {
      throw new Error("No transactions found to import (all rows were invalid or already imported).");
    }

    for (let i = 0; i < inserts.length; i += 500) {
      const chunk = inserts.slice(i, i + 500);
      const { error: insertError } = await supabase.from("transactions").insert(chunk);
      if (insertError) throw new Error(insertError.message);
    }

    return inserts.length;
  };

  const onSelectFile: React.ChangeEventHandler<HTMLInputElement> = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const count = await handleCsvImport(file);
      await fetchTransactions();
      setMessage(`Imported ${count} transactions from ${file.name}.`);
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : "Import failed.");
    } finally {
      event.target.value = "";
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[55vh] items-center justify-center">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      {error && <div className="rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}
      {message && (
        <div className="rounded-2xl border border-green-500/40 bg-green-500/10 px-4 py-3 text-sm text-green-200">{message}</div>
      )}

      <section className="rounded-3xl border border-white/10 bg-secondary/70 p-5">
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <h2 className="text-4xl font-black tracking-tight text-white">All Transactions</h2>
          <div className="flex w-full flex-wrap items-center gap-2 md:w-auto md:justify-end">
            <div className="relative w-full sm:w-64">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search transactions..."
                className="w-full rounded-xl border border-white/10 bg-background px-9 py-2 text-sm text-white outline-none focus:border-primary"
              />
            </div>
            <button
              type="button"
              onClick={() => setIsFilterOpen((prev) => !prev)}
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-background px-4 py-2 text-sm font-semibold text-white"
            >
              <Filter className="h-4 w-4" /> Filters <ChevronDown className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              Import Data
            </button>
            <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={onSelectFile} />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {(["all", "debit", "credit"] as const).map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => setTab(name)}
              className={`rounded-2xl border p-4 text-left transition ${
                tab === name ? "border-primary bg-primary/15 text-white" : "border-white/10 bg-background/70 text-gray-300"
              }`}
            >
              <p className="text-xs font-bold uppercase tracking-wide">{name}</p>
              <p className="text-sm text-gray-400">{tabCounts[name]} transactions</p>
            </button>
          ))}
        </div>

        {isFilterOpen && (
          <div className="mt-4 rounded-2xl border border-white/10 bg-background p-4">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase tracking-wide text-gray-400">Specific period (year/month)</label>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <select
                    value={draftFilters.year}
                    onChange={(event) =>
                      setDraftFilters((prev) => ({
                        ...prev,
                        year: event.target.value,
                        relative: event.target.value === "all" ? prev.relative : "none",
                      }))
                    }
                    className="w-full rounded-lg border border-white/10 bg-secondary px-3 py-2 text-sm text-white"
                  >
                    {years.map((year) => (
                      <option key={year} value={year}>
                        {year === "all" ? "All Time" : year}
                      </option>
                    ))}
                  </select>
                  <select
                    value={draftFilters.month}
                    onChange={(event) => setDraftFilters((prev) => ({ ...prev, month: event.target.value }))}
                    disabled={draftFilters.year === "all"}
                    className="w-full rounded-lg border border-white/10 bg-secondary px-3 py-2 text-sm text-white disabled:opacity-50"
                  >
                    <option value="all">All Months</option>
                    {Array.from({ length: 12 }).map((_, index) => (
                      <option key={index} value={String(index)}>
                        {monthName(index)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase tracking-wide text-gray-400">Relative time</label>
                <select
                  value={draftFilters.relative}
                  onChange={(event) =>
                    setDraftFilters((prev) => ({
                      ...prev,
                      relative: event.target.value as RelativeRange,
                      year: event.target.value === "none" ? prev.year : "all",
                      month: event.target.value === "none" ? prev.month : "all",
                    }))
                  }
                  className="w-full rounded-lg border border-white/10 bg-secondary px-3 py-2 text-sm text-white"
                >
                  <option value="none">None</option>
                  <option value="this_week">This Week</option>
                  <option value="this_month">This Month</option>
                  <option value="last_30">Last 30 Days</option>
                  <option value="last_90">Last 90 Days</option>
                  <option value="last_180">Last 6 Months</option>
                  <option value="custom">Custom Range</option>
                </select>
              </div>

              {draftFilters.relative === "custom" && (
                <>
                  <input
                    type="date"
                    value={draftFilters.customStart}
                    onChange={(event) => setDraftFilters((prev) => ({ ...prev, customStart: event.target.value }))}
                    className="rounded-lg border border-white/10 bg-secondary px-3 py-2 text-sm text-white"
                  />
                  <input
                    type="date"
                    value={draftFilters.customEnd}
                    onChange={(event) => setDraftFilters((prev) => ({ ...prev, customEnd: event.target.value }))}
                    className="rounded-lg border border-white/10 bg-secondary px-3 py-2 text-sm text-white"
                  />
                </>
              )}

              <select
                value={draftFilters.category}
                onChange={(event) => setDraftFilters((prev) => ({ ...prev, category: event.target.value }))}
                className="rounded-lg border border-white/10 bg-secondary px-3 py-2 text-sm text-white"
              >
                {categories.map((value) => (
                  <option key={value} value={value}>
                    {value === "all" ? "All Categories" : value}
                  </option>
                ))}
              </select>

              <select
                value={draftFilters.status}
                onChange={(event) => setDraftFilters((prev) => ({ ...prev, status: event.target.value }))}
                className="rounded-lg border border-white/10 bg-secondary px-3 py-2 text-sm text-white"
              >
                <option value="all">All Status</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
                <option value="refunded">Refunded</option>
                <option value="failed">Failed</option>
              </select>

              <div className="flex min-w-0 items-center gap-2">
                <input
                  type="number"
                  placeholder="Min"
                  value={draftFilters.minAmount}
                  onChange={(event) => setDraftFilters((prev) => ({ ...prev, minAmount: event.target.value }))}
                  className="w-full rounded-lg border border-white/10 bg-secondary px-3 py-2 text-sm text-white"
                />
                <span className="text-gray-500">to</span>
                <input
                  type="number"
                  placeholder="Max"
                  value={draftFilters.maxAmount}
                  onChange={(event) => setDraftFilters((prev) => ({ ...prev, maxAmount: event.target.value }))}
                  className="w-full rounded-lg border border-white/10 bg-secondary px-3 py-2 text-sm text-white"
                />
              </div>

              <select
                value={draftFilters.paymentMethod}
                onChange={(event) => setDraftFilters((prev) => ({ ...prev, paymentMethod: event.target.value }))}
                className="rounded-lg border border-white/10 bg-secondary px-3 py-2 text-sm text-white"
              >
                {paymentMethods.map((value) => (
                  <option key={value} value={value}>
                    {value === "all" ? "All Methods" : value}
                  </option>
                ))}
              </select>
            </div>

            <div className="mt-4 flex items-center justify-end gap-2">
              <button type="button" onClick={clearFilters} className="rounded-lg border border-white/10 px-4 py-2 text-sm text-gray-300">
                Clear All
              </button>
              <button type="button" onClick={applyFilters} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white">
                Apply
              </button>
            </div>
          </div>
        )}
      </section>

      {groupedTransactions.length === 0 ? (
        <div className="flex-1 rounded-3xl border border-white/10 bg-secondary/60 p-12 text-center text-gray-400">
          <Calendar className="mx-auto mb-3 h-8 w-8" />
          No transactions match your current filters.
        </div>
      ) : (
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overflow-x-hidden pr-1 [scrollbar-gutter:stable] snap-y snap-mandatory">
          {groupedTransactions.map((group) => {
            const headerLabel = tab === "credit" ? "Total Credited" : tab === "debit" ? "Total Spent" : "Net Total";
            const headerValue = tab === "credit" ? group.credited : tab === "debit" ? group.spent : group.net;
            const headerColor = tab === "credit" ? "text-green-300" : "text-white";
            return (
              <section key={group.key} className="overflow-hidden rounded-3xl border border-white/10 bg-secondary/70 snap-start">
                <div className="flex items-center justify-between bg-gradient-to-r from-black to-gray-800 px-6 py-4">
                  <div>
                    <p className="text-xs text-gray-400">{group.year}</p>
                    <h3 className="text-4xl font-black leading-none text-white">{monthName(group.month)}</h3>
                  </div>
                  <div className="text-right">
                    <p className="text-xs uppercase text-gray-400">{headerLabel}</p>
                    <p className={`text-4xl font-black ${headerColor}`}>
                      {tab === "all" && headerValue < 0 ? "-" : ""}₹{Math.abs(headerValue).toLocaleString("en-IN")}
                    </p>
                  </div>
                </div>

                <div className="divide-y divide-white/5">
                  {group.rows.map((tx) => {
                    const amount = Number(tx.amount || 0);
                    const isCredit = amount >= 0;
                    const status = normalizeStatus(tx.status ?? "completed");
                    return (
                      <button
                        type="button"
                        key={tx.id}
                        onClick={() => setSelected(tx)}
                        className="flex w-full snap-start items-center justify-between px-6 py-4 text-left transition hover:bg-white/5"
                      >
                      <div className="flex min-w-0 items-center gap-4">
                        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10 text-xl">
                          {categoryIcon(tx.category ?? "Misc")}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                              <p className="truncate text-lg font-bold text-white">{tx.description || "Transaction"}</p>
                              {status !== "completed" && (
                                <span className="rounded-full bg-white/10 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-gray-300">
                                  {status}
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-gray-400">
                              {new Date(tx.transaction_date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                            </p>
                          </div>
                        </div>
                        <p className={`shrink-0 text-2xl font-black ${isCredit ? "text-green-400" : "text-red-400"}`}>
                          {isCredit ? "+" : "-"}₹{Math.abs(amount).toLocaleString("en-IN")}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-xl rounded-3xl border border-white/10 bg-secondary p-6">
            <div className="mb-4 flex items-center justify-between">
              <button type="button" onClick={() => setSelected(null)} className="rounded-full bg-white/10 p-2 text-white">
                <X className="h-4 w-4" />
              </button>
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/30 text-2xl">
                {categoryIcon(selected.category ?? "Misc")}
              </div>
              <div className="w-8" />
            </div>

            <div className="mb-5 text-center">
              <h4 className="text-3xl font-black text-white">{selected.description || "Transaction"}</h4>
              <p className="text-gray-400">{selected.merchant_name || selected.category || "Unknown"}</p>
              <p className={`mt-3 text-5xl font-black ${Number(selected.amount) >= 0 ? "text-green-400" : "text-red-400"}`}>
                {Number(selected.amount) >= 0 ? "+" : "-"}₹{Math.abs(Number(selected.amount)).toLocaleString("en-IN")}
              </p>
              <p className="mt-2 text-sm uppercase tracking-wide text-gray-400">{normalizeStatus(selected.status ?? "completed")}</p>
            </div>

            <div className="space-y-2 rounded-2xl bg-background p-4 text-sm text-gray-300">
              <div className="flex justify-between border-b border-white/5 py-2">
                <span>Payment Method</span>
                <span className="font-semibold text-white">{selected.payment_method || "unknown"}</span>
              </div>
              <div className="flex justify-between border-b border-white/5 py-2">
                <span>Transaction ID</span>
                <span className="max-w-[58%] break-all text-right font-semibold text-white">{selected.id}</span>
              </div>
              <div className="flex justify-between border-b border-white/5 py-2">
                <span>Category</span>
                <span className="font-semibold text-white">{selected.category || "Misc"}</span>
              </div>
              <div className="flex justify-between py-2">
                <span>Date</span>
                <span className="font-semibold text-white">
                  {new Date(selected.transaction_date).toLocaleString("en-IN", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
