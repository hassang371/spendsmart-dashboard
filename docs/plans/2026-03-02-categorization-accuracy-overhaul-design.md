# Categorization Accuracy Overhaul — Design

**Date:** 2026-03-02
**Status:** Approved
**Market:** India only

---

## Goal

Improve transaction categorization accuracy by:
1. Expanding the keyword rule set to cover the Indian market properly
2. Fixing `merchant_name` extraction (currently broken/garbled for many transactions)
3. Inferring `payment_method` from description patterns (currently always empty)
4. Adding a confidence threshold to HypCD — low-confidence predictions are stored as suggestions rather than silently assigned
5. Giving users a Review tab to approve or correct uncategorized transactions
6. Feeding corrections back into per-user model fine-tuning (active learning loop)

---

## Current State (from live Supabase inspection)

- 149 transactions: **137 wrongly categorized as "Health"** (things like "Cloud Storage Monthly", "Music Premium", "Play Pass Monthly")
- `payment_method` is **empty for all 149 rows**
- `merchant_name` partially populated but broken ("Movie Rental HD" → "Vodafone", "Samay Raina membership" → "Samay Raina Me Ership")
- Descriptions are **already clean** (Google Play-style: "YouTube Premium Individual") — no UPI prefix stripping needed for current data, but parser will handle UPI for future real bank imports
- `rules.py` has ~50 keywords; `_initialize_anchors` has only 3 seed phrases per category

---

## Architecture

### Classification Pipeline (updated)

```
Incoming transaction description
            │
            ▼
    clean_description()           ← existing cleaner.py
            │
            ▼
    KeywordMatcher.predict()      ← rules.py (fast path)
            │
     match? ─── yes ──► category assigned, confidence=1.0, done
            │
            no
            ▼
    HypCD.predict_batch()
            │
   confidence ≥ THRESHOLD? ── yes ──► category assigned normally
            │
            no
            ▼
   category = "Uncategorized"
   suggested_category = HypCD top-1 prediction
   confidence_score   = HypCD score (stored for threshold tuning)
```

`CONFIDENCE_THRESHOLD` is a named constant (default `0.90`). Tuned after running real data.

---

## Changes by Layer

### 1. Schema — `transactions` table (2 new columns)

```sql
ALTER TABLE transactions
  ADD COLUMN suggested_category TEXT,
  ADD COLUMN confidence_score    FLOAT;
```

- `suggested_category`: HypCD's best guess when confidence < threshold. NULL when category is assigned normally.
- `confidence_score`: Raw HypCD score, stored for future threshold analysis.

### 2. `rules.py` — expand from ~50 → ~200 keywords

New coverage (Indian market):
- **Food**: Dunzo, BigBasket, JioMart, EatFit, Licious, Ola Foods, Box8, FreshMenu, Milkbasket, Country Delight, Barbeque Nation, Haldiram, Amul
- **Transport**: InDrive, BluSmart, Namma Metro, BEST, KSRTC, BMTC, IndiGo, SpiceJet, Air India, Ixigo, MakeMyTrip, redBus, Yatra, HP Petrol, IndianOil
- **Entertainment**: JioCinema, SonyLIV, ZEE5, Mubi, Apple TV, Lionsgate, BookMyShow, Disney+, Gaana, JioSaavn, WynkMusic, Play Pass, Google Play
- **Shopping**: Nykaa, Meesho, Snapdeal, Tata CLiQ, Croma, Reliance Digital, Vijay Sales, DMart, Spencer's, Big Bazaar, Lifestyle, Westside
- **Finance**: CRED, PhonePe, Paytm, GPay, Bajaj Finance, HDFC, ICICI, SBI, Axis, Kotak, Angel One, Upstox, INDmoney, Fi Money
- **Health**: 1mg, Netmeds, Pharmeasy, Healthifyme, Cult.fit, Lybrate, Tata 1mg, Apollo247, Portea
- **Utilities**: Tata Power, MSEDCL, TNEB, BSES, Hathway, YOU Broadband, Tikona, BSNL
- **Education**: BYJU'S, Unacademy, Vedantu, upGrad, Simplilearn, Physics Wallah, Khan Academy

### 3. `constants.py` — expand `DEFAULT_CATEGORY_KEYWORDS`

Anchor seed phrases per category: **3 → 8–10**, using realistic Indian transaction descriptions:

```python
"Food": [
    "swiggy order", "zomato payment", "restaurant bill",
    "blinkit grocery", "zepto delivery", "bigbasket order",
    "dunzo delivery", "food delivery payment", "cafe coffee day",
    "dominos pizza order"
]
```

### 4. `hypcd.py` — expand `_initialize_anchors` + add threshold constant

Same expanded phrases as constants.py so geometric prototypes are well-positioned in Poincaré space.

Add at module level:
```python
CONFIDENCE_THRESHOLD = 0.90  # Tune after real-data evaluation
```

`predict_batch()` returns confidence score alongside category; caller checks threshold.

### 5. Ingestion — fix `merchant_name` + add `payment_method` inference

**`merchant_name` extraction** — new `extract_merchant_name(description: str) -> str` function in `packages/ingestion_engine/`:

Priority order:
1. UPI format: `UPI[-/]<MERCHANT>[-/]<VPA>` → extract MERCHANT segment, title-case
2. NEFT/RTGS/IMPS: extract payee name after bank code
3. ACH/NACH: extract company name
4. Clean description (current data): use full description, strip trailing numbers/codes
5. Fallback: first 3 meaningful words, title-cased

**`payment_method` inference** — new `infer_payment_method(description: str) -> str`:

| Pattern | Result |
|---|---|
| Starts with `UPI` | `"UPI"` |
| Contains `NEFT` / `RTGS` | `"Bank Transfer"` |
| Contains `IMPS` | `"IMPS"` |
| Contains `ACH` / `NACH` / `ECS` | `"Auto Debit"` |
| Contains `ATM` / `cash` | `"Cash"` |
| Contains `POS` / `card` / `swipe` | `"Card"` |
| Google Play / App Store / subscription keywords | `"Subscription"` |
| Default | `"Other"` |

Both functions run at import time in the ingestion router, populating `merchant_name` and `payment_method` before DB insert.

### 6. API — new endpoint

```
GET /accounts/transactions/uncategorized
```

Returns all transactions where `category = 'Uncategorized'`, including `suggested_category` and `confidence_score`. Paginated, same cursor pattern as existing list endpoint.

Accept/reclassify actions use existing `PATCH /accounts/transactions/{id}` with `old_category` — merchant-batch update now matches on `merchant_name` (not raw description keyword) to avoid over-matching.

### 7. Frontend — Review tab on transactions page

- New **"Review"** tab alongside existing transaction list tabs
- Badge showing count of uncategorized transactions
- Each row: description · amount · date · **"Suggested: [chip]"**
- Two actions:
  - **✓ Accept** — calls `PATCH` with `category = suggested_category`; bulk-updates same merchant
  - **✗ Reclassify** — opens category picker; user picks; bulk-updates same merchant
- Both write to `training_corrections` and trigger supervised fine-tuning background task

---

## Active Learning Loop

```
User corrects transaction
        │
        ▼
training_corrections INSERT
  (description, original=suggested_category, corrected=user_pick)
        │
        ▼
user_model_metadata.correction_count += 1
        │
        ▼
_run_supervised_finetuning_bg()   ← existing background task
  loads user adapter → fine-tunes on correction → saves adapter
        │
        ▼
Next time same merchant appears:
  adapter shifts embedding closer to corrected category ✓
```

---

## What Is NOT Changing

- HypCD architecture (Poincaré Ball, GCD routing, hierarchy norm) — untouched
- Existing merchant-batch reclassification mechanism — reused, not duplicated
- `training_corrections` and `user_model_metadata` tables — already in DB
- Confidence threshold value — left as `0.90`, tuned empirically later

---

## Verification

- All existing 142 backend tests still pass
- New tests: `extract_merchant_name`, `infer_payment_method`, uncategorized endpoint, Review tab accept/reclassify flow
- Manual check: re-run 149 live transactions through updated classifier — expect Health count to drop significantly, Entertainment/Shopping/Finance to rise
