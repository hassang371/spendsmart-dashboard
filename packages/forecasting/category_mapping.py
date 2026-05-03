"""Maps MiniLM v2 classifier labels to the fixed 12-bucket taxonomy.

Stability contract: ``CATEGORY_BUCKETS`` (in ``buckets.py``) is the ML
contract. The classifier's emitted labels (the ``Category`` enum from
``packages/categorization/constants.py``) may evolve over time; this
module absorbs that churn behind a single mapping table.

Every value of the ``Category`` enum MUST appear as a key in
``CLASSIFIER_LABEL_TO_BUCKET``. This is asserted by the
``test_every_classifier_label_maps`` test. Adding a new ``Category``
value without adding a mapping entry will fail CI.

Per RFC-005 §1 H1, the routing decisions are:
    - ``Insurance``        → ``"other"``  (signal-loss accepted v1)
    - ``Taxes``            → ``"other"``  (signal-loss accepted v1)
    - ``Bank Fees``        → ``"other"``  (signal-loss accepted v1)
    - ``Home Maintenance`` → ``"other"``  (signal-loss accepted v1)

Re-evaluate in v1.5 once real data shows whether a 13th
``fees_and_taxes`` bucket would be worth the additional taxonomy
surface area.
"""

from __future__ import annotations

from packages.categorization.constants import Category
from packages.forecasting.buckets import CATEGORY_BUCKETS

# Mapping from classifier label (Category.value) to one of the 12 buckets.
# Keys are case-sensitive matches of ``Category.value`` strings; the
# lookup helper applies a ``.strip().lower()`` normalisation against a
# parallel lower-cased index.
CLASSIFIER_LABEL_TO_BUCKET: dict[str, str] = {
    # ── Food & Dining ────────────────────────────────────────────────
    Category.FOOD.value: "dining",
    Category.GROCERIES.value: "groceries",
    Category.COFFEE_SNACKS.value: "dining",
    # ── Transport ────────────────────────────────────────────────────
    Category.TAXI_RIDESHARE.value: "transport",
    Category.PUBLIC_TRANSIT.value: "transport",
    Category.FLIGHTS.value: "transport",
    Category.FUEL.value: "transport",
    # ── Housing & Utilities ──────────────────────────────────────────
    Category.RENT_MORTGAGE.value: "rent",
    Category.ELECTRICITY_WATER.value: "utilities",
    Category.INTERNET_PHONE.value: "utilities",
    Category.HOME_MAINTENANCE.value: "other",  # RFC-005 §1 H1
    # ── Shopping ─────────────────────────────────────────────────────
    Category.CLOTHING_FASHION.value: "other",
    Category.ELECTRONICS.value: "other",
    Category.GENERAL_RETAIL.value: "other",
    # ── Entertainment ────────────────────────────────────────────────
    Category.SUBSCRIPTIONS.value: "entertainment",
    Category.MOVIES_EVENTS.value: "entertainment",
    Category.GAMING.value: "entertainment",
    # ── Health ───────────────────────────────────────────────────────
    Category.MEDICAL.value: "health",
    Category.PHARMACY.value: "health",
    Category.FITNESS.value: "health",
    # ── Finance ──────────────────────────────────────────────────────
    Category.INVESTMENTS.value: "investment",
    Category.INSURANCE.value: "other",  # RFC-005 §1 H1
    Category.LOAN_EMI.value: "emi_loan",
    Category.TAXES.value: "other",  # RFC-005 §1 H1
    Category.BANK_FEES.value: "other",  # RFC-005 §1 H1
    # ── Travel & Lodging ─────────────────────────────────────────────
    Category.HOTELS_STAYS.value: "other",
    Category.TRAVEL_BOOKING.value: "other",
    # ── People ───────────────────────────────────────────────────────
    Category.TRANSFERS_TO_PEOPLE.value: "transfer",
    Category.RECEIVED_FROM_PEOPLE.value: "transfer",
    # ── Income ───────────────────────────────────────────────────────
    Category.SALARY.value: "salary",
    Category.REFUNDS.value: "salary",
    Category.INTEREST.value: "salary",
    # ── Misc ─────────────────────────────────────────────────────────
    Category.UNCATEGORIZED.value: "other",
}


# Lower-cased lookup index used by the case-insensitive helper.
_LOWER_INDEX: dict[str, str] = {key.strip().lower(): value for key, value in CLASSIFIER_LABEL_TO_BUCKET.items()}


def map_classifier_label_to_bucket(label: str | None) -> str:
    """Return the bucket for a classifier label.

    Falls back to ``"other"`` for unknown labels. Case-insensitive;
    surrounding whitespace is stripped. ``None`` / empty string also
    fall through to ``"other"``.
    """
    if not label:
        return "other"
    return _LOWER_INDEX.get(label.strip().lower(), "other")


__all__ = [
    "CATEGORY_BUCKETS",
    "CLASSIFIER_LABEL_TO_BUCKET",
    "map_classifier_label_to_bucket",
]
