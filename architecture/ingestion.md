# SOP: Data Ingestion (ingestion.md)

## Goal
Ingest financial transaction data from CSV/Excel files into Supabase `transactions` table.

## Inputs
- **Source:** Local file path (CSV or Excel).
- **Format:**
  - Must have headers.
  - Required columns: `Date`, `Description`, `Amount`, `Type` (Credit/Debit). 
  - Optional: `Category`, `Currency` (default: INR).

## Transformation Logic
1. **Load File:** Use `pandas` to read `.csv` or `.xlsx`.
2. **Normalize Headers:** Convert to lowercase, strip whitespace, and map known variations (e.g. "txn date" -> "date").
3. **Parse Dates:** Convert to ISO 8601 format. Handle "DD/MM/YYYY" or "YYYY-MM-DD".
4. **Clean Amount:** Remove symbols (₹, $), commas. Handle "(100)" as negative if needed, though "Type" column usually specifies sign.
   - **Rule:** If `Type` is 'Debit', amount should be negative? Or store absolute + type? 
   - **Decision:** Store signed amount in DB. Debit = negative, Credit = positive.
5. **Deduplicate:** Generate a hash of `(date, amount, description)` to check against existing records (if possible) or just rely on DB constraints.
6. **Enrich:**
   - `merchant_name`: Extract from description (simple regex or LLM).
   - `category`: Default to 'Uncategorized' if missing.

## Outputs
- **Destination:** Supabase `transactions` table.
- **Batching:** Insert in server-side batches.

## Edge Cases
- **Missing Date/Amount:** Skip row and log error.
- **Duplicate Rows in File:** Filter before insert.
- **DB Constraint Violation:** Log error and continue with next batch.

## Tools
- `tools/import_transactions.py`
