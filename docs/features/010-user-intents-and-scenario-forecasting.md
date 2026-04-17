# Feature: User Intents + Scenario Forecasting

> **Doc ID:** 010-user-intents-and-scenario-forecasting
> **Date:** 2026-04-17
> **DRI:** Mohammed Hassan Mohiddin
> **Status:** Draft
> **Type:** Feature LLD

## Problem Statement

SCALE's TFT forecast extrapolates from historical transactions. It cannot, by design, anticipate events the user already knows about but the model has never seen: an upcoming vacation, a planned appliance purchase, a new job starting in six weeks, a baby on the way. These show up in the forecast only after the transactions land — which is too late to be useful.

The Cowork brainstorming session resolved this with a structured user-intent layer: the user tells SCALE about known future events through a fixed schema; the backend wires those intents into the TFT as known-future covariates (for dated cash flows) and into the RFC-005 stochastic widener (for life events). No NLP, no ML, no free text. The same schema becomes the contract for the future LLM orchestrator — when it lands, it is a natural-language → schema converter, not a replacement.

Five concrete gaps between LLD 009's design and what this feature delivers:

1. **No `user_intents` table.** LLD 009 does not model user-declared future events at all. Nothing the user says about their upcoming month is represented in the forecast.
2. **No scenario endpoint.** The AI Insights page planned in LLD 011 will render "Scenario Impact Cards" comparing forecast with vs. without an intent; that endpoint does not exist.
3. **No confidence-aware forecast shift.** The Cowork synthesis specified tiered behaviour: high-confidence intents shift the P50 median directly; medium-confidence widen the P90 upward; low-confidence widen symmetrically. None of this is wired.
4. **LIFE_EVENT signal has no home.** A user flagging "we're expecting" should trigger the RFC-005 widener's `active_intents` parameter (already speced to accept a list). Today that parameter is always passed empty because no intent source exists.
5. **Confusion between "scheduled cash flows" and "user intents."** RFC-005 introduces `scheduled_cashflows` for heuristically-detected recurring events; intents are user-declared future events that mostly map to the same concept but include non-dated types (LIFE_EVENT, SAVINGS_GOAL) that do not. A clean bridge between the two models is required so the ML pipeline stays simple while the user-facing domain stays faithful.

Without this feature, the forecast will be systematically wrong around every declarable life event — a structural blind spot independent of model capacity, data richness, or hyperparameter choice.

## Success Criteria

- [ ] `public.user_intents` table migration applied with full seven-type enum and RLS policies permitting users to read/insert/update their own rows
- [ ] `POST /forecast/intents` creates a new intent; `GET /forecast/intents` lists the user's active intents; `PATCH /forecast/intents/{id}` updates; `DELETE /forecast/intents/{id}` soft-deletes via `is_active=false`
- [ ] `POST /forecast/scenario` returns a `ScenarioResponse` with two `ForecastResponse` payloads (`with_intents` + `without_intents`) plus a computed `delta` sub-object
- [ ] Dated intent types (INCOME_CHANGE, PLANNED_LARGE_EXPENSE, OBLIGATION_CHANGE, FD_MATURITY, EXPECTED_BONUS) automatically bridge to `scheduled_cashflows` rows with `source='intent'`; toggling intent `is_active` cascades to the bridged row
- [ ] LIFE_EVENT intents are passed as the `active_intents` argument to RFC-005's `widen_intervals` during `compute_insights`
- [ ] SAVINGS_GOAL intents are stored and returned via `GET /forecast/intents` but NOT injected into the TFT or the widener (explicitly metadata-only in v1)
- [ ] Confidence field behaves per the tiered mapping: `high` → 100 % covariate amount, `medium` → 70 % covariate amount, `low` → 0 % covariate amount. On top of the covariate weight, non-high-confidence intents (any type) **activate** RFC-005's `widen_intervals` by appearing in `active_intents`; the widener applies its fixed `SPREAD_BUMP_INTENT=0.25` per RFC-005 §Layer 4 — LLD 010 does NOT change widener internals.
- [ ] All new code covered by unit + integration tests
- [ ] Backward compatibility: users with zero intents see no change in forecast behaviour vs. pre-feature state

## Scope

### In Scope

- `public.user_intents` table with the seven intent types (INCOME_CHANGE, PLANNED_LARGE_EXPENSE, LIFE_EVENT, OBLIGATION_CHANGE, SAVINGS_GOAL, FD_MATURITY, EXPECTED_BONUS)
- REST CRUD endpoints under `/forecast/intents/`
- Scenario endpoint `POST /forecast/scenario` accepting `intent_ids_to_exclude` + `ephemeral_intents` override list
- Bridge logic converting dated intents to `scheduled_cashflows` rows (RFC-005 `source='intent'` path)
- LIFE_EVENT propagation into RFC-005's `widen_intervals`
- Confidence-tiered forecast behaviour
- Pydantic schemas for `UserIntent`, `IntentCreateRequest`, `ScenarioRequest`, `ScenarioResponse`
- Service layer in `apps/api/domains/forecasting/intents_service.py` owning CRUD + bridge + scenario orchestration
- Unit + integration tests

### Out of Scope

- Frontend form for intent entry — owned by LLD 011 (AI Insights page)
- Natural-language intent creation (LLM parser) — v1.5+; the schema here IS the LLM's target contract
- ML-based intent classification ("we detect you're planning a trip from your browsing") — multimodal path, explicitly rejected in the Cowork synthesis
- SAVINGS_GOAL progress tracking UI — v1.5; v1 stores the goal but does not surface progress
- Batch-import of intents from external sources (Google Calendar, emails) — future
- Notification / reminder when an intent becomes active (e.g., "your vacation is next week") — future
- Auto-dismissal of fulfilled intents (detect a matching transaction landed → mark intent fulfilled) — future
- Per-intent type custom UI affordances (e.g., a date-picker wizard for LIFE_EVENT "expected delivery date") — frontend scope

## Design

### Architecture / Data Flow

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant API as ⚙️ FastAPI
    participant SVC as 📊 IntentsService
    participant DB as 💾 Supabase
    participant FSVC as 🧠 ForecastService
    participant INS as 🧮 compute_insights (RFC-003)
    participant TFT as 🧠 TFT (RFC-005 panel)

    Note over U,DB: Intent CRUD
    U->>API: POST /forecast/intents { type, amount, start_date, ... }
    API->>SVC: create_intent(payload)
    SVC->>DB: INSERT user_intents
    alt dated intent (INCOME_CHANGE, PLANNED_LARGE_EXPENSE, OBLIGATION_CHANGE, FD_MATURITY, EXPECTED_BONUS)
        SVC->>DB: INSERT scheduled_cashflows (source='intent', confidence=mapped)
    else LIFE_EVENT or SAVINGS_GOAL
        Note over SVC: no bridge row; LIFE_EVENT feeds widener live at predict time
    end
    SVC-->>API: UserIntent
    API-->>U: 201 { UserIntent }

    Note over U,TFT: Scenario forecast
    U->>API: POST /forecast/scenario { intent_ids_to_exclude, ephemeral_intents }
    API->>FSVC: scenario_predict(user_id, excludes, ephemeral)
    FSVC->>DB: fetch all active user_intents
    FSVC->>FSVC: A = build active set minus excludes
    FSVC->>FSVC: B = A ∪ ephemeral
    par A (baseline "without")
        FSVC->>TFT: predict(scheduled_cashflows from heuristic only)
        FSVC->>INS: compute_insights(..., active_intents=[])
    and B (with intents)
        FSVC->>TFT: predict(scheduled_cashflows from heuristic + bridged intents)
        FSVC->>INS: compute_insights(..., active_intents=[LIFE_EVENT from B])
    end
    FSVC->>FSVC: delta = B.insights − A.insights
    FSVC-->>API: ScenarioResponse { with_intents: B, without_intents: A, delta }
    API-->>U: 200 { ScenarioResponse }
```

### Domain Model

```python
# apps/api/domains/forecasting/schemas.py  (additions)

from enum import Enum
from typing import Annotated, Literal
from uuid import UUID
from datetime import date
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    INCOME_CHANGE        = "income_change"
    PLANNED_LARGE_EXPENSE = "planned_large_expense"
    LIFE_EVENT           = "life_event"
    OBLIGATION_CHANGE    = "obligation_change"
    SAVINGS_GOAL         = "savings_goal"
    FD_MATURITY          = "fd_maturity"
    EXPECTED_BONUS       = "expected_bonus"


class IntentConfidence(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class UserIntent(BaseModel):
    id:             UUID
    user_id:        UUID
    intent_type:    IntentType
    amount:         float | None = None               # required for dated types, None for LIFE_EVENT + SAVINGS_GOAL-without-amount
    amount_delta:   float | None = None               # signed delta for INCOME_CHANGE (e.g. +20000 raise)
    category_bucket: str | None = None                # optional, from RFC-005 CATEGORY_BUCKETS
    start_date:     date
    end_date:       date | None = None                # optional for one-off events; required for recurring
    confidence:     IntentConfidence
    is_recurring:   bool = False
    rrule_freq:     Literal["monthly", "weekly", "biweekly", "quarterly", "annual"] | None = None
    notes:          str | None = None                 # free-text, max 280 chars
    is_active:      bool = True
    created_at:     str                               # ISO 8601 timestamptz
    updated_at:     str


class IntentCreateRequest(BaseModel):
    intent_type:    IntentType
    amount:         float | None = None
    amount_delta:   float | None = None
    category_bucket: str | None = None
    start_date:     date
    end_date:       date | None = None
    confidence:     IntentConfidence = IntentConfidence.MEDIUM
    is_recurring:   bool = False
    rrule_freq:     Literal["monthly", "weekly", "biweekly", "quarterly", "annual"] | None = None
    notes:          Annotated[str | None, Field(max_length=280)] = None


class IntentUpdateRequest(BaseModel):
    amount:       float | None = None
    amount_delta: float | None = None
    start_date:   date | None = None
    end_date:     date | None = None
    confidence:   IntentConfidence | None = None
    notes:        str | None = None
    is_active:    bool | None = None


class ScenarioRequest(BaseModel):
    horizon:               Annotated[int, Field(ge=1, le=30)] = 30
    intent_ids_to_exclude: list[UUID] = []
    ephemeral_intents:     Annotated[list[IntentCreateRequest], Field(max_length=20)] = []


class ScenarioDelta(BaseModel):
    """Per-field delta (B - A) on the insights block."""
    safe_to_spend:           float
    overdraft_risk_score:    float
    predicted_monthly_spend: float
    predicted_monthly_income: float
    month_end_p50_delta:     float
    confidence_band_width_delta: float


class ScenarioResponse(BaseModel):
    with_intents:    ForecastResponse                 # per RFC-003 §1 — same module, direct ref
    without_intents: ForecastResponse
    delta:           ScenarioDelta
    applied_intents: list[UserIntent]                 # what ended up being folded in
    excluded_intents: list[UserIntent]                # what was toggled off
```

> **Module-order note.** `ForecastResponse` (from RFC-003 §1) and `ScenarioResponse` both live in `apps/api/domains/forecasting/schemas.py`. `ScenarioResponse` must be declared **after** `ForecastResponse` in that file so the direct class reference resolves at module-load time — no forward-reference string, no `model_rebuild()` call needed. If a future refactor moves them to separate modules, switch to `ForecastResponse` import + `ScenarioResponse.model_rebuild()` explicitly.

Pydantic field-level validators enforce cross-field rules:

- `amount` required for INCOME_CHANGE / PLANNED_LARGE_EXPENSE / OBLIGATION_CHANGE / FD_MATURITY / EXPECTED_BONUS.
- `amount` optional for LIFE_EVENT + SAVINGS_GOAL.
- `is_recurring=True` requires `rrule_freq` and `end_date` (or `end_date=None` for indefinite).
- `SAVINGS_GOAL` requires `end_date` (target deadline).
- `amount_delta` allowed only on `INCOME_CHANGE`.
- `category_bucket` must be one of RFC-005's `CATEGORY_BUCKETS` constants.

### Intent → `scheduled_cashflows` Bridge

```python
# packages/forecasting/intent_bridge.py  (new module)

from datetime import timedelta
from uuid import UUID

from apps.api.domains.forecasting.schemas import UserIntent, IntentType, IntentConfidence

# Per Cowork synthesis confidence → injection mapping
CONFIDENCE_COVARIATE_WEIGHT = {
    IntentConfidence.HIGH:   1.0,
    IntentConfidence.MEDIUM: 0.7,
    IntentConfidence.LOW:    0.0,
}

DATED_INTENT_TYPES = {
    IntentType.INCOME_CHANGE,
    IntentType.PLANNED_LARGE_EXPENSE,
    IntentType.OBLIGATION_CHANGE,
    IntentType.FD_MATURITY,
    IntentType.EXPECTED_BONUS,
}


def should_have_bridge_row(intent: UserIntent) -> bool:
    """Does this intent type get a scheduled_cashflows row at all?
    Answered independently of is_active — soft-deletes still keep the row
    (with is_active=false mirrored) so audit + UI still works.
    LIFE_EVENT and SAVINGS_GOAL never get rows regardless of is_active."""
    return intent.intent_type in DATED_INTENT_TYPES


def intent_to_scheduled_cashflow_row(intent: UserIntent) -> dict:
    """Translate a dated UserIntent into the scheduled_cashflows row shape.
    Never called for LIFE_EVENT or SAVINGS_GOAL.

    Amount sign convention: PLANNED_LARGE_EXPENSE + OBLIGATION_CHANGE → negative.
    INCOME_CHANGE (amount_delta) + FD_MATURITY + EXPECTED_BONUS → positive.

    Confidence-weighted amount: amount × CONFIDENCE_COVARIATE_WEIGHT[intent.confidence].
    Low-confidence intents produce a 0-amount row that is still written (so the
    row exists for audit/UI) but contributes zero to the TFT covariate. RFC-005
    widener applies the P90 bump separately based on the intent's presence.

    Source-of-truth split for amounts:
    * `user_intents.amount`        — raw user-declared amount (UI reads this).
    * `scheduled_cashflows.amount` — confidence-weighted amount (TFT reads this).
    The UI never reads scheduled_cashflows.amount for intent rows. The TFT never
    reads user_intents at all. `IntentsService` owns the mapping in both writes
    (create, patch); there is no third consumer.
    """
    weight = CONFIDENCE_COVARIATE_WEIGHT[intent.confidence]
    raw_amount = intent.amount or abs(intent.amount_delta or 0.0)
    signed_amount = _sign_by_type(intent.intent_type) * raw_amount * weight
    return {
        "user_id":         intent.user_id,
        "merchant":        f"intent:{intent.id}",        # sentinel merchant so the heuristic detector ignores
        "amount":          signed_amount,
        "category_bucket": intent.category_bucket or _default_bucket_for_type(intent.intent_type),
        "rrule_freq":      intent.rrule_freq or "monthly",
        "next_occurrence": intent.start_date,
        "end_date":        intent.end_date,
        "confidence":      1.0,                           # scheduled_cashflows.confidence is about recurrence regularity,
                                                          # not intent confidence; user asserted it → regularity = 1.0
        "source":          "intent",
        "is_active":       intent.is_active,
    }
```

Bridge operations from `IntentsService`:

| Intent mutation | Bridge action |
|---|---|
| `POST /forecast/intents` creates dated intent | INSERT `scheduled_cashflows` row with `source='intent'` |
| `POST /forecast/intents` creates LIFE_EVENT / SAVINGS_GOAL | no bridge row; LIFE_EVENT consumed by widener at predict time |
| `PATCH /forecast/intents/{id}` on dated intent (amount, confidence, dates changed) | UPDATE matching `scheduled_cashflows` row by `source_rule_id` lookup (a new column added; see §Database Changes) |
| `PATCH /forecast/intents/{id}` setting `is_active=false` | UPDATE `scheduled_cashflows.is_active=false` |
| `DELETE /forecast/intents/{id}` (soft) | same as `is_active=false` |

### LIFE_EVENT Propagation Into Widener

RFC-005 §Layer 4 defines `widen_intervals(forecast_matrix, volatilities, active_intents=[])`. Today `active_intents` is always empty because no source exists. LLD 010 populates it with every active intent whose confidence is `low` or `medium`, regardless of type:

```python
# apps/api/domains/forecasting/service.py  (inside ForecastService.predict)

active = [i for i in self._fetch_active_intents(user_id) if i.is_active]
widener_intents = [
    i for i in active
    if (
        i.intent_type == IntentType.LIFE_EVENT                      # always widen on LIFE_EVENT
        or i.confidence in (IntentConfidence.LOW, IntentConfidence.MEDIUM)
    )
]
forecast_matrix = widen_intervals(
    forecast_matrix,
    volatilities,
    active_intents=widener_intents,     # RFC-005 widener applies SPREAD_BUMP_INTENT=0.25 once when list non-empty
)
```

**Confidence ↔ widener interaction (clarification for H3/H4):** RFC-005's widener is type-agnostic and stacks a single fixed `SPREAD_BUMP_INTENT=0.25` when `active_intents` is non-empty (capped at `MAX_SPREAD_MULTIPLIER=2.0`). LLD 010 does **not** change widener internals — it only controls which intents enter the list. The "medium → +15 %, low → +25 %" language used in earlier drafts conflated two mechanisms; the true v1 contract is:

| Confidence | Covariate amount injected | Goes into widener's `active_intents`? | Net effect |
|---|---|---|---|
| `high`   | 100 % × amount | No (dated) / Yes (LIFE_EVENT always) | P50 shifts via covariate; intervals stay sharp (dated) |
| `medium` | 70  % × amount | Yes | P50 shifts partially + widener fires once at +0.25 |
| `low`    | 0   % × amount | Yes | Widener fires once; no P50 shift |

LIFE_EVENT overrides: LIFE_EVENT always enters the widener list irrespective of confidence (a baby is unpredictable even when you're sure it's coming). LIFE_EVENT has no covariate contribution regardless of confidence because it has no amount to project.

Future (v1.5) — per-confidence widener bumps (medium=+0.15, low=+0.25) require an RFC-005 DEVIATION extending `widen_intervals(active_intents=[...], spread_bumps_per_intent=[...])`. Out of scope for v1 to keep RFC-005 stable.

### Scenario Endpoint Design

`POST /forecast/scenario` body:

```json
{
  "horizon": 30,
  "intent_ids_to_exclude": ["uuid-of-vacation-intent"],
  "ephemeral_intents": [
    { "intent_type": "planned_large_expense",
      "amount": 80000,
      "start_date": "2026-05-15",
      "confidence": "high",
      "category_bucket": "entertainment",
      "notes": "test: would Goa trip at 80k blow my budget?" }
  ]
}
```

Processing:

1. Fetch all active intents for the user (`A` = set).
2. Build B: A minus `intent_ids_to_exclude`, plus `ephemeral_intents` (not persisted — scoped to request).
3. Run two forecasts in parallel:
   - **without_intents**: scheduled_cashflows filtered to `source IN ('heuristic','user_override')` AND active intents from B excluded from the LIFE_EVENT widener list.
   - **with_intents**: scheduled_cashflows including `source='intent'` from B's dated intents; LIFE_EVENT widener fed from B.
4. Compute `delta` as (with.insights − without.insights) field-by-field for the six comparable metrics.
5. Return both `ForecastResponse` payloads plus the delta.

The "without_intents" path intentionally does NOT turn off heuristically-detected recurrences. The user's real rent, EMI, salary still show up. Only user-declared intents are toggled. This is the Cowork synthesis's intended semantic — scenarios compare "with my plans" vs. "without my plans", not "with everything" vs. "counterfactual universe with no obligations".

### Component Architecture

```
apps/api/domains/forecasting/
  router.py                  # MODIFY — add /intents/* routes + /scenario
  intents_service.py         # NEW — CRUD + bridge orchestration
  service.py                 # MODIFY — wire LIFE_EVENT into widen_intervals; scenario_predict method
  schemas.py                 # MODIFY — append IntentType enum + UserIntent + ScenarioRequest + ScenarioResponse
  tests/
    test_intents_service.py  # NEW
    test_scenario.py         # NEW
    test_intent_schemas.py   # NEW

packages/forecasting/
  intent_bridge.py           # NEW — intent_to_scheduled_cashflow_row + confidence mapping
  tests/
    test_intent_bridge.py    # NEW

supabase/migrations/
  20260418300000_user_intents.sql            # NEW — user_intents table + RLS
  20260418300001_scheduled_cashflows_source_rule_id.sql  # NEW — adds source_rule_id column to scheduled_cashflows
```

## API Changes

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/forecast/intents` | Create a new user intent (body: `IntentCreateRequest`; returns 201 + `UserIntent`) |
| GET | `/forecast/intents` | List current user's active intents (`?include_inactive=true` shows soft-deleted) |
| GET | `/forecast/intents/{id}` | Fetch single intent |
| PATCH | `/forecast/intents/{id}` | Update mutable fields (body: `IntentUpdateRequest`) |
| DELETE | `/forecast/intents/{id}` | Soft-delete (sets `is_active=false`; bridged row cascades) |
| POST | `/forecast/scenario` | Scenario A/B forecast (body: `ScenarioRequest`; returns `ScenarioResponse`) |

All six endpoints require JWT authentication. Rate-limited via existing `RateLimiter + rate_limit_dependency` pattern at 20/min per user (intent CRUD is cheap; scenario is heavier — scenario gets 5/min).

No changes to existing forecast endpoints. `GET /forecast/predict` transparently consumes stored intents on every call via the widener wiring and the `scheduled_cashflows` join.

## Database Changes

Two new migrations. Existing tables: `public.scheduled_cashflows` (RFC-005), `public.user_predictions` (RFC-003), `public.training_jobs` (LLD 009) — unchanged except for one column addition to `scheduled_cashflows`.

**Migration ordering:** Migration 2 (`20260418300001_scheduled_cashflows_source_rule_id.sql`) depends on Migration 1 (`20260418300000_user_intents.sql`) because its new FK references `public.user_intents(id)`. The timestamp-based filename sort (`300000 < 300001`) guarantees correct apply sequence under Supabase's migration runner. Do not rename either file without preserving this order. RFC-005's `20260418200000_scheduled_cashflows.sql` must be applied before either of these (it creates the base table).

### Migration 1: `public.user_intents`

```sql
CREATE TABLE public.user_intents (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    intent_type      text        NOT NULL CHECK (intent_type IN (
        'income_change','planned_large_expense','life_event',
        'obligation_change','savings_goal','fd_maturity','expected_bonus'
    )),
    amount           numeric,
    amount_delta     numeric,
    category_bucket  text        CHECK (category_bucket IS NULL OR category_bucket IN (
        'salary','rent','groceries','dining','transport','utilities',
        'entertainment','health','emi_loan','investment','transfer','other'
    )),
    start_date       date        NOT NULL,
    end_date         date,
    confidence       text        NOT NULL DEFAULT 'medium' CHECK (confidence IN ('low','medium','high')),
    is_recurring     boolean     NOT NULL DEFAULT false,
    rrule_freq       text        CHECK (rrule_freq IS NULL OR rrule_freq IN (
        'monthly','weekly','biweekly','quarterly','annual'
    )),
    notes            text        CHECK (notes IS NULL OR length(notes) <= 280),
    is_active        boolean     NOT NULL DEFAULT true,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT amount_required_for_dated CHECK (
        intent_type NOT IN (
            'income_change','planned_large_expense','obligation_change',
            'fd_maturity','expected_bonus'
        )
        OR amount IS NOT NULL OR amount_delta IS NOT NULL
    ),
    CONSTRAINT recurring_has_rrule CHECK (
        is_recurring = false OR rrule_freq IS NOT NULL
    ),
    CONSTRAINT savings_goal_has_end_date CHECK (
        intent_type <> 'savings_goal' OR end_date IS NOT NULL
    )
);

-- Auto-update updated_at on row mutation
CREATE OR REPLACE FUNCTION public.user_intents_touch_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_user_intents_touch_updated_at
BEFORE UPDATE ON public.user_intents
FOR EACH ROW EXECUTE FUNCTION public.user_intents_touch_updated_at();

CREATE INDEX idx_user_intents_user_active
    ON public.user_intents (user_id, is_active, start_date);

ALTER TABLE public.user_intents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users read own intents"
    ON public.user_intents FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "users insert own intents"
    ON public.user_intents FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users update own intents"
    ON public.user_intents FOR UPDATE TO authenticated
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- No DELETE policy — clients soft-delete via is_active=false. Hard delete only
-- via service role for ON DELETE CASCADE from auth.users.
```

### Migration 2: `scheduled_cashflows.source_rule_id`

```sql
-- Links scheduled_cashflows rows created by the intent bridge back to the
-- originating user_intents row, so intent mutations can cascade.
ALTER TABLE public.scheduled_cashflows
    ADD COLUMN source_rule_id uuid
        REFERENCES public.user_intents(id) ON DELETE CASCADE;

CREATE INDEX idx_scheduled_cashflows_source_rule
    ON public.scheduled_cashflows (source_rule_id)
    WHERE source = 'intent';
```

The `ON DELETE CASCADE` means a hard-deleted intent (only possible when auth.users deletes) automatically removes its bridged row. For soft-delete (`is_active=false`), the bridge service updates the companion row explicitly.

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|---|---|
| User creates INCOME_CHANGE without `amount` nor `amount_delta` | Pydantic + CHECK constraint reject with 400 |
| User sets `is_recurring=true` without `rrule_freq` | Pydantic + CHECK constraint reject with 400 |
| User creates LIFE_EVENT with `amount` provided | Accept; amount stored but ignored by bridge (no dated row); UI may use it to label the event |
| User deletes an intent that has a bridged `scheduled_cashflows` row | Soft-delete intent (is_active=false) + update bridged row to is_active=false; hard-delete via cascade only if auth.users row is deleted |
| Intent `start_date` in the past | Accept. Widener + scheduler still read active intents; past-dated intents just don't appear in future covariate projections |
| Scenario request with `intent_ids_to_exclude` referencing another user's intent | 404 — the RLS SELECT policy prevents the service from seeing that row |
| Scenario request with 50 ephemeral intents (abuse) | `ephemeral_intents` list length capped at 20 per request (Pydantic `Field(max_length=20)`); 400 on overflow |
| User has 1000+ intents stored | `GET /forecast/intents` paginates (default limit 50, `?cursor=...` for next page); forecast-time fetch queries with `is_active=true AND start_date >= now() - interval '30 days'` to bound the set |
| Scenario run when user has no trained TFT | Both paths fall back to Chronos-only; delta may be zero if Chronos ignores `scheduled_cashflows` (expected — scheduled cash flows are TFT-specific known-future covariates; Chronos receives only closing_balance) |
| Widener receives 10 LIFE_EVENT intents (unrealistic but possible) | Widener clamps total widening at MAX_SPREAD_MULTIPLIER=2.0 (RFC-005 §Layer 4); stacked intents do not produce uselessly-wide bands |
| SAVINGS_GOAL intent in scenario call | Included in `applied_intents` / `excluded_intents` response lists but produces identical forecasts in both paths (metadata-only); delta is zero; UI can still render "your goal: ₹2L by Dec" alongside |
| Intent created with `confidence='low'` | Bridge writes scheduled_cashflows row with `amount = 0` (per 0.0 weight); widener applies +25% spread bump; UI labels it "your uncertain plan" |
| Redis pub-sub invalidation after retraining should also re-read intents | Not required — intents are fetched fresh on every predict/scenario request; no caching of intent list per user |
| Scenario endpoint `horizon > 30` | Pydantic `Field(le=30)` rejects with 400 (RFC-003 §1 caps horizon at 30) |

## Security Considerations

- **Authentication:** all six new endpoints require valid Supabase JWT via `get_current_user_id` dependency, consistent with existing forecast routes.
- **Authorisation:** RLS on `public.user_intents` restricts SELECT/INSERT/UPDATE to `auth.uid() = user_id`. Defence in depth — service code also filters by `user_id` on every query, so a future RLS misconfiguration does not become a data leak.
- **PII handling:** `notes` field is free-text up to 280 chars; users may write anything, including names. Treated as PII. Not sent to any external model (the LLM orchestrator path for v1.5 will route through a SCALE-operated service; notes never leave SCALE's backend until that ship).
- **Rate limiting:** intent CRUD capped at 20/min/user, scenario endpoint at 5/min/user via the existing `RateLimiter + rate_limit_dependency` pattern. Prevents ephemeral-intent abuse (running scenarios in a loop to probe model behaviour).
- **Bridge integrity:** `source_rule_id` FK ensures bridged `scheduled_cashflows` rows cannot orphan. If an intent is hard-deleted, the cascade removes the companion. If soft-deleted, the service updates the companion atomically in one transaction (Supabase RPC wraps both writes in a BEGIN/COMMIT).
- **Scenario isolation:** ephemeral intents in a scenario request are not persisted. No side effects on `user_intents` or `scheduled_cashflows`. The scenario endpoint is strictly read-only with respect to stored state.
- **Resource limits:** `ephemeral_intents` list capped at 20; `horizon` capped at 30; `notes` capped at 280 chars. `GET /forecast/intents` paginates.

## Testing Strategy

### Unit Tests

- `test_intent_schemas.py` — every intent type + confidence combination validates; cross-field validators reject invalid shapes (INCOME_CHANGE without amount, recurring without rrule, SAVINGS_GOAL without end_date, LIFE_EVENT with amount_delta)
- `test_intent_bridge.py` — `should_bridge` returns True only for dated types; `intent_to_scheduled_cashflow_row` signs amounts correctly per type; confidence weighting produces 1.0 / 0.7 / 0.0 amounts; LIFE_EVENT + SAVINGS_GOAL never produce a row
- `test_intents_service.py` — CRUD flows with mocked Supabase: create dated intent writes two rows in one transaction; create LIFE_EVENT writes one row; PATCH amount updates both user_intents and bridged scheduled_cashflows; DELETE cascades to bridged row via is_active=false; update to confidence changes the bridged amount
- `test_scenario.py` — delta math (B − A) correct for each `ScenarioDelta` field; ephemeral intents not persisted; excluded intent removed from both TFT covariates AND widener list; SAVINGS_GOAL inclusion/exclusion produces zero delta

### Integration Tests

- End-to-end intent CRUD via FastAPI TestClient + fakeredis + test Supabase
- Scenario endpoint returns correct shape with a user having one dated intent + one LIFE_EVENT + one SAVINGS_GOAL
- Intent soft-delete at `t=0` → forecast at `t=1` no longer includes the excluded covariate nor widens on LIFE_EVENT
- Widener interaction: scenario with `confidence=high` vs `confidence=low` for the same PLANNED_LARGE_EXPENSE produces different P10/P90 spreads

### Contract Tests

- RLS enforcement: a user's JWT cannot SELECT another user's `user_intents` rows (asserted by integration test hitting real Supabase local instance with two synthetic users)
- RFC-005 contract: the bridged `scheduled_cashflows` row's `category_bucket` is always in `CATEGORY_BUCKETS`
- **Two-level cascade:** hard-deleting a row from `auth.users` removes both `user_intents` rows (via RFC-005 Migration 1 CASCADE) AND their bridged `scheduled_cashflows` rows (via `source_rule_id` CASCADE on Migration 2). Asserted by `apps/api/domains/forecasting/tests/test_intents_cascade.py` against a real Supabase local instance: seed one user + one dated intent + one LIFE_EVENT; `DELETE FROM auth.users WHERE id = ...`; assert both tables now have zero rows for that user.

### Performance Smoke

- Scenario endpoint p50 ≤ 2× single-forecast p50 (runs two forecasts in parallel via `asyncio.gather`, so the wall-clock penalty should be small)
- 1000-intent user: `GET /forecast/intents?limit=50` returns under 100 ms; forecast path bounded intent query returns under 50 ms

## Related Documents

- Feature LLD: `docs/features/009-prediction-engine.md` — this feature adds to the forecast surface it defines
- RFC: `docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md` — `ForecastResponse` + `ForecastInsights` shape that `ScenarioResponse` wraps
- RFC: `docs/rfcs/RFC-004-tft-inference-cache-architecture.md` — no interaction; the cache stores TFT models, not intents
- RFC: `docs/rfcs/RFC-005-aggregation-strategy-three-tier-data-separation.md` — defines `scheduled_cashflows` (intents bridge to it), `CATEGORY_BUCKETS` (intents reference), `widen_intervals` (LIFE_EVENT feeds it)
- RFC: `docs/rfcs/RFC-006-forecast-evaluation-harness.md` — no v1 interaction; v1.5 may add intent-rich users to the stratified sample
- Future LLD: `docs/features/011-ai-insights-page.md` (not yet written) — frontend form for intent entry + Scenario Impact Cards consume `/forecast/scenario`
- Future RFC: natural-language → schema LLM orchestrator — will sit in front of these same endpoints; the schema defined here is its contract
- HLD to update: `docs/design/system-architecture.md` — add the intent layer + scenario endpoint to the forecast component

## Changelog

| Date | Entry |
|---|---|
| 2026-04-17 | Initial draft. Schema directly lifted from the Cowork brainstorming synthesis. Seven intent types; confidence-tiered mapping; two-table model (`user_intents` source of truth + bridged `scheduled_cashflows` rows with `source='intent'`); scenario endpoint accepts both stored-intent toggles and ephemeral overrides. LIFE_EVENT feeds RFC-005 widener; SAVINGS_GOAL metadata-only. Frontend form owned by LLD 011 (not this LLD). Natural-language intent creation explicitly deferred — this schema is the LLM orchestrator's future contract. Status: Draft. |
| 2026-04-17 | Spec review fixes before commit. C1 — explicit source-of-truth split documented: `user_intents.amount` = raw (UI reads), `scheduled_cashflows.amount` = confidence-weighted (TFT reads); nothing else reads either. C2 — dropped forward-reference quotes on `ForecastResponse` (same module as `ScenarioResponse`); added module-ordering note. H1/H2 — `ScenarioRequest.horizon: Annotated[int, Field(ge=1, le=30)]` and `ephemeral_intents: Annotated[..., Field(max_length=20)]` match the edge-case claims. H3/H4 — clarified that RFC-005 widener is type-agnostic at `SPREAD_BUMP_INTENT=0.25` fixed; LLD 010 only controls which intents enter `active_intents` (low/medium confidence or any LIFE_EVENT); per-confidence variable bumps deferred to a v1.5 RFC-005 DEVIATION. Table inserted showing confidence × covariate × widener interaction. H5 — renamed `should_bridge` to `should_have_bridge_row` with docstring clarifying it is type-only, independent of `is_active`; is_active mirroring handled by IntentsService. H6 — added migration-ordering note citing the timestamp-sort guarantee and RFC-005's base migration dependency. H7 — added two-level cascade contract test to Testing Strategy. M2 — `savings_goal_has_end_date` CHECK constraint added. M4 — `updated_at` BEFORE UPDATE trigger added to Migration 1. |
