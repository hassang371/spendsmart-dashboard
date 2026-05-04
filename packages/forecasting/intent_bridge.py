"""LLD 010 — User intent → ``scheduled_cashflows`` bridge.

Pure-function module. No DB access, no HTTP, no logging side effects.
``IntentsService`` owns the orchestration that calls this module.

**Source-of-truth split for amounts (LLD 010 Spec C1):**

* ``user_intents.amount`` — raw user-declared amount (UI reads this).
* ``scheduled_cashflows.amount`` — confidence-weighted amount (TFT reads
  this). Computed here as ``raw_amount × CONFIDENCE_COVARIATE_WEIGHT``.

Nothing else reads either column. The UI never reads
``scheduled_cashflows.amount`` for ``source='intent'`` rows. The TFT
covariate join never reads ``user_intents`` directly. ``IntentsService``
owns the mapping in both writes (create + patch); there is no third
consumer.

LIFE_EVENT and SAVINGS_GOAL never produce a bridge row regardless of
``is_active``. LIFE_EVENT feeds RFC-005's stochastic widener at predict
time instead. SAVINGS_GOAL is metadata-only in v1.

Refs: docs/features/010-user-intents-and-scenario-forecasting.md
      §Intent → scheduled_cashflows Bridge
"""

from __future__ import annotations

from typing import Any

from apps.api.domains.forecasting.schemas import (
    IntentConfidence,
    IntentType,
    UserIntent,
)

__all__ = [
    "CONFIDENCE_COVARIATE_WEIGHT",
    "DATED_INTENT_TYPES",
    "intent_to_scheduled_cashflow_row",
    "should_have_bridge_row",
]


# Per LLD 010 §Design (Confidence × covariate × widener interaction).
# High = full amount; Medium = 70%; Low = 0% (still write the row for
# audit/UI; widener fires on its own based on the intent's presence).
CONFIDENCE_COVARIATE_WEIGHT: dict[IntentConfidence, float] = {
    IntentConfidence.HIGH: 1.0,
    IntentConfidence.MEDIUM: 0.7,
    IntentConfidence.LOW: 0.0,
}


# The five "dated" intent types per LLD 010 §Architecture / Data Flow.
# These bridge to scheduled_cashflows; the other two (LIFE_EVENT,
# SAVINGS_GOAL) do not.
DATED_INTENT_TYPES: frozenset[IntentType] = frozenset(
    {
        IntentType.INCOME_CHANGE,
        IntentType.PLANNED_LARGE_EXPENSE,
        IntentType.OBLIGATION_CHANGE,
        IntentType.FD_MATURITY,
        IntentType.EXPECTED_BONUS,
    }
)


# Sign convention per LLD 010 §Bridge "Amount sign convention" docstring.
_POSITIVE_TYPES: frozenset[IntentType] = frozenset(
    {
        IntentType.INCOME_CHANGE,
        IntentType.FD_MATURITY,
        IntentType.EXPECTED_BONUS,
    }
)
_NEGATIVE_TYPES: frozenset[IntentType] = frozenset(
    {
        IntentType.PLANNED_LARGE_EXPENSE,
        IntentType.OBLIGATION_CHANGE,
    }
)


# Default category buckets when the user did not specify one. These keep
# the bridge row valid against the scheduled_cashflows CHECK constraint
# without forcing a UX decision on the user.
_DEFAULT_BUCKET_BY_TYPE: dict[IntentType, str] = {
    IntentType.INCOME_CHANGE: "salary",
    IntentType.PLANNED_LARGE_EXPENSE: "other",
    IntentType.OBLIGATION_CHANGE: "emi_loan",
    IntentType.FD_MATURITY: "investment",
    IntentType.EXPECTED_BONUS: "salary",
}


def should_have_bridge_row(intent: UserIntent) -> bool:
    """Does this intent type get a ``scheduled_cashflows`` row at all?

    Type-only check — independent of ``is_active``. Soft-deleted intents
    (``is_active=False``) still keep their bridge row (mirrored to
    ``is_active=False``) so the audit + UI history continues to render
    cleanly. ``IntentsService`` owns the ``is_active`` mirroring.

    LIFE_EVENT and SAVINGS_GOAL always return ``False``.
    """
    return intent.intent_type in DATED_INTENT_TYPES


def _sign_for_type(intent_type: IntentType) -> int:
    if intent_type in _POSITIVE_TYPES:
        return 1
    if intent_type in _NEGATIVE_TYPES:
        return -1
    # LIFE_EVENT / SAVINGS_GOAL never reach here (caller gates on
    # should_have_bridge_row), but default to negative as a safety net.
    return -1


def _default_bucket_for_type(intent_type: IntentType) -> str:
    return _DEFAULT_BUCKET_BY_TYPE.get(intent_type, "other")


def intent_to_scheduled_cashflow_row(intent: UserIntent) -> dict[str, Any]:
    """Translate a dated ``UserIntent`` into a ``scheduled_cashflows`` row.

    Amount is confidence-weighted. ``LOW`` confidence → 0.0 amount (the
    row is still written so the widener can fire on the intent's
    presence; the row contributes 0 to the TFT covariate).

    Never call this for LIFE_EVENT or SAVINGS_GOAL — gate on
    :func:`should_have_bridge_row` first. Calling it on a non-dated
    intent will produce a row with the wrong sign assumption.

    Returns:
        A dict matching the ``scheduled_cashflows`` row shape, ready
        for handoff to the ``upsert_intent_with_bridge`` RPC.
    """
    weight = CONFIDENCE_COVARIATE_WEIGHT[intent.confidence]
    raw_amount = intent.amount if intent.amount is not None else abs(intent.amount_delta or 0.0)
    signed_amount = float(_sign_for_type(intent.intent_type)) * float(raw_amount) * weight

    return {
        "user_id": intent.user_id,
        # Sentinel merchant so the heuristic recurrence detector ignores
        # this row when it scans the table for collisions.
        "merchant": f"intent:{intent.id}",
        "amount": signed_amount,
        "category_bucket": intent.category_bucket or _default_bucket_for_type(intent.intent_type),
        "rrule_freq": intent.rrule_freq or "monthly",
        "next_occurrence": intent.start_date,
        "end_date": intent.end_date,
        # scheduled_cashflows.confidence is recurrence regularity, not
        # user-intent confidence — the user asserted this rule, so
        # regularity = 1.0.
        "confidence": 1.0,
        "source": "intent",
        "is_active": intent.is_active,
    }
