'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { ForecastApiError, createIntent } from '@/lib/api/forecast';
import type {
  CategoryBucket,
  IntentConfidence,
  IntentCreateRequest,
  IntentType,
  RRuleFreq,
  UserIntent,
} from '@/lib/api/forecast.types';

interface AddPlanModalProps {
  /** Called after a successful POST so the page can re-fetch forecast + intents. */
  onCreated?: (intent: UserIntent) => void;
}

const INTENT_TYPE_OPTIONS: ReadonlyArray<{ value: IntentType; label: string }> = [
  { value: 'planned_large_expense', label: 'Planned large expense' },
  { value: 'income_change', label: 'Income change' },
  { value: 'life_event', label: 'Life event' },
  { value: 'obligation_change', label: 'Obligation change' },
  { value: 'savings_goal', label: 'Savings goal' },
  { value: 'fd_maturity', label: 'FD maturity' },
  { value: 'expected_bonus', label: 'Expected bonus' },
];

const CATEGORY_BUCKETS: readonly CategoryBucket[] = [
  'salary',
  'rent',
  'groceries',
  'dining',
  'transport',
  'utilities',
  'entertainment',
  'health',
  'emi_loan',
  'investment',
  'transfer',
  'other',
];

const RRULE_FREQS: readonly RRuleFreq[] = ['monthly', 'weekly', 'biweekly', 'quarterly', 'annual'];

const NOTES_LIMIT = 280;

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

interface FieldErrors {
  [field: string]: string | undefined;
  _global?: string;
}

function parsePydanticErrors(detail: unknown): FieldErrors {
  if (!detail || typeof detail !== 'object') return {};
  const errors: FieldErrors = {};
  // FastAPI shape: { detail: [{loc: [...], msg: '...'}] } OR { detail: '...' }
  const raw = (detail as { detail?: unknown }).detail;
  if (typeof raw === 'string') return { _global: raw };
  if (Array.isArray(raw)) {
    for (const item of raw) {
      if (item && typeof item === 'object' && 'loc' in item && 'msg' in item) {
        const loc = (item as { loc: unknown[] }).loc;
        const field = loc.length > 1 ? String(loc[loc.length - 1]) : '_global';
        errors[field] = String((item as { msg: string }).msg);
      }
    }
  }
  return errors;
}

/** Per LLD 011 §AddPlanModal — framer-motion modal (NOT shadcn). */
export default function AddPlanModal({ onCreated }: AddPlanModalProps) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const headingId = useId();

  // Portal mount guard: createPortal must run client-side after hydration.
  useEffect(() => {
    setMounted(true);
  }, []);

  // Form state
  const [intentType, setIntentType] = useState<IntentType>('planned_large_expense');
  const [startDate, setStartDate] = useState(todayIso());
  const [endDate, setEndDate] = useState('');
  const [amount, setAmount] = useState('');
  const [categoryBucket, setCategoryBucket] = useState<string>('');
  const [confidence, setConfidence] = useState<IntentConfidence>('medium');
  const [isRecurring, setIsRecurring] = useState(false);
  const [rruleFreq, setRruleFreq] = useState<RRuleFreq>('monthly');
  const [notes, setNotes] = useState('');

  const requiresEndDate = intentType === 'savings_goal' || isRecurring;
  const allowsAmount = intentType !== 'life_event';

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        setOpen(false);
      }
    };
    document.addEventListener('keydown', onKey);
    // Focus the dialog on open.
    dialogRef.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      // Restore focus to the trigger after close.
      triggerRef.current?.focus();
    }
  }, [open]);

  const reset = () => {
    setIntentType('planned_large_expense');
    setStartDate(todayIso());
    setEndDate('');
    setAmount('');
    setCategoryBucket('');
    setConfidence('medium');
    setIsRecurring(false);
    setRruleFreq('monthly');
    setNotes('');
    setErrors({});
  };

  const handleClose = () => {
    setOpen(false);
    setErrors({});
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setErrors({});
    const body: IntentCreateRequest = {
      intent_type: intentType,
      start_date: startDate,
      confidence,
      is_recurring: isRecurring,
    };
    if (allowsAmount && amount) {
      const parsed = Number(amount);
      if (Number.isNaN(parsed)) {
        setErrors({ amount: 'Amount must be a number.' });
        return;
      }
      body.amount = parsed;
    }
    if (categoryBucket) body.category_bucket = categoryBucket;
    if (requiresEndDate && endDate) body.end_date = endDate;
    if (isRecurring) body.rrule_freq = rruleFreq;
    if (notes.trim()) body.notes = notes.trim().slice(0, NOTES_LIMIT);

    setSubmitting(true);
    try {
      const created = await createIntent(body);
      reset();
      setOpen(false);
      onCreated?.(created);
    } catch (err) {
      if (err instanceof ForecastApiError) {
        const parsed = parsePydanticErrors(err.data);
        if (Object.keys(parsed).length === 0) {
          setErrors({ _global: err.message });
        } else {
          setErrors(parsed);
        }
      } else if (err instanceof Error) {
        setErrors({ _global: err.message });
      } else {
        setErrors({ _global: 'Could not save plan.' });
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Modal content rendered into a portal so ancestor CSS transforms do NOT
  // re-anchor the position:fixed overlay relative to a transformed parent
  // (which is what was making the dialog stick to the lower-right of the
  // dashboard's transformed grid). Portal target is document.body.
  const modalContent = (
    <AnimatePresence>
      {open && (
        <motion.div
          key="backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-40 bg-black/50"
          onClick={handleClose}
          data-testid="add-plan-backdrop"
        />
      )}
      {open && (
        <div
          key="panel-wrapper"
          className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2"
        >
          <motion.div
            ref={dialogRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby={headingId}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="max-h-[90vh] w-[min(36rem,calc(100vw-2rem))] overflow-y-auto rounded-xl border border-border bg-card p-6 text-card-foreground shadow-xl focus:outline-none"
            data-testid="add-plan-modal"
          >
            <div className="mb-4 flex items-start justify-between">
              <h2 id={headingId} className="text-lg font-semibold">
                Add plan
              </h2>
              <button
                type="button"
                onClick={handleClose}
                aria-label="Close"
                className="rounded-md p-1 text-muted-foreground hover:bg-accent"
              >
                ✕
              </button>
            </div>

            {errors._global && (
              <p
                role="alert"
                data-testid="add-plan-global-error"
                className="mb-3 rounded-md border border-red-300 bg-red-50 p-2 text-sm text-red-800 dark:border-red-700 dark:bg-red-950 dark:text-red-100"
              >
                {errors._global}
              </p>
            )}

            <form onSubmit={handleSubmit} className="space-y-3 text-sm">
              <label className="block">
                <span className="font-medium">Plan type</span>
                <select
                  value={intentType}
                  onChange={e => setIntentType(e.target.value as IntentType)}
                  className="mt-1 w-full rounded-md border border-border bg-background p-2"
                  data-testid="add-plan-intent-type"
                >
                  {INTENT_TYPE_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                {errors.intent_type && (
                  <p className="mt-1 text-xs text-red-700">{errors.intent_type}</p>
                )}
              </label>

              <label className="block">
                <span className="font-medium">Start date</span>
                <input
                  type="date"
                  value={startDate}
                  onChange={e => setStartDate(e.target.value)}
                  required
                  className="mt-1 w-full rounded-md border border-border bg-background p-2"
                  data-testid="add-plan-start-date"
                />
                {errors.start_date && (
                  <p className="mt-1 text-xs text-red-700">{errors.start_date}</p>
                )}
              </label>

              {requiresEndDate && (
                <label className="block">
                  <span className="font-medium">End date</span>
                  <input
                    type="date"
                    value={endDate}
                    onChange={e => setEndDate(e.target.value)}
                    className="mt-1 w-full rounded-md border border-border bg-background p-2"
                    data-testid="add-plan-end-date"
                  />
                  {errors.end_date && (
                    <p className="mt-1 text-xs text-red-700">{errors.end_date}</p>
                  )}
                </label>
              )}

              {allowsAmount && (
                <label className="block">
                  <span className="font-medium">Amount (₹)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={amount}
                    onChange={e => setAmount(e.target.value)}
                    className="mt-1 w-full rounded-md border border-border bg-background p-2"
                    data-testid="add-plan-amount"
                  />
                  {errors.amount && <p className="mt-1 text-xs text-red-700">{errors.amount}</p>}
                </label>
              )}

              <label className="block">
                <span className="font-medium">Category (optional)</span>
                <select
                  value={categoryBucket}
                  onChange={e => setCategoryBucket(e.target.value)}
                  className="mt-1 w-full rounded-md border border-border bg-background p-2"
                  data-testid="add-plan-category"
                >
                  <option value="">None</option>
                  {CATEGORY_BUCKETS.map(b => (
                    <option key={b} value={b}>
                      {b.replace(/_/g, ' ')}
                    </option>
                  ))}
                </select>
                {errors.category_bucket && (
                  <p className="mt-1 text-xs text-red-700">{errors.category_bucket}</p>
                )}
              </label>

              <fieldset>
                <legend className="font-medium">Confidence</legend>
                <div className="mt-1 flex gap-2" role="radiogroup">
                  {(['low', 'medium', 'high'] as IntentConfidence[]).map(level => (
                    <label
                      key={level}
                      className={`flex-1 cursor-pointer rounded-md border p-2 text-center text-xs capitalize ${
                        confidence === level
                          ? 'border-primary bg-primary/10 font-semibold'
                          : 'border-border'
                      }`}
                    >
                      <input
                        type="radio"
                        name="confidence"
                        value={level}
                        checked={confidence === level}
                        onChange={() => setConfidence(level)}
                        className="sr-only"
                        data-testid={`add-plan-confidence-${level}`}
                      />
                      {level}
                    </label>
                  ))}
                </div>
              </fieldset>

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={isRecurring}
                  onChange={e => setIsRecurring(e.target.checked)}
                  data-testid="add-plan-recurring"
                />
                <span className="font-medium">Recurring</span>
              </label>

              {isRecurring && (
                <label className="block">
                  <span className="font-medium">Frequency</span>
                  <select
                    value={rruleFreq}
                    onChange={e => setRruleFreq(e.target.value as RRuleFreq)}
                    className="mt-1 w-full rounded-md border border-border bg-background p-2"
                    data-testid="add-plan-rrule-freq"
                  >
                    {RRULE_FREQS.map(f => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                  {errors.rrule_freq && (
                    <p className="mt-1 text-xs text-red-700">{errors.rrule_freq}</p>
                  )}
                </label>
              )}

              <label className="block">
                <span className="font-medium">Notes</span>
                <textarea
                  value={notes}
                  onChange={e => setNotes(e.target.value.slice(0, NOTES_LIMIT))}
                  maxLength={NOTES_LIMIT}
                  className="mt-1 w-full rounded-md border border-border bg-background p-2"
                  rows={3}
                  data-testid="add-plan-notes"
                />
                <p className="mt-1 text-right text-xs text-muted-foreground">
                  {notes.length}/{NOTES_LIMIT}
                </p>
              </label>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={handleClose}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm hover:bg-accent"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  data-testid="add-plan-submit"
                  className="rounded-md border border-border bg-primary px-3 py-2 text-sm text-primary-foreground hover:opacity-90 disabled:opacity-50"
                >
                  {submitting ? 'Saving…' : 'Save plan'}
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(true)}
        data-testid="add-plan-trigger"
        className="rounded-md border border-border bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        Add plan
      </button>
      {mounted ? createPortal(modalContent, document.body) : null}
    </>
  );
}
