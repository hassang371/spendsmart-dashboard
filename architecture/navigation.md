# Navigation Layer (navigation.md)

## Purpose
Routes user actions/events to specific Tools and SOPs.

## Routes

### 1. Data Ingestion (Manual/Batch)
- **Trigger:** User uploads FILE (CSV/Excel) via CLI or UI.
- **Action:** UI sends batched payloads to `POST /api/import` (CLI helper can still use `tools/import_transactions.py`).
- **Arguments:** `file_path`, `user_id`.
- **Logic:**
    - Parse file (see `ingestion.md`).
    - Validate Schema.
    - Insert into Supabase `transactions`.
    - Report success/failure count.

### 2. Analysis (Future)
- **Trigger:** User requests "Analyze spending".
- **Action:** Execute `tools/analyze_transactions.py` (TBD).
- **Arguments:** `user_id`, `date_range`.

### 3. User Setup
- **Trigger:** New user registration.
- **Action:** Supabase Auth Trigger (or manual setup via `tools/setup_user.py` if needed).
- **Logic:** Create user profile entry.

## Error Handling
- **Tool Failure:** Log to `progress.md` (or system log).
- **Self-Healing:** Identify error pattern -> Update `ingestion.md` -> Fix Tool.
