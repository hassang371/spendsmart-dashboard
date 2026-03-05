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
4. **Clean Amount:** Remove symbols (₹, $), commas. Handle "(100)" as negative if needed.
   - **Rule:** Store signed amount in DB. Debit = negative, Credit = positive.
5. **Deduplicate:** Generate a 6-field fingerprint hash of `(date, amount, description, merchant, payment_method, reference)` and check against existing records.
6. **Text Processing (v2):**
   - `informative_text`: Bank Statement Lexicon translates abbreviations (WDL, TFR, UPI, POS, ATM) into intent-rich text (e.g., "UPI Transfer to Allan G via YESB").
   - `merchant_name`: Extract from description using v2 cleaner pipeline, with fallback to legacy merchant extractor.
7. **Classify:**
   - First pass: KeywordMatcher (deterministic rules for known merchants + P2P transfers).
   - Second pass: MiniLM + Cosine Similarity (zero-shot classification against 25+ category seed phrases).
   - Confidence threshold: 0.75. Below threshold → `suggested_category` for user review.

## Outputs

- **Destination:** Supabase `transactions` table (includes `informative_text` column).
- **Batching:** Insert in server-side batches.

## Edge Cases

- **Missing Date/Amount:** Skip row and log error.
- **Duplicate Rows in File:** Filter before insert.
- **DB Constraint Violation:** Log error and continue with next batch.

## Model Architecture (v2)

- **Embedding:** Frozen `all-MiniLM-L6-v2` (22MB, 384-dim)
- **Classification:** Cosine similarity against pre-computed category embeddings
- **Adaptation:** Per-user Linear Adapter trained on reclassifications (~10KB per user)
- **Storage:** User adapter weights stored in Supabase Storage bucket "models"
