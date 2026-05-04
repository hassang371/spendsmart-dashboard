# BUG-021: Worker fetches only 1000 transactions (PostgREST default LIMIT)

> **Doc ID:** BUG-021-worker-fetches-only-1000-transactions
> **Date:** 2026-05-04
> **Status:** Fix Applied
> **Severity:** Critical (training silently runs on truncated history)

## Symptom
Worker logs `Loaded 1000 transactions. Preparing features...` regardless of how many transactions a user actually has (Hassan has ~3 years of data → tens of thousands of rows). TFT training proceeds on the OLDEST 1000 transactions only, producing a panel that ends well before the current date. The trained model then forecasts from a stale window and is essentially useless for current-date predictions.

## Root cause
`fetch_user_transactions` in `packages/forecasting/trainer.py`:

```python
response = (
    supabase.table("transactions")
    .select("transaction_date, amount, description, merchant_name, category")
    .eq("user_id", user_id)
    .order("transaction_date", desc=False)
    .execute()
)
```

No `.range(0, n)` set. PostgREST defaults to `Range: 0-999` → returns 1000 rows max. Order ASC means oldest 1000.

## Fix
Paginate with `.range(start, start + page_size - 1)` until empty page returned. Concat into single DataFrame. Page size 10_000 (PostgREST default max) so most users land in 1-3 round-trips.

## Regression prevention
- Add an integration test seeding 5000+ transactions and asserting `fetch_user_transactions` returns the full set.
- Add `len(df)` assertion in worker's training pipeline: warn if `< 90 days × 5 txns/day = 450` rows for an established user (smoke check that pagination is working).

## Refs
- `packages/forecasting/trainer.py::fetch_user_transactions`
