'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

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
import { accountsApi, categorizationApi, ingestionApi } from '../../../lib/api/client';

type TransactionRow = {
  id: string;
  user_id: string;
  transaction_date: string;
  amount: number;
  description: string;
  category: string;
  original_category?: string | null;
  suggested_category?: string | null;
  confidence_score?: number | null;
  payment_method: string;
  merchant_name: string;
  status: string;
  type: string;
  created_at: string;
  raw_data?: Record<string, any>;
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

const TRANSACTIONS_CACHE_TTL_MS = 60 * 1000;
const INITIAL_VISIBLE_COUNT = 50;
const LOAD_MORE_STEP = 50;

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
  const categoryPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    const {
      data: { user },
      error: userError,
    } = await supabase.auth.getUser();

    if (userError || !user) {
      router.replace('/login');
      return;
    }

    setUserId(user.id);

    // Get auth token
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) {
      router.replace('/login');
      return;
    }

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

    // Fetch all transactions via FastAPI backend with pagination
    const allItems: TransactionRow[] = [];
    let cursor: string | undefined;
    let hasMore = true;

    while (hasMore) {
      const response = await accountsApi.getTransactions(session.access_token, {
        limit: 100,
        cursor,
      });
      // Map API response items to TransactionRow
      for (const item of response.items) {
        allItems.push({
          id: item.id,
          user_id: item.user_id,
          transaction_date: item.transaction_date || new Date().toISOString(),
          amount: item.amount,
          description: item.description || 'Imported transaction',
          merchant_name: item.merchant_name || 'Unknown Merchant',
          category: item.category || 'Uncategorized',
          original_category: item.original_category,
          payment_method: item.payment_method || 'Cash',
          status: item.status || 'completed',
          type: item.type || (item.amount >= 0 ? 'credit' : 'debit'),
          created_at: item.created_at || new Date().toISOString(),
          raw_data: item.raw_data as Record<string, any>,
        });
      }
      hasMore = response.has_more;
      cursor = response.next_cursor ?? undefined;
    }

    setTransactions(allItems);
    sessionStorage.setItem(
      cacheKey,
      JSON.stringify({
        timestamp: Date.now(),
        rows: allItems,
      })
    );
  }, [router]);

  // Poll for category updates after import — background classification takes a few seconds.
  // Stops after 15 polls (30s) or on unmount.
  const startCategoryPolling = useCallback(() => {
    if (categoryPollRef.current) clearInterval(categoryPollRef.current);
    let polls = 0;
    categoryPollRef.current = setInterval(async () => {
      polls++;
      await fetchTransactions();
      if (polls >= 15) {
        clearInterval(categoryPollRef.current!);
        categoryPollRef.current = null;
      }
    }, 2000);
  }, [fetchTransactions]);

  // Cleanup poll on unmount
  useEffect(() => () => {
    if (categoryPollRef.current) clearInterval(categoryPollRef.current);
  }, []);

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

  const saveCategoryEdit = async () => {
    if (!editingCategoryTxId || !userId) return;
    setUpdatingCategory(true);
    try {
      const tx = transactions.find(t => t.id === editingCategoryTxId);
      if (!tx) throw new Error('Transaction not found');

      // Get auth token
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const accessToken = session?.access_token as string;

      const isIncome = editingCategoryValue.toLowerCase() === 'income';
      const currentAmount = tx.amount;

      // Auto-flip logic
      let newAmount = currentAmount;
      if (isIncome && currentAmount < 0) {
        newAmount = Math.abs(currentAmount);
      } else if (!isIncome && currentAmount > 0 && tx.category?.toLowerCase() === 'income') {
        newAmount = -Math.abs(currentAmount);
      }

      const updates: { category: string; amount?: number; original_category?: string; old_category?: string } = {
        category: editingCategoryValue,
        old_category: tx.category,  // For merchant-batch reclassification (handled server-side)
      };

      if (!tx.original_category) {
        updates.original_category = tx.category;
      }

      if (newAmount !== currentAmount) {
        updates.amount = newAmount;
      }

      // Update via API — server auto-updates all matching merchant transactions
      await accountsApi.updateTransaction(editingCategoryTxId, updates, accessToken);

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

      // Active Learning: Submit feedback to backend (handles training_corrections too)
      if (tx && tx.category !== editingCategoryValue) {
        categorizationApi
          .submitFeedback({ [tx.description]: editingCategoryValue }, accessToken)
          .catch(err => console.warn('Feedback failed:', err));
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

  /* Consolidated handleDataImport — now delegates entirely to the backend */
  const handleDataImport = async (file: File, password?: string): Promise<number> => {
    if (!userId) throw new Error('No authenticated user found.');

    // Auth Check
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) throw new Error('Session expired.');
    const accessToken = session.access_token;

    setImportProgress(10);

    // Send file to backend — it handles ALL parsing, classification, dedup, and insertion
    const result = await ingestionApi.importFile(file, accessToken, password);

    setImportProgress(100);
    return result.inserted;
  };

  const onSelectFile: React.ChangeEventHandler<HTMLInputElement> = async event => {
    console.log('onSelectFile triggered', event.target.files);
    if (saving) {
      event.target.value = '';
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
      setTab('all');
      listRef.current?.scrollTo({ top: 0, behavior: 'auto' });
      setMessage(`Imported ${count} transactions from ${file.name}.`);
      setSaving(false);
      setImportProgress(null);
      event.target.value = '';
      if (count > 0) startCategoryPolling();
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
      if (count > 0) startCategoryPolling();
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
