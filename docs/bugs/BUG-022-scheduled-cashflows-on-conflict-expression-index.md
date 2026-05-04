# BUG-022: scheduled_cashflows upsert fails — ON CONFLICT can't target expression index

> **Doc ID:** BUG-022-scheduled-cashflows-on-conflict-expression-index
> **Date:** 2026-05-04
> **Status:** Fix Applied
> **Severity:** Medium (non-fatal — training continues without scheduled events; forecast quality reduced)

## Symptom
Worker logs:

```
HTTP/2 400 Bad Request — there is no unique or exclusion constraint matching the ON CONFLICT specification (42P10)
```

on every `upsert_scheduled_cashflows` call. Recurring rules detected by `detect_recurring_cashflows` are never persisted → forecast misses rent / salary / EMI as known-future covariates → quality degraded.

## Root cause
RFC-005 Codex Fix #3 expanded the unique constraint to include `COALESCE(merchant,'')`, `COALESCE(day_of_month,-1)`, `COALESCE(day_of_week,-1)` to fold NULL values into a single representative. This produced an **expression-based unique index** rather than a plain UNIQUE constraint. PostgreSQL allows `ON CONFLICT (col1, col2, ...)` to infer the conflict target from a unique constraint OR a non-expression unique index, but **not from expression indexes**. The worker's supabase-py upsert with `on_conflict=user_id,merchant,amount,...` therefore can't bind to `uniq_scheduled_cashflows_rule`.

## Fix (chosen)
Change worker upsert to plain INSERT + per-row try/except. Skip rows that conflict via `duplicate key` 23505 — log + continue. Slower than upsert but guaranteed to work with the expression index.

## Alternative considered
Migrate the unique index to non-expression form by adding `NOT NULL DEFAULT` on `merchant`, `day_of_month`, `day_of_week`. Rejected: changes RFC-005 contract + requires backfill on prod data.

## Regression prevention
Add an integration test that upserts a recurrence rule twice and asserts only one row exists.

## Refs
- `apps/worker/main.py::upsert_scheduled_cashflows`
- `supabase/migrations/20260418200000_scheduled_cashflows.sql`
