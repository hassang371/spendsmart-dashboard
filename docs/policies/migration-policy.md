# Migration Safety Policy

> **Doc ID:** migration-policy
> **Date:** 2026-03-08
> **Status:** Current
> **DRI:** Hassan
> **Source:** Feature 002 Rec DB-1

All migrations under `supabase/migrations/` must satisfy this checklist before merging.

---

## Pre-Migration Checklist

### Risk Assessment

- [ ] Lock-risk assessed: could this block writes/reads on large tables?
  - If yes → use `CONCURRENTLY` for indexes, `NOT VALID` for constraints, schedule in low-traffic window
- [ ] Table size estimated (check `pg_relation_size` in staging before prod)
- [ ] Estimated migration wall-clock time documented

### Safety Guards

- [ ] No `DROP TABLE ... CASCADE` — always check and list dependents explicitly
- [ ] No unconditional `DELETE`/`TRUNCATE` without a `WHERE` guard
- [ ] `IF EXISTS` / `IF NOT EXISTS` guards on all DDL where applicable
- [ ] Non-transactional marker added if using `CONCURRENTLY` (cannot run in a transaction block)

### Rollback

- [ ] Rollback script written and tested in staging
- [ ] Rollback script included as a comment block at the bottom of the migration file

### Review

- [ ] Migration reviewed by at least one other engineer
- [ ] PR labelled `migration` for extra review attention
- [ ] Backup confirmation noted (Supabase point-in-time recovery enabled)

---

## Migration File Template

```sql
-- Migration: [short description]
-- Date: YYYY-MM-DD
-- Author: [name]
-- Risk: Low | Medium | High
-- Estimated time: <1s | <10s | minutes
-- Lock risk: None | Metadata | Write | Full
-- Requires non-transactional: Yes | No

-- ============================================================
-- FORWARD MIGRATION
-- ============================================================

-- [migration SQL here]

-- ============================================================
-- ROLLBACK SCRIPT (run manually if needed)
-- ============================================================
-- [rollback SQL here]
```

---

## Index Migrations

Always use `CREATE INDEX CONCURRENTLY` to avoid write locks on production tables.

```sql
-- CORRECT ✅
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_name ON table (col);

-- WRONG ❌ — locks writes
CREATE INDEX IF NOT EXISTS idx_name ON table (col);
```

Note: `CONCURRENTLY` cannot run inside a transaction block. Execute as a standalone statement.

---

## Destructive Change Protocol

For any `DROP TABLE`, `DROP COLUMN`, or data-destructive `UPDATE`/`DELETE`:

1. Open a migration review ticket with blast-radius analysis
2. Add label `destructive-migration` to PR
3. Require explicit sign-off from tech lead
4. Confirm staging test + rollback drill completed
5. Schedule during maintenance window with < 5 min expected downtime

---

## Changelog

| Date | Change |
|---|---|
| 2026-03-08 | Initial policy — pre-migration checklist, rollback template, destructive change protocol (from Feature 002 Rec DB-1) |
