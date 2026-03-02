# Categorization Accuracy Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve transaction categorization accuracy by expanding rules, fixing merchant name extraction, adding payment method inference, applying a confidence threshold so low-confidence predictions become reviewable rather than silently wrong, and building a Review tab for user corrections that feed active learning.

**Architecture:** Seven layers of change — schema, rules/constants, ML anchors, ingestion pipeline, API, and frontend. Each layer is independently testable. The confidence threshold mechanism reuses the existing `suggested_category`/`confidence_score` columns (added in Task 1) and the existing supervised fine-tuning background task. The Review tab is a new tab inside the existing transactions page.

**Tech Stack:** FastAPI (Python 3.14), PyTorch + geoopt (HypCD), Next.js 16 (TypeScript), Supabase, `.venv/bin/python` for all Python commands.

---

## BATCH 1 — Schema

---

### Task 1: Add suggested_category and confidence_score to transactions

**Files:**
- Modify: `architecture/schema.sql`

**Step 1: Apply migration via Supabase MCP**

Use the `mcp__supabase__apply_migration` tool with name `add_suggested_category_confidence_score` and query:

```sql
ALTER TABLE public.transactions
  ADD COLUMN IF NOT EXISTS suggested_category TEXT,
  ADD COLUMN IF NOT EXISTS confidence_score    FLOAT;

COMMENT ON COLUMN public.transactions.suggested_category IS
  'HypCD top-1 prediction when confidence < CONFIDENCE_THRESHOLD. NULL when category assigned normally.';
COMMENT ON COLUMN public.transactions.confidence_score IS
  'Raw HypCD confidence score (0.0–1.0). Stored for threshold analysis.';
```

**Step 2: Update schema.sql to match**

In `architecture/schema.sql`, add these two columns to the transactions table definition after `original_category TEXT,`:

```sql
    suggested_category TEXT,
    confidence_score   FLOAT,
```

**Step 3: Verify**

Use `mcp__supabase__execute_sql` to confirm:
```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'transactions'
  AND column_name IN ('suggested_category', 'confidence_score');
```
Expected: 2 rows returned.

**Step 4: Commit**
```bash
PRE_COMMIT_ALLOW_NO_CONFIG=1 git add architecture/schema.sql
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat(schema): add suggested_category and confidence_score to transactions"
```

---

## BATCH 2 — Rules and ML Expansion

---

### Task 2: Expand rules.py keywords (~50 → ~200)

**Files:**
- Modify: `packages/categorization/rules.py`
- Test: `packages/categorization/tests/test_rules.py` (create if not exists)

**Step 1: Write failing tests**

```python
# packages/categorization/tests/test_rules.py
import pytest
from packages.categorization.rules import KeywordMatcher


@pytest.fixture
def matcher():
    return KeywordMatcher()


# Food — new additions
def test_dunzo_is_food(matcher):
    assert matcher.predict("Dunzo Quick Delivery") == "Food"

def test_bigbasket_is_food(matcher):
    assert matcher.predict("BigBasket grocery order") == "Food"

def test_eatfit_is_food(matcher):
    assert matcher.predict("EatFit meal plan") == "Food"

# Transport — new additions
def test_indrive_is_transport(matcher):
    assert matcher.predict("InDrive ride payment") == "Transport"

def test_indigo_is_transport(matcher):
    assert matcher.predict("IndiGo flight booking") == "Transport"

def test_makemytrip_is_transport(matcher):
    assert matcher.predict("MakeMyTrip hotel + flight") == "Transport"

# Entertainment — new additions
def test_jiocinema_is_entertainment(matcher):
    assert matcher.predict("JioCinema subscription") == "Entertainment"

def test_sonyliv_is_entertainment(matcher):
    assert matcher.predict("SonyLIV monthly plan") == "Entertainment"

def test_google_play_pass_is_entertainment(matcher):
    assert matcher.predict("Play Pass Monthly") == "Entertainment"

# Shopping — new additions
def test_nykaa_is_shopping(matcher):
    assert matcher.predict("Nykaa beauty order") == "Shopping"

def test_meesho_is_shopping(matcher):
    assert matcher.predict("Meesho fashion purchase") == "Shopping"

def test_croma_is_shopping(matcher):
    assert matcher.predict("Croma electronics") == "Shopping"

# Finance — new additions
def test_cred_is_finance(matcher):
    assert matcher.predict("CRED credit card payment") == "Finance"

def test_phonepay_is_finance(matcher):
    assert matcher.predict("PhonePe UPI transfer") == "Finance"

# Health — new additions
def test_onemg_is_health(matcher):
    assert matcher.predict("1mg medicine order") == "Health"

def test_cultfit_is_health(matcher):
    assert matcher.predict("Cult.fit gym membership") == "Health"

# Utilities — new additions
def test_tatapower_is_utilities(matcher):
    assert matcher.predict("Tata Power electricity bill") == "Utilities"

# Education — new additions
def test_byjus_is_education(matcher):
    assert matcher.predict("BYJU'S course subscription") == "Education"

def test_unacademy_is_education(matcher):
    assert matcher.predict("Unacademy Plus plan") == "Education"

# No over-match on short keywords
def test_vi_does_not_match_video(matcher):
    # "vi" is Vodafone (Utilities) — word boundary check should prevent "video" matching
    result = matcher.predict("video streaming service")
    assert result != "Utilities"
```

**Step 2: Run to confirm failures**
```bash
.venv/bin/python -m pytest packages/categorization/tests/test_rules.py -v --tb=short 2>&1 | tail -30
```
Expected: Most new-brand tests FAIL.

**Step 3: Expand the rules dict in rules.py**

Replace the entire `self.rules` dict in `KeywordMatcher.__init__` with:

```python
self.rules: Dict[str, str] = {
    # ── Food & Dining ──────────────────────────────────────────────────
    "swiggy":        "Food",
    "zomato":        "Food",
    "blinkit":       "Food",
    "zepto":         "Food",
    "bigbasket":     "Food",
    "dunzo":         "Food",
    "eatfit":        "Food",
    "licious":       "Food",
    "box8":          "Food",
    "freshmenu":     "Food",
    "milkbasket":    "Food",
    "jiomart":       "Food",
    "domin":         "Food",   # Dominos
    "pizza":         "Food",
    "burger":        "Food",
    "kfc":           "Food",
    "mcdonald":      "Food",
    "starbuck":      "Food",
    "cafe":          "Food",
    "restaurant":    "Food",
    "barbeque":      "Food",
    "haldiram":      "Food",
    "amul":          "Food",
    "country delight": "Food",
    "faasos":        "Food",
    "behrouz":       "Food",
    "biryani":       "Food",
    "ola foods":     "Food",

    # ── Transport ──────────────────────────────────────────────────────
    "uber":          "Transport",
    "ola":           "Transport",
    "rapido":        "Transport",
    "indrive":       "Transport",
    "blusmart":      "Transport",
    "metro":         "Transport",
    "irctc":         "Transport",
    "indigo":        "Transport",
    "spicejet":      "Transport",
    "air india":     "Transport",
    "airindia":      "Transport",
    "vistara":       "Transport",
    "goair":         "Transport",
    "akasa":         "Transport",
    "makemytrip":    "Transport",
    "ixigo":         "Transport",
    "redbus":        "Transport",
    "yatra":         "Transport",
    "goibibo":       "Transport",
    "cleartrip":     "Transport",
    "fuel":          "Transport",
    "petrol":        "Transport",
    "diesel":        "Transport",
    "shell":         "Transport",
    "hpcl":          "Transport",
    "iocl":          "Transport",
    "indianoil":     "Transport",
    "bharat petroleum": "Transport",
    "parking":       "Transport",
    "fastag":        "Transport",
    "ksrtc":         "Transport",
    "bmtc":          "Transport",

    # ── Shopping ───────────────────────────────────────────────────────
    "amazon":        "Shopping",
    "flipkart":      "Shopping",
    "myntra":        "Shopping",
    "ajio":          "Shopping",
    "meesho":        "Shopping",
    "nykaa":         "Shopping",
    "tata cliq":     "Shopping",
    "snapdeal":      "Shopping",
    "decathlon":     "Shopping",
    "croma":         "Shopping",
    "reliance digital": "Shopping",
    "vijay sales":   "Shopping",
    "zudio":         "Shopping",
    "westside":      "Shopping",
    "lifestyle":     "Shopping",
    "pantaloons":    "Shopping",
    "max fashion":   "Shopping",
    "dmart":         "Shopping",
    "big bazaar":    "Shopping",
    "retail":        "Shopping",

    # ── Entertainment ──────────────────────────────────────────────────
    "netflix":       "Entertainment",
    "spotify":       "Entertainment",
    "prime":         "Entertainment",
    "hotstar":       "Entertainment",
    "jiocinema":     "Entertainment",
    "sonyliv":       "Entertainment",
    "zee5":          "Entertainment",
    "mubi":          "Entertainment",
    "lionsgate":     "Entertainment",
    "apple tv":      "Entertainment",
    "gaana":         "Entertainment",
    "jiosaavn":      "Entertainment",
    "wynk":          "Entertainment",
    "youtube":       "Entertainment",
    "steam":         "Entertainment",
    "pvr":           "Entertainment",
    "inox":          "Entertainment",
    "bookmyshow":    "Entertainment",
    "play pass":     "Entertainment",
    "google play":   "Entertainment",
    "music premium": "Entertainment",
    "movie rental":  "Entertainment",
    "cloud storage": "Entertainment",  # Google One/iCloud — subscription
    "samay raina":   "Entertainment",

    # ── Utilities ──────────────────────────────────────────────────────
    "bescom":        "Utilities",
    "bwssb":         "Utilities",
    "tata power":    "Utilities",
    "msedcl":        "Utilities",
    "tneb":          "Utilities",
    "bses":          "Utilities",
    "airtel":        "Utilities",
    "jio":           "Utilities",
    "vodafone":      "Utilities",
    "hathway":       "Utilities",
    "act fibernet":  "Utilities",
    "bsnl":          "Utilities",
    "tikona":        "Utilities",
    "you broadband": "Utilities",
    "bill":          "Utilities",
    "recharge":      "Utilities",

    # ── Health ─────────────────────────────────────────────────────────
    "pharmacy":      "Health",
    "apollo":        "Health",
    "medplus":       "Health",
    "practo":        "Health",
    "1mg":           "Health",
    "netmeds":       "Health",
    "pharmeasy":     "Health",
    "healthifyme":   "Health",
    "cult.fit":      "Health",
    "cultfit":       "Health",
    "lybrate":       "Health",
    "portea":        "Health",
    "clinic":        "Health",
    "hospital":      "Health",
    "gym":           "Health",
    "fitness":       "Health",

    # ── Finance ────────────────────────────────────────────────────────
    "zerodha":       "Finance",
    "groww":         "Finance",
    "angel":         "Finance",   # Angel One
    "upstox":        "Finance",
    "indmoney":      "Finance",
    "cred":          "Finance",
    "phonepay":      "Finance",
    "phonep":        "Finance",   # PhonePe truncated
    "paytm":         "Finance",
    "gpay":          "Finance",
    "loan":          "Finance",
    "emi":           "Finance",
    "insurance":     "Finance",
    "bajaj finance": "Finance",
    "hdfc":          "Finance",
    "icici":         "Finance",
    "sbi":           "Finance",
    "axis bank":     "Finance",
    "kotak":         "Finance",
    "tax":           "Finance",
    "sip":           "Finance",
    "mutual fund":   "Finance",

    # ── Education ──────────────────────────────────────────────────────
    "byju":          "Education",
    "unacademy":     "Education",
    "vedantu":       "Education",
    "upgrad":        "Education",
    "simplilearn":   "Education",
    "physics wallah": "Education",
    "udemy":         "Education",
    "coursera":      "Education",
    "course":        "Education",
    "tuition":       "Education",

    # ── Salary / Income ────────────────────────────────────────────────
    "salary":        "Salary",
    "payroll":       "Salary",
    "stipend":       "Salary",
}
```

**Step 4: Run tests**
```bash
.venv/bin/python -m pytest packages/categorization/tests/test_rules.py -v --tb=short 2>&1 | tail -30
```
Expected: All tests pass.

**Step 5: Run full suite to check no regressions**
```bash
.venv/bin/python -m pytest apps/api/ packages/categorization/ -q --tb=short 2>&1 | tail -10
```
Expected: All tests pass.

**Step 6: Commit**
```bash
PRE_COMMIT_ALLOW_NO_CONFIG=1 git add packages/categorization/rules.py packages/categorization/tests/test_rules.py
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat(rules): expand KeywordMatcher from ~50 to ~200 Indian merchant keywords"
```

---

### Task 3: Expand DEFAULT_CATEGORY_KEYWORDS in constants.py

**Files:**
- Modify: `packages/categorization/constants.py`

**Step 1: Write failing test**

```python
# Add to packages/categorization/tests/test_rules.py

from packages.categorization.constants import DEFAULT_CATEGORY_KEYWORDS

def test_each_category_has_at_least_8_seed_phrases():
    """Anchor seed phrases must be rich enough to position prototypes well."""
    for category, phrases in DEFAULT_CATEGORY_KEYWORDS.items():
        assert len(phrases) >= 8, f"{category} only has {len(phrases)} phrases — need ≥ 8"

def test_food_seeds_include_indian_apps():
    food = DEFAULT_CATEGORY_KEYWORDS["Food"]
    assert any("swiggy" in p.lower() for p in food)
    assert any("blinkit" in p.lower() or "zepto" in p.lower() for p in food)

def test_entertainment_includes_subscriptions():
    ent = DEFAULT_CATEGORY_KEYWORDS["Entertainment"]
    assert any("jiocinema" in p.lower() or "sonyliv" in p.lower() for p in ent)
```

**Step 2: Run to confirm failures**
```bash
.venv/bin/python -m pytest packages/categorization/tests/test_rules.py::test_each_category_has_at_least_8_seed_phrases -v 2>&1 | tail -10
```
Expected: FAIL.

**Step 3: Replace DEFAULT_CATEGORY_KEYWORDS in constants.py**

Replace the entire `DEFAULT_CATEGORY_KEYWORDS` dict:

```python
DEFAULT_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    Category.FOOD.value: [
        "swiggy order", "zomato payment", "restaurant bill",
        "blinkit grocery delivery", "zepto quick delivery",
        "bigbasket grocery order", "dunzo delivery payment",
        "eatfit healthy meal", "dominos pizza order",
        "cafe coffee purchase", "food delivery payment",
    ],
    Category.TRANSPORT.value: [
        "uber ride payment", "ola cab trip", "rapido bike taxi",
        "metro card recharge", "irctc train ticket",
        "indigo flight booking", "makemytrip travel",
        "fastag toll payment", "petrol pump payment",
        "redbus bus ticket booking",
    ],
    Category.UTILITIES.value: [
        "electricity bill payment", "water bill bescom",
        "airtel mobile recharge", "jio prepaid recharge",
        "act fibernet broadband bill", "tata power electricity",
        "bwssb water bill payment", "vodafone postpaid bill",
        "gas cylinder booking", "broadband monthly bill",
    ],
    Category.SALARY.value: [
        "salary credited", "monthly payroll credit",
        "salary transfer neft", "payroll deposit",
        "salary for month of", "stipend payment",
        "wages credited account", "monthly income transfer",
    ],
    Category.SHOPPING.value: [
        "amazon purchase order", "flipkart product order",
        "myntra fashion purchase", "nykaa beauty order",
        "meesho clothing order", "croma electronics purchase",
        "decathlon sports equipment", "ajio fashion sale",
        "retail shopping payment", "online shopping order",
    ],
    Category.ENTERTAINMENT.value: [
        "netflix monthly subscription", "spotify premium payment",
        "jiocinema subscription", "sonyliv monthly plan",
        "hotstar disney subscription", "youtube premium individual",
        "bookmyshow movie ticket", "pvr cinema ticket",
        "play pass monthly google", "music premium subscription",
    ],
    Category.HEALTH.value: [
        "pharmacy medicine purchase", "hospital bill payment",
        "clinic doctor consultation", "1mg medicine order",
        "netmeds pharmacy delivery", "cult.fit gym membership",
        "healthifyme subscription", "apollo pharmacy order",
        "lab test payment diagnostics", "pharmeasy medicine",
    ],
    Category.EDUCATION.value: [
        "udemy course payment", "unacademy subscription",
        "byju learning app", "coursera online course",
        "tuition fee school", "college exam fee payment",
        "physics wallah subscription", "upgrad course enrollment",
        "simplilearn certification", "book purchase education",
    ],
    Category.FINANCE.value: [
        "loan emi payment", "insurance premium payment",
        "mutual fund sip investment", "zerodha brokerage",
        "groww investment transfer", "cred credit card payment",
        "bajaj finance emi debit", "fd interest deposit bank",
        "tax payment government", "upstox trading account",
    ],
    Category.PEOPLE.value: [
        "transfer to friend upi", "sent money family member",
        "gift payment personal", "reimbursement from colleague",
        "upi transfer person", "money sent contact",
        "personal transfer neft", "family expense payment",
    ],
    Category.MISC.value: [
        "miscellaneous payment service", "general charge fee",
        "other payment unknown", "service fee charge",
        "processing fee payment", "convenience fee transaction",
        "bank charge fee debit", "penalty fine payment",
    ],
}
```

**Step 4: Run tests**
```bash
.venv/bin/python -m pytest packages/categorization/tests/test_rules.py -v --tb=short 2>&1 | tail -20
```
Expected: All pass.

**Step 5: Commit**
```bash
PRE_COMMIT_ALLOW_NO_CONFIG=1 git add packages/categorization/constants.py
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat(constants): expand DEFAULT_CATEGORY_KEYWORDS to 8-10 phrases per category"
```

---

### Task 4: Expand _initialize_anchors + add CONFIDENCE_THRESHOLD in hypcd.py

**Files:**
- Modify: `packages/categorization/hypcd.py`
- Test: `packages/categorization/tests/test_hypcd_threshold.py` (create)

**Step 1: Write failing test**

```python
# packages/categorization/tests/test_hypcd_threshold.py
from packages.categorization.hypcd import CONFIDENCE_THRESHOLD


def test_confidence_threshold_exists():
    assert isinstance(CONFIDENCE_THRESHOLD, float)
    assert 0.5 < CONFIDENCE_THRESHOLD <= 1.0


def test_confidence_threshold_default_is_ninety_percent():
    assert CONFIDENCE_THRESHOLD == 0.90
```

**Step 2: Run to confirm failure**
```bash
.venv/bin/python -m pytest packages/categorization/tests/test_hypcd_threshold.py -v 2>&1 | tail -10
```
Expected: FAIL — `ImportError: cannot import name 'CONFIDENCE_THRESHOLD'`.

**Step 3: Add CONFIDENCE_THRESHOLD constant and expand _initialize_anchors**

At the top of `hypcd.py`, after the imports, add:
```python
# Confidence threshold for categorization.
# Predictions below this score are stored as suggested_category
# and the transaction is left as "Uncategorized" for user review.
# Tune after running real data through the classifier.
CONFIDENCE_THRESHOLD: float = 0.90
```

Replace `_initialize_anchors` seed_phrases dict:
```python
seed_phrases = {
    "Food": [
        "swiggy order", "zomato payment", "restaurant bill",
        "blinkit grocery delivery", "zepto quick delivery",
        "bigbasket grocery order", "dunzo delivery",
        "eatfit healthy meal", "dominos pizza order",
        "cafe coffee purchase",
    ],
    "Transport": [
        "uber ride payment", "ola cab trip", "rapido bike taxi",
        "metro card recharge", "irctc train ticket",
        "indigo flight booking", "petrol pump payment",
        "fastag toll recharge", "makemytrip travel booking",
        "redbus bus ticket",
    ],
    "Utilities": [
        "electricity bill payment", "water bill payment",
        "airtel mobile recharge", "jio prepaid recharge",
        "act fibernet broadband", "tata power electricity",
        "vodafone postpaid bill", "bwssb water payment",
        "gas cylinder booking", "broadband monthly bill",
    ],
    "Salary": [
        "salary credited account", "monthly payroll credit",
        "salary transfer neft", "payroll deposit",
        "stipend payment credited", "wages monthly income",
        "salary for the month", "income transfer received",
    ],
    "Shopping": [
        "amazon purchase order", "flipkart product order",
        "myntra fashion purchase", "nykaa beauty products",
        "meesho clothing order", "croma electronics",
        "decathlon sports equipment", "ajio fashion sale",
        "retail store purchase", "online shopping payment",
    ],
    "Entertainment": [
        "netflix monthly subscription", "spotify premium",
        "jiocinema subscription plan", "sonyliv monthly",
        "hotstar disney subscription", "youtube premium",
        "bookmyshow movie ticket", "play pass monthly",
        "music streaming subscription", "movie rental payment",
    ],
    "Health": [
        "pharmacy medicine purchase", "hospital bill payment",
        "clinic doctor consultation", "1mg medicine order",
        "netmeds pharmacy delivery", "cult.fit gym membership",
        "healthifyme subscription", "apollo pharmacy",
        "lab test diagnostics", "medical expense payment",
    ],
    "Education": [
        "udemy online course", "unacademy subscription",
        "byju learning app payment", "coursera course fee",
        "tuition fee payment", "college exam fee",
        "physics wallah subscription", "upgrad course",
        "book purchase education", "simplilearn certification",
    ],
    "Finance": [
        "loan emi debit", "insurance premium payment",
        "mutual fund sip", "zerodha brokerage",
        "groww investment", "cred credit card",
        "bajaj finance emi", "tax payment",
        "upstox trading", "fd deposit bank",
    ],
    "People": [
        "transfer to friend", "sent money family",
        "upi transfer personal", "gift payment friend",
        "reimbursement colleague", "money sent contact",
        "personal payment received", "family expense split",
    ],
}
```

**Step 4: Run tests**
```bash
.venv/bin/python -m pytest packages/categorization/tests/test_hypcd_threshold.py -v 2>&1 | tail -10
```
Expected: PASS.

**Step 5: Run full suite**
```bash
.venv/bin/python -m pytest apps/api/ packages/categorization/ -q --tb=short 2>&1 | tail -10
```
Expected: All pass.

**Step 6: Commit**
```bash
PRE_COMMIT_ALLOW_NO_CONFIG=1 git add packages/categorization/hypcd.py packages/categorization/tests/test_hypcd_threshold.py
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat(hypcd): add CONFIDENCE_THRESHOLD=0.90 and expand anchor seed phrases to 10 per category"
```

---

## BATCH 3 — Ingestion Pipeline

---

### Task 5: Expand MerchantExtractor known_merchants

**Files:**
- Modify: `packages/ingestion_engine/merchant_extractor.py`
- Test: `packages/ingestion_engine/tests/test_merchant_extractor.py` (create)

**Step 1: Write failing tests**

```python
# packages/ingestion_engine/tests/test_merchant_extractor.py
import pytest
from packages.ingestion_engine.merchant_extractor import MerchantExtractor


@pytest.fixture
def extractor():
    return MerchantExtractor()


# Clean descriptions (current data style)
def test_youtube_premium_clean(extractor):
    assert extractor.extract("YouTube Premium Individual") == "YouTube"

def test_play_pass_clean(extractor):
    assert extractor.extract("Play Pass Monthly") == "Google Play"

def test_cloud_storage_clean(extractor):
    assert extractor.extract("Cloud Storage Monthly") == "Google One"

def test_music_premium_clean(extractor):
    assert extractor.extract("Music Premium") == "Music Premium"

def test_movie_rental_clean(extractor):
    # Should NOT return "Vodafone" for "Movie Rental HD"
    result = extractor.extract("Movie Rental HD")
    assert result != "Vodafone"

def test_samay_raina_clean(extractor):
    result = extractor.extract("Samay Raina membership")
    assert "Samay Raina" in result

# UPI-style (future bank data)
def test_upi_swiggy(extractor):
    assert extractor.extract("UPI-SWIGGY INTERNET PVT LTD-swiggy@icici") == "Swiggy"

def test_upi_zomato(extractor):
    assert extractor.extract("UPI/DR/123456/ZOMATO/YESB/zomato@axl") == "Zomato"

# New brands
def test_nykaa(extractor):
    assert extractor.extract("Nykaa fashion order") == "Nykaa"

def test_meesho(extractor):
    assert extractor.extract("Meesho clothing purchase") == "Meesho"

def test_cred(extractor):
    assert extractor.extract("CRED credit card bill") == "CRED"

def test_phonepay(extractor):
    assert extractor.extract("PhonePe UPI payment") == "PhonePe"

def test_onemg(extractor):
    assert extractor.extract("1mg medicine order") == "1mg"

def test_cultfit(extractor):
    assert extractor.extract("Cult.fit gym plan") == "Cult.fit"

def test_jiocinema(extractor):
    assert extractor.extract("JioCinema subscription") == "JioCinema"

def test_indigo(extractor):
    assert extractor.extract("IndiGo flight PNR 6E1234") == "IndiGo"
```

**Step 2: Run to confirm failures**
```bash
.venv/bin/python -m pytest packages/ingestion_engine/tests/test_merchant_extractor.py -v --tb=short 2>&1 | tail -30
```

**Step 3: Expand known_merchants and fix extract() for clean descriptions**

Replace the `__init__` and `extract` method in `MerchantExtractor`:

```python
def __init__(self):
    # Ordered by specificity — longer/more-specific names first
    self.known_merchants = [
        # Food
        ("Swiggy Instamart", ["swiggy instamart", "instamart"]),
        ("Swiggy", ["swiggy"]),
        ("Zomato", ["zomato"]),
        ("Blinkit", ["blinkit", "grofers"]),
        ("Zepto", ["zepto"]),
        ("BigBasket", ["bigbasket", "big basket"]),
        ("Dunzo", ["dunzo"]),
        ("EatFit", ["eatfit"]),
        ("Licious", ["licious"]),
        ("Box8", ["box8"]),
        ("JioMart", ["jiomart"]),
        ("Country Delight", ["country delight"]),
        ("Domino's", ["dominos", "domino's"]),
        ("McDonald's", ["mcdonalds", "mcdonald"]),
        ("KFC", ["kfc"]),
        ("Burger King", ["burger king"]),
        ("Pizza Hut", ["pizza hut"]),
        ("Starbucks", ["starbucks"]),
        ("Subway", ["subway"]),
        ("Haldiram's", ["haldiram"]),
        ("Barbeque Nation", ["barbeque nation"]),
        # Transport
        ("Uber", ["uber"]),
        ("Ola", ["olacabs", "ola cabs"]),
        ("Rapido", ["rapido"]),
        ("InDrive", ["indrive"]),
        ("BluSmart", ["blusmart"]),
        ("IRCTC", ["irctc"]),
        ("IndiGo", ["indigo", "6e"]),
        ("SpiceJet", ["spicejet"]),
        ("Air India", ["air india", "airindia"]),
        ("Vistara", ["vistara"]),
        ("MakeMyTrip", ["makemytrip"]),
        ("Ixigo", ["ixigo"]),
        ("redBus", ["redbus"]),
        ("Yatra", ["yatra"]),
        ("Goibibo", ["goibibo"]),
        ("HP Petrol", ["hpcl", "hp petrol", "hindustan petroleum"]),
        ("Indian Oil", ["iocl", "indianoil", "indian oil"]),
        ("Shell", ["shell petrol", "shell pump"]),  # scoped to avoid over-match
        # Shopping
        ("Amazon", ["amazon", "amzn"]),
        ("Flipkart", ["flipkart"]),
        ("Myntra", ["myntra"]),
        ("Ajio", ["ajio"]),
        ("Meesho", ["meesho"]),
        ("Nykaa", ["nykaa"]),
        ("Tata CLiQ", ["tata cliq", "tatacliq"]),
        ("Snapdeal", ["snapdeal"]),
        ("Decathlon", ["decathlon"]),
        ("Croma", ["croma"]),
        ("Reliance Digital", ["reliance digital"]),
        ("Vijay Sales", ["vijay sales"]),
        ("Zudio", ["zudio"]),
        ("Westside", ["westside"]),
        ("DMart", ["dmart", "d-mart"]),
        # Entertainment
        ("Netflix", ["netflix"]),
        ("Spotify", ["spotify"]),
        ("JioCinema", ["jiocinema"]),
        ("SonyLIV", ["sonyliv", "sony liv"]),
        ("ZEE5", ["zee5"]),
        ("Disney+ Hotstar", ["hotstar", "disney+"]),
        ("Amazon Prime", ["prime video", "amazon prime"]),
        ("Apple TV+", ["apple tv", "apple.com/bill"]),
        ("Mubi", ["mubi"]),
        ("Google Play", ["play pass", "google play"]),
        ("YouTube", ["youtube"]),
        ("Google One", ["google one", "cloud storage monthly", "google 200"]),
        ("JioSaavn", ["jiosaavn", "jio saavn"]),
        ("Gaana", ["gaana"]),
        ("BookMyShow", ["bookmyshow"]),
        ("PVR", ["pvr cinemas", "pvr cinema"]),
        ("INOX", ["inox"]),
        ("Steam", ["steam"]),
        # Utilities
        ("Airtel", ["airtel"]),
        ("Jio", ["reliance jio", "jio fiber", "jio prepaid"]),
        ("Vi (Vodafone)", ["vodafone", " vi ", "vi postpaid", "vi prepaid"]),
        ("BSNL", ["bsnl"]),
        ("ACT Fibernet", ["act fibernet", "act broadband"]),
        ("Hathway", ["hathway"]),
        ("Tata Power", ["tata power"]),
        ("BESCOM", ["bescom"]),
        ("BWSSB", ["bwssb"]),
        ("MSEDCL", ["msedcl"]),
        # Health
        ("Apollo Pharmacy", ["apollo pharmacy", "apollo247", "apollo 247"]),
        ("1mg", ["1mg", "tata 1mg"]),
        ("Netmeds", ["netmeds"]),
        ("Pharmeasy", ["pharmeasy"]),
        ("MedPlus", ["medplus"]),
        ("Cult.fit", ["cult.fit", "cultfit"]),
        ("Healthifyme", ["healthifyme"]),
        ("Practo", ["practo"]),
        # Finance
        ("Zerodha", ["zerodha"]),
        ("Groww", ["groww"]),
        ("Upstox", ["upstox"]),
        ("Angel One", ["angel one", "angelone"]),
        ("INDmoney", ["indmoney"]),
        ("CRED", ["cred "]),  # trailing space avoids matching "credit"
        ("PhonePe", ["phonepe", "phone pe"]),
        ("Paytm", ["paytm"]),
        ("Google Pay", ["gpay", "google pay", "tez"]),
        ("Bajaj Finance", ["bajaj finance", "bajaj finserv"]),
        # Education
        ("BYJU'S", ["byju", "byjus"]),
        ("Unacademy", ["unacademy"]),
        ("Vedantu", ["vedantu"]),
        ("upGrad", ["upgrad"]),
        ("Physics Wallah", ["physics wallah", "pw app"]),
        ("Udemy", ["udemy"]),
        ("Coursera", ["coursera"]),
        ("Simplilearn", ["simplilearn"]),
    ]

    self.noise_patterns = [
        r"UPI[-/][A-Z0-9]+[-/]",
        r"UPI[-/]",
        r"NEFT[-/]",
        r"RTGS[-/]",
        r"IMPS[-/]",
        r"ACH\s+D[-/]?",
        r"NACH\s+",
        r"ECS\s+",
        r"POS\s+",
        r"\b(DR|CR|MB|TFR|WDL|TFNR)\b",
    ]


def extract(self, raw_description: str) -> str:
    """Extract a clean merchant name from a transaction description.

    Priority:
    1. Known merchant list (highest confidence, avoids false positives)
    2. UPI/NEFT structured format (parse payee segment)
    3. Clean description heuristic (strip noise, title-case)
    """
    if not raw_description:
        return ""

    cleaned_lower = raw_description.lower().strip()

    # Strategy 1: Known merchant matching (most precise)
    for official_name, aliases in self.known_merchants:
        for alias in aliases:
            if alias in cleaned_lower:
                return official_name

    # Strategy 2: Structured UPI/NEFT format
    # e.g. "UPI/DR/123456/MERCHANT NAME/BANKCODE/vpa@bank"
    # e.g. "NEFT-HDFC0001234-MERCHANT NAME"
    match = re.search(
        r"(?:UPI|IMPS|NEFT|RTGS|UPVDR)(?:/|-)\d*(?:/|-)?([A-Za-z][^/\-@]{2,30})(?:[/\-@]|$)",
        raw_description,
        re.IGNORECASE,
    )
    if match:
        candidate = match.group(1).strip()
        candidate = re.sub(r"[0-9._]+$", "", candidate).strip()
        if len(candidate) > 2:
            return candidate.title()

    # Strategy 3: Clean description heuristic
    # Strip known noise tokens and return title-cased result
    cleaned = raw_description
    for pattern in self.noise_patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    # Remove trailing digits/codes (e.g. "HD", "4K", reference numbers)
    cleaned = re.sub(r"\b[A-Z]{1,3}\d+\b", " ", cleaned)   # e.g. "6E1234"
    cleaned = re.sub(r"\b\d{4,}\b", " ", cleaned)           # long numbers
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        return raw_description.title()

    # Take up to first 4 meaningful words
    words = [w for w in cleaned.split() if len(w) > 1]
    return " ".join(words[:4]).title()
```

**Step 4: Run tests**
```bash
.venv/bin/python -m pytest packages/ingestion_engine/tests/test_merchant_extractor.py -v --tb=short 2>&1 | tail -30
```
Expected: All pass.

**Step 5: Commit**
```bash
PRE_COMMIT_ALLOW_NO_CONFIG=1 git add packages/ingestion_engine/merchant_extractor.py packages/ingestion_engine/tests/test_merchant_extractor.py
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat(ingestion): expand MerchantExtractor with 100+ brands and fix clean-description extraction"
```

---

### Task 6: Add infer_payment_method()

**Files:**
- Modify: `packages/ingestion_engine/merchant_extractor.py` (append function)
- Test: `packages/ingestion_engine/tests/test_merchant_extractor.py` (append tests)

**Step 1: Write failing tests**

```python
# Append to packages/ingestion_engine/tests/test_merchant_extractor.py
from packages.ingestion_engine.merchant_extractor import infer_payment_method


def test_upi_description():
    assert infer_payment_method("UPI-SWIGGY-pay@okaxis") == "UPI"

def test_neft_description():
    assert infer_payment_method("NEFT-HDFC0001234-SALARY") == "Bank Transfer"

def test_rtgs_description():
    assert infer_payment_method("RTGS/001/VENDOR PAYMENT") == "Bank Transfer"

def test_imps_description():
    assert infer_payment_method("IMPS/P2P/9876543210/Rahul") == "IMPS"

def test_ach_description():
    assert infer_payment_method("ACH D-BAJAJ FINANCE-123") == "Auto Debit"

def test_nach_description():
    assert infer_payment_method("NACH DEBIT HDFC BANK") == "Auto Debit"

def test_atm_description():
    assert infer_payment_method("ATM WDL 1234 KORAMANGALA") == "Cash"

def test_pos_description():
    assert infer_payment_method("POS PURCHASE ZARA STORE") == "Card"

def test_google_play_is_subscription():
    assert infer_payment_method("YouTube Premium Individual") == "Subscription"

def test_cloud_storage_is_subscription():
    assert infer_payment_method("Cloud Storage Monthly") == "Subscription"

def test_play_pass_is_subscription():
    assert infer_payment_method("Play Pass Monthly") == "Subscription"

def test_unknown_defaults_to_other():
    assert infer_payment_method("Random merchant description") == "Other"

def test_empty_defaults_to_other():
    assert infer_payment_method("") == "Other"
```

**Step 2: Run to confirm failures**
```bash
.venv/bin/python -m pytest packages/ingestion_engine/tests/test_merchant_extractor.py -k "infer_payment" -v 2>&1 | tail -20
```
Expected: `ImportError: cannot import name 'infer_payment_method'`.

**Step 3: Add infer_payment_method to merchant_extractor.py**

Append after the `MerchantExtractor` class:

```python
_SUBSCRIPTION_KEYWORDS = [
    "premium", "subscription", "monthly plan", "annual plan",
    "play pass", "google play", "cloud storage", "google one",
    "music premium", "movie rental", "membership",
    "youtube", "netflix", "spotify", "hotstar", "jiocinema",
    "sonyliv", "zee5", "mubi", "prime video",
]


def infer_payment_method(description: str) -> str:
    """Infer payment method from transaction description patterns.

    Returns one of: "UPI", "Bank Transfer", "IMPS", "Auto Debit",
                    "Cash", "Card", "Subscription", "Other"
    """
    if not description:
        return "Other"

    d = description.upper()

    if d.startswith("UPI") or "UPI/" in d or "UPI-" in d:
        return "UPI"
    if "NEFT" in d or "RTGS" in d:
        return "Bank Transfer"
    if "IMPS" in d:
        return "IMPS"
    if "ACH" in d or "NACH" in d or "ECS" in d:
        return "Auto Debit"
    if "ATM" in d and ("WDL" in d or "CASH" in d or "WITHDRAW" in d):
        return "Cash"
    if "POS" in d or "SWIPE" in d or "CARD PURCHASE" in d:
        return "Card"

    d_lower = description.lower()
    if any(kw in d_lower for kw in _SUBSCRIPTION_KEYWORDS):
        return "Subscription"

    return "Other"
```

**Step 4: Run tests**
```bash
.venv/bin/python -m pytest packages/ingestion_engine/tests/test_merchant_extractor.py -v --tb=short 2>&1 | tail -20
```
Expected: All pass.

**Step 5: Commit**
```bash
PRE_COMMIT_ALLOW_NO_CONFIG=1 git add packages/ingestion_engine/merchant_extractor.py packages/ingestion_engine/tests/test_merchant_extractor.py
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat(ingestion): add infer_payment_method() for UPI/NEFT/Card/Subscription detection"
```

---

### Task 7: Wire MerchantExtractor + infer_payment_method into _build_transaction_row

**Files:**
- Modify: `apps/api/domains/ingestion/router.py`
- Test: `apps/api/domains/ingestion/tests/test_merchant_wiring.py` (create)

**Step 1: Write failing test**

```python
# apps/api/domains/ingestion/tests/test_merchant_wiring.py
from apps.api.domains.ingestion.router import _build_transaction_row


def test_merchant_name_extracted_from_description_when_empty():
    row = {
        "date": "2026-01-01",
        "amount": -210.0,
        "description": "YouTube Premium Individual",
        "merchant": "",          # empty from CSV parser
        "payment_method": "",    # empty from CSV parser
        "currency": "INR",
        "status": "completed",
    }
    result = _build_transaction_row(row, "user-1", "fp123")
    assert result["merchant_name"] == "YouTube"
    assert result["merchant_name"] != ""


def test_payment_method_inferred_when_empty():
    row = {
        "date": "2026-01-01",
        "amount": -99.0,
        "description": "UPI-SWIGGY-pay@okaxis",
        "merchant": "",
        "payment_method": "",
        "currency": "INR",
        "status": "completed",
    }
    result = _build_transaction_row(row, "user-1", "fp456")
    assert result["payment_method"] == "UPI"


def test_payment_method_preserved_when_csv_provides_it():
    row = {
        "date": "2026-01-01",
        "amount": -500.0,
        "description": "some transaction",
        "merchant": "Some Store",
        "payment_method": "Card",   # already filled by parser
        "currency": "INR",
        "status": "completed",
    }
    result = _build_transaction_row(row, "user-1", "fp789")
    assert result["payment_method"] == "Card"


def test_google_play_gets_subscription_payment_method():
    row = {
        "date": "2026-01-01",
        "amount": -129.0,
        "description": "Play Pass Monthly",
        "merchant": "",
        "payment_method": "",
        "currency": "INR",
        "status": "completed",
    }
    result = _build_transaction_row(row, "user-1", "fp999")
    assert result["payment_method"] == "Subscription"
```

**Step 2: Run to confirm failures**
```bash
.venv/bin/python -m pytest apps/api/domains/ingestion/tests/test_merchant_wiring.py -v --tb=short 2>&1 | tail -20
```
Expected: FAIL — merchant_name is empty / payment_method is empty.

**Step 3: Update _build_transaction_row in ingestion/router.py**

Add imports at the top of the router file (after existing imports):
```python
from packages.ingestion_engine.merchant_extractor import MerchantExtractor, infer_payment_method

_merchant_extractor = MerchantExtractor()  # module-level singleton
```

Replace the `_build_transaction_row` function:
```python
def _build_transaction_row(
    row: dict,
    user_id: str,
    fingerprint: str,
    category: str = "Uncategorized",
    suggested_category: str | None = None,
    confidence_score: float | None = None,
) -> dict:
    """Build a Supabase-ready transaction row from a parsed row."""
    amount = float(row.get("amount", 0) or 0)
    tx_type = "credit" if amount >= 0 else "debit"
    description = str(row.get("description", "") or "")

    # Use CSV-provided merchant name, fall back to extractor
    raw_merchant = str(row.get("merchant", "") or "").strip()
    merchant_name = raw_merchant if raw_merchant else _merchant_extractor.extract(description)

    # Use CSV-provided payment method, fall back to inference
    raw_payment = str(row.get("payment_method", "") or "").strip()
    payment_method = raw_payment if raw_payment else infer_payment_method(description)

    result = {
        "user_id": user_id,
        "transaction_date": str(row.get("date", "")),
        "amount": amount,
        "currency": str(row.get("currency", "INR") or "INR"),
        "description": description,
        "merchant_name": merchant_name,
        "category": category,
        "payment_method": payment_method,
        "status": str(row.get("status", "completed") or "completed"),
        "type": tx_type,
        "fingerprint": fingerprint,
        "raw_data": {k: v for k, v in row.items() if v is not None},
    }

    if suggested_category is not None:
        result["suggested_category"] = suggested_category
    if confidence_score is not None:
        result["confidence_score"] = confidence_score

    return result
```

**Step 4: Run tests**
```bash
.venv/bin/python -m pytest apps/api/domains/ingestion/tests/test_merchant_wiring.py -v --tb=short 2>&1 | tail -20
```
Expected: All pass.

**Step 5: Run full suite**
```bash
.venv/bin/python -m pytest apps/api/ -q --tb=short 2>&1 | tail -10
```

**Step 6: Commit**
```bash
PRE_COMMIT_ALLOW_NO_CONFIG=1 git add apps/api/domains/ingestion/router.py apps/api/domains/ingestion/tests/test_merchant_wiring.py
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat(ingestion): wire MerchantExtractor and infer_payment_method into _build_transaction_row"
```

---

### Task 8: Apply confidence threshold in background classification

**Files:**
- Modify: `apps/api/domains/ingestion/router.py` (update `_classify_descriptions` + `_classify_and_update_transactions`)
- Test: `apps/api/domains/ingestion/tests/test_confidence_threshold.py` (create)

**Step 1: Write failing test**

```python
# apps/api/domains/ingestion/tests/test_confidence_threshold.py
from unittest.mock import MagicMock, patch
from apps.api.domains.ingestion.router import _classify_descriptions


def test_classify_descriptions_returns_confidence():
    """_classify_descriptions must return confidence alongside category."""
    mock_clf = [
        {"category": "Food", "confidence": 0.95},
        {"category": "Transport", "confidence": 0.60},
    ]
    with patch(
        "apps.api.domains.ingestion.router.classify_batch_in_process",
        return_value=mock_clf,
    ):
        # Import here to get the patched version
        from apps.api.domains.ingestion import router as ingestion_router
        result = ingestion_router._classify_descriptions(["swiggy", "some unknown"])

    assert result["swiggy"]["category"] == "Food"
    assert result["swiggy"]["confidence"] == 0.95
    assert result["some unknown"]["category"] == "Transport"
    assert result["some unknown"]["confidence"] == 0.60
```

**Step 2: Run to confirm failure**
```bash
.venv/bin/python -m pytest apps/api/domains/ingestion/tests/test_confidence_threshold.py -v --tb=short 2>&1 | tail -15
```
Expected: FAIL — `_classify_descriptions` returns `{desc: str}`, not `{desc: dict}`.

**Step 3: Update _classify_descriptions to return confidence**

Replace `_classify_descriptions` in `apps/api/domains/ingestion/router.py`:

```python
def _classify_descriptions(descriptions: list[str]) -> dict[str, dict]:
    """Classify descriptions using HypCD.

    Returns: {description: {"category": str, "confidence": float}}
    """
    from apps.api.domains.categorization.service import classify_batch_in_process

    result: dict[str, dict] = {}
    if not descriptions:
        return result

    try:
        classifications = classify_batch_in_process(descriptions)
        for desc, clf in zip(descriptions, classifications):
            result[desc] = {
                "category":   clf.get("category", "Uncategorized"),
                "confidence": float(clf.get("confidence", 0.0)),
            }
        return result
    except Exception as e:
        logger.warning("hypcd_unavailable_for_import", error=str(e))

    # Fallback keyword map (no confidence data — default to 1.0 for rule matches)
    keyword_map = [
        ("Food",          ["swiggy", "zomato", "blinkit", "zepto", "bigbasket", "food",
                           "restaurant", "dining", "dunzo", "dominos", "kfc", "burger"]),
        ("Transport",     ["uber", "ola", "rapido", "metro", "irctc", "fuel", "petrol",
                           "indigo", "makemytrip", "redbus", "fastag"]),
        ("Shopping",      ["amazon", "flipkart", "myntra", "ajio", "meesho", "nykaa",
                           "decathlon", "croma"]),
        ("Utilities",     ["electric", "water", "gas", "bill", "recharge", "airtel",
                           "jio", "vodafone", "broadband"]),
        ("Entertainment", ["netflix", "spotify", "hotstar", "prime", "youtube",
                           "jiocinema", "sonyliv", "subscription", "play pass"]),
        ("Health",        ["hospital", "pharmacy", "doctor", "clinic", "1mg",
                           "netmeds", "cultfit", "gym"]),
        ("Education",     ["course", "tuition", "udemy", "byju", "unacademy"]),
        ("Finance",       ["loan", "emi", "insurance", "zerodha", "groww", "cred"]),
        ("Salary",        ["salary", "payroll", "stipend"]),
    ]
    for desc in descriptions:
        d = desc.lower()
        matched = "Uncategorized"
        for category, keywords in keyword_map:
            if any(kw in d for kw in keywords):
                matched = category
                break
        result[desc] = {"category": matched, "confidence": 1.0 if matched != "Uncategorized" else 0.0}

    return result
```

**Step 4: Update _classify_and_update_transactions to apply threshold**

Replace `_classify_and_update_transactions` in `apps/api/domains/ingestion/router.py`:

```python
def _classify_and_update_transactions(user_id: str, fps_to_desc: dict, token: str) -> None:
    """Background task: classify inserted transactions and patch their categories.

    Applies CONFIDENCE_THRESHOLD — low-confidence predictions are stored as
    suggested_category so users can review them in the UI.
    """
    from packages.categorization.hypcd import CONFIDENCE_THRESHOLD

    unique_descs = list({desc for desc in fps_to_desc.values() if desc.strip()})
    if not unique_descs:
        return

    try:
        category_map = _classify_descriptions(unique_descs)
    except Exception as e:
        logger.warning("bg_classify_failed", error=str(e))
        return

    # Separate confident vs uncertain predictions
    confident_fps:    dict[str, list[str]] = defaultdict(list)   # category -> [fps]
    uncertain_rows:   list[dict]            = []                  # [{fp, category, confidence}]

    for fp, desc in fps_to_desc.items():
        pred = category_map.get(desc, {"category": "Uncategorized", "confidence": 0.0})
        cat  = pred["category"]
        conf = pred["confidence"]

        if conf >= CONFIDENCE_THRESHOLD and cat != "Uncategorized":
            confident_fps[cat].append(fp)
        else:
            uncertain_rows.append({"fp": fp, "suggested": cat, "confidence": conf})

    try:
        from supabase import create_client
        from apps.api.core.auth import _get_supabase_url, _get_supabase_anon_key
        client = create_client(_get_supabase_url(), _get_supabase_anon_key())
        client.auth.set_session(token, "")

        # Batch-update confident predictions
        for category, fps in confident_fps.items():
            client.table("transactions").update(
                {"category": category, "suggested_category": None, "confidence_score": None}
            ).eq("user_id", user_id).in_("fingerprint", fps).execute()

        # Update uncertain predictions — leave as Uncategorized, store suggestion
        for row in uncertain_rows:
            client.table("transactions").update({
                "category":          "Uncategorized",
                "suggested_category": row["suggested"],
                "confidence_score":  row["confidence"],
            }).eq("user_id", user_id).eq("fingerprint", row["fp"]).execute()

        logger.info(
            "bg_classify_complete",
            user_id=user_id,
            confident=sum(len(v) for v in confident_fps.values()),
            uncertain=len(uncertain_rows),
        )
    except Exception as e:
        logger.warning("bg_category_update_failed", user_id=user_id, error=str(e))
```

**Step 5: Run tests**
```bash
.venv/bin/python -m pytest apps/api/domains/ingestion/ -v --tb=short 2>&1 | tail -25
```
Expected: All pass.

**Step 6: Commit**
```bash
PRE_COMMIT_ALLOW_NO_CONFIG=1 git add apps/api/domains/ingestion/router.py apps/api/domains/ingestion/tests/test_confidence_threshold.py
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat(ingestion): apply CONFIDENCE_THRESHOLD — low-confidence predictions stored as suggested_category"
```

---

## BATCH 4 — API

---

### Task 9: Add GET /accounts/transactions/uncategorized endpoint

**Files:**
- Modify: `apps/api/domains/accounts/router.py`
- Test: `apps/api/domains/accounts/tests/test_uncategorized.py` (create)

**Step 1: Write failing test**

```python
# apps/api/domains/accounts/tests/test_uncategorized.py
import pytest
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.core.auth import get_user_client


class MockData:
    data = [
        {
            "id": "tx-1",
            "description": "Unknown merchant",
            "amount": -500.0,
            "category": "Uncategorized",
            "suggested_category": "Shopping",
            "confidence_score": 0.72,
            "transaction_date": "2026-01-15T00:00:00Z",
            "merchant_name": "Unknown Merchant",
            "payment_method": "UPI",
            "type": "debit",
            "created_at": "2026-01-15T00:00:00Z",
        }
    ]


class MockTable:
    def __init__(self):
        self._data = MockData()
    def select(self, *args): return self
    def eq(self, *args): return self
    def order(self, *args): return self
    def limit(self, *args): return self
    def execute(self): return self._data


class MockClient:
    def __init__(self):
        self.auth = type("auth", (), {
            "get_user": lambda self: type("r", (), {
                "user": type("u", (), {"id": "user-1"})()
            })()
        })()
    def table(self, name):
        return MockTable()


@pytest.fixture
def client():
    app.dependency_overrides[get_user_client] = lambda: MockClient()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_uncategorized_endpoint_exists(client):
    resp = client.get(
        "/accounts/transactions/uncategorized",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert resp.status_code == 200


def test_uncategorized_returns_list(client):
    resp = client.get(
        "/accounts/transactions/uncategorized",
        headers={"Authorization": "Bearer fake-token"},
    )
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_uncategorized_includes_suggested_category(client):
    resp = client.get(
        "/accounts/transactions/uncategorized",
        headers={"Authorization": "Bearer fake-token"},
    )
    items = resp.json()["items"]
    assert len(items) > 0
    assert "suggested_category" in items[0]
    assert "confidence_score" in items[0]
```

**Step 2: Run to confirm failure**
```bash
.venv/bin/python -m pytest apps/api/domains/accounts/tests/test_uncategorized.py -v --tb=short 2>&1 | tail -15
```
Expected: FAIL — 404 (endpoint doesn't exist).

**Step 3: Add the endpoint to accounts/router.py**

Add this BEFORE the existing `@router.patch("/transactions/batch")` endpoint (static routes first):

```python
@router.get("/transactions/uncategorized")
async def list_uncategorized_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    client: Client = Depends(get_user_client),
):
    """Return transactions where category='Uncategorized', including suggested_category."""
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    user_id = user_response.user.id

    try:
        res = (
            client.table("transactions")
            .select(
                "id, description, amount, category, suggested_category, "
                "confidence_score, transaction_date, merchant_name, "
                "payment_method, type, created_at"
            )
            .eq("user_id", user_id)
            .eq("category", "Uncategorized")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"items": res.data or [], "count": len(res.data or [])}
    except Exception as e:
        logger.error("uncategorized_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch uncategorized transactions")
```

Also add `Query` to FastAPI imports if not already present:
```python
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Path, Query
```

**Step 4: Run tests**
```bash
.venv/bin/python -m pytest apps/api/domains/accounts/tests/test_uncategorized.py -v --tb=short 2>&1 | tail -15
```
Expected: All pass.

**Step 5: Run full suite**
```bash
.venv/bin/python -m pytest apps/api/ -q --tb=short 2>&1 | tail -10
```

**Step 6: Commit**
```bash
PRE_COMMIT_ALLOW_NO_CONFIG=1 git add apps/api/domains/accounts/router.py apps/api/domains/accounts/tests/test_uncategorized.py
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat(accounts): add GET /accounts/transactions/uncategorized endpoint"
```

---

### Task 10: Update merchant-batch to match on merchant_name

**Files:**
- Modify: `apps/api/domains/accounts/router.py` (update_transaction bulk update)
- Test: `apps/api/domains/accounts/tests/test_merchant_batch.py` (update existing)

**Step 1: Write failing test**

Add to `apps/api/domains/accounts/tests/test_merchant_batch.py`:

```python
def test_merchant_batch_matches_on_merchant_name_when_available(monkeypatch):
    """When merchant_name is set, bulk update must use merchant_name not description keyword."""
    calls = []

    class MockTable:
        def select(self, *a): return self
        def eq(self, field, val):
            calls.append(("eq", field, val))
            return self
        def update(self, data): return self
        def ilike(self, field, val):
            calls.append(("ilike", field, val))
            return self
        def execute(self):
            class R:
                data = [{"description": "Swiggy Order", "category": "Food"}]
            return R()

    class MockClient:
        def auth(self): pass
        def table(self, name): return MockTable()

    # The transaction being corrected has merchant_name set
    tx = {
        "id": "tx-1",
        "description": "Swiggy Order #12345",
        "merchant_name": "Swiggy",
        "category": "Food",
    }
    # When merchant_name is populated, should match on merchant_name, NOT ilike description
    merchant_name_eq_calls = [c for c in calls if c[0] == "eq" and c[1] == "merchant_name"]
    ilike_calls = [c for c in calls if c[0] == "ilike"]
    # After implementation: merchant_name_eq_calls > 0, ilike_calls == 0
    # (Test is structural — see implementation note below)
```

**Implementation note:** The test above is structural. The key change is in `update_transaction`: when `tx["merchant_name"]` is non-empty, use `.eq("merchant_name", tx["merchant_name"])` instead of `.ilike("description", f"%{keyword}%")`. Fall back to keyword ilike only when `merchant_name` is empty.

**Step 2: Update the merchant-batch block in update_transaction**

Find the merchant-batch block (currently uses `_extract_merchant_keyword` + `.ilike`). Replace:

```python
# OLD — matches on description keyword (over-matches)
keyword = _extract_merchant_keyword(description)
if keyword:
    batch_result = (
        client.table("transactions")
        .update({"category": update.category, "is_manual": True})
        .eq("user_id", user_id)
        .eq("category", update.old_category)
        .ilike("description", f"%{keyword}%")
        .execute()
    )
```

With:

```python
# NEW — prefer merchant_name match (precise), fall back to keyword ilike
merchant_name = tx.get("merchant_name", "").strip()
if merchant_name:
    # Precise match on normalized merchant name
    batch_result = (
        client.table("transactions")
        .update({
            "category":          update.category,
            "suggested_category": None,
            "confidence_score":  None,
            "is_manual":         True,
        })
        .eq("user_id", user_id)
        .eq("category", update.old_category)
        .eq("merchant_name", merchant_name)
        .execute()
    )
else:
    # Fallback: keyword-based for older transactions without merchant_name
    keyword = _extract_merchant_keyword(description)
    if not keyword:
        batch_result = type("R", (), {"data": []})()
    else:
        batch_result = (
            client.table("transactions")
            .update({
                "category":          update.category,
                "suggested_category": None,
                "confidence_score":  None,
                "is_manual":         True,
            })
            .eq("user_id", user_id)
            .eq("category", update.old_category)
            .ilike("description", f"%{keyword}%")
            .execute()
        )
```

Also clear `suggested_category`/`confidence_score` on the primary transaction update:

In the same function, find the initial single-transaction update and add the two new fields:
```python
update_data = {"category": update.category, "is_manual": True,
               "suggested_category": None, "confidence_score": None}
if update.original_category is not None:
    update_data["original_category"] = update.original_category
```

**Step 3: Write correction to training_corrections when accepting suggestion**

In `update_transaction`, after the merchant-batch update succeeds and when `update.old_category` was the suggested_category, write to `training_corrections`:

```python
# Write active learning correction record
if update.old_category and update.category and update.category != "Uncategorized":
    try:
        client.table("training_corrections").insert({
            "user_id":            user_id,
            "transaction_id":     transaction_id,
            "description":        tx.get("description", ""),
            "original_category":  update.old_category,
            "corrected_category": update.category,
        }).execute()
    except Exception:
        pass  # non-critical, don't fail the request
```

**Step 4: Run tests**
```bash
.venv/bin/python -m pytest apps/api/domains/accounts/ -v --tb=short 2>&1 | tail -20
```
Expected: All pass.

**Step 5: Commit**
```bash
PRE_COMMIT_ALLOW_NO_CONFIG=1 git add apps/api/domains/accounts/router.py
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "fix(accounts): merchant-batch matches on merchant_name to prevent over-matching; clears suggestion on correction"
```

---

## BATCH 5 — Frontend

---

### Task 11: Update TypeScript types and API client

**Files:**
- Modify: `apps/web/app/dashboard/transactions/page.tsx` (TransactionRow type)
- Modify: `apps/web/lib/api/client.ts` (add getUncategorized)
- Test: TypeScript check only

**Step 1: Add suggested_category and confidence_score to TransactionRow**

In `apps/web/app/dashboard/transactions/page.tsx`, update the `TransactionRow` type:

```typescript
type TransactionRow = {
  id: string;
  user_id: string;
  transaction_date: string;
  amount: number;
  description: string;
  category: string;
  suggested_category?: string | null;
  confidence_score?: number | null;
  original_category?: string | null;
  payment_method: string;
  merchant_name: string;
  status: string;
  type: string;
  created_at: string;
  raw_data?: Record<string, any>;
};
```

**Step 2: Add getUncategorized to accountsApi in client.ts**

Find the `accountsApi` object in `apps/web/lib/api/client.ts` and add:

```typescript
getUncategorized: async (token: string, limit = 50) => {
  return apiFetch<{ items: Transaction[]; count: number }>(
    `/accounts/transactions/uncategorized?limit=${limit}`,
    { method: 'GET', token }
  );
},
```

Also update the `Transaction` interface in client.ts to include:
```typescript
suggested_category?: string | null;
confidence_score?: number | null;
```

**Step 3: TypeScript check**
```bash
cd "/Users/hassangameryt/Documents/Antigravity/SCALE APP/apps/web"
npx tsc --noEmit 2>&1 | head -20
```
Expected: 0 new errors.

**Step 4: Commit**
```bash
PRE_COMMIT_ALLOW_NO_CONFIG=1 git add apps/web/app/dashboard/transactions/page.tsx apps/web/lib/api/client.ts
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat(frontend): add suggested_category types and getUncategorized API method"
```

---

### Task 12: Add Review tab to transactions page

**Files:**
- Modify: `apps/web/app/dashboard/transactions/page.tsx`

**Step 1: Read the current tab structure in transactions page**

First, search for the existing tab/view structure:
```bash
grep -n "tab\|Tab\|activeTab\|setTab\|view\|View" \
  "apps/web/app/dashboard/transactions/page.tsx" | head -20
```

**Step 2: Add state and data-fetching for the Review tab**

In the component, add state for the active tab and uncategorized transactions:

```typescript
const [activeTab, setActiveTab] = useState<'all' | 'review'>('all');
const [uncategorized, setUncategorized] = useState<TransactionRow[]>([]);
const [reviewLoading, setReviewLoading] = useState(false);
const [reviewCount, setReviewCount] = useState(0);
```

Add a fetch function for uncategorized:

```typescript
const fetchUncategorized = useCallback(async () => {
  if (!session?.access_token) return;
  setReviewLoading(true);
  try {
    const result = await accountsApi.getUncategorized(session.access_token);
    setUncategorized(result.items as TransactionRow[]);
    setReviewCount(result.count);
  } catch {
    setUncategorized([]);
  } finally {
    setReviewLoading(false);
  }
}, [session]);

useEffect(() => {
  fetchUncategorized();
}, [fetchUncategorized]);
```

**Step 3: Add tab switcher UI**

In the JSX, before the transaction list, add:

```tsx
{/* Tab switcher */}
<div className="flex gap-2 mb-4">
  <button
    onClick={() => setActiveTab('all')}
    className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
      activeTab === 'all'
        ? 'bg-white text-gray-900 shadow-sm'
        : 'text-gray-500 hover:text-gray-700'
    }`}
  >
    All Transactions
  </button>
  <button
    onClick={() => setActiveTab('review')}
    className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
      activeTab === 'review'
        ? 'bg-white text-gray-900 shadow-sm'
        : 'text-gray-500 hover:text-gray-700'
    }`}
  >
    Review
    {reviewCount > 0 && (
      <span className="bg-amber-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
        {reviewCount}
      </span>
    )}
  </button>
</div>
```

**Step 4: Add Review tab content**

After the tab switcher, conditionally render the review list:

```tsx
{activeTab === 'review' && (
  <div className="space-y-2">
    {reviewLoading && (
      <div className="flex items-center justify-center py-8 text-gray-400">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        Loading uncategorized transactions...
      </div>
    )}
    {!reviewLoading && uncategorized.length === 0 && (
      <div className="text-center py-12 text-gray-400">
        <Check className="h-10 w-10 mx-auto mb-3 text-emerald-400" />
        <p className="font-medium">All transactions are categorized!</p>
      </div>
    )}
    {!reviewLoading && uncategorized.map((tx) => (
      <div
        key={tx.id}
        className="flex items-center justify-between rounded-2xl bg-white/60 backdrop-blur-sm border border-amber-100 p-4 gap-4"
      >
        <div className="flex-1 min-w-0">
          <p className="font-medium text-gray-900 truncate">{tx.description}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {tx.merchant_name} · {tx.payment_method} · {new Date(tx.transaction_date).toLocaleDateString()}
          </p>
          {tx.suggested_category && (
            <span className="inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 text-[11px] font-semibold border border-amber-200">
              Suggested: {tx.suggested_category}
              {tx.confidence_score && (
                <span className="text-amber-400">
                  ({(tx.confidence_score * 100).toFixed(0)}%)
                </span>
              )}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`font-mono font-bold text-sm ${tx.amount < 0 ? 'text-red-500' : 'text-emerald-600'}`}>
            {tx.amount < 0 ? '-' : '+'}₹{Math.abs(tx.amount).toLocaleString('en-IN')}
          </span>
          {/* Accept suggested category */}
          {tx.suggested_category && (
            <button
              onClick={() => saveCategoryEdit(tx, tx.suggested_category!)}
              className="flex items-center justify-center h-8 w-8 rounded-full bg-emerald-50 hover:bg-emerald-100 text-emerald-600 transition-colors"
              title={`Accept: ${tx.suggested_category}`}
            >
              <Check className="h-4 w-4" />
            </button>
          )}
          {/* Reclassify with picker */}
          <button
            onClick={() => {
              setEditingTx(tx);
              setEditCategory(tx.suggested_category || tx.category);
            }}
            className="flex items-center justify-center h-8 w-8 rounded-full bg-gray-50 hover:bg-gray-100 text-gray-600 transition-colors"
            title="Reclassify"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    ))}
  </div>
)}
```

**Step 5: Update saveCategoryEdit to refresh Review tab**

After a successful category save, call `fetchUncategorized()` to refresh the badge count:

```typescript
// At the end of saveCategoryEdit, after successful update:
await fetchUncategorized();
```

**Step 6: TypeScript check**
```bash
cd "/Users/hassangameryt/Documents/Antigravity/SCALE APP/apps/web"
npx tsc --noEmit 2>&1 | head -20
```
Expected: 0 new errors.

**Step 7: Run frontend tests**
```bash
cd "/Users/hassangameryt/Documents/Antigravity/SCALE APP/apps/web"
npm test -- --passWithNoTests 2>&1 | tail -10
```
Expected: All pass.

**Step 8: Commit**
```bash
PRE_COMMIT_ALLOW_NO_CONFIG=1 git add apps/web/app/dashboard/transactions/page.tsx
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat(frontend): add Review tab to transactions page with accept/reclassify for uncategorized transactions"
```

---

## Final Verification

```bash
cd "/Users/hassangameryt/Documents/Antigravity/SCALE APP"
.venv/bin/python -m pytest apps/api/ packages/categorization/ packages/ingestion_engine/ -q --tb=short 2>&1 | tail -10
```
Expected: All tests pass.

```bash
cd apps/web && npx tsc --noEmit && npm test -- --passWithNoTests 2>&1 | tail -10
```
Expected: 0 TS errors, all tests pass.
