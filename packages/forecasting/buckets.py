"""RFC-005 fixed 12-bucket category taxonomy.

Extracted into its own module to break the circular import between
``packages.forecasting.scheduler`` (consumer of the bucket list) and
``packages.forecasting.category_mapping`` (mapping classifier labels to
buckets, also a consumer).

The 12-bucket taxonomy is the v1 ML contract — additions / removals
require a coordinated migration (mapping-table update + dashboard
revisions). See RFC-005 §1 for the rationale.
"""

from __future__ import annotations

CATEGORY_BUCKETS: tuple[str, ...] = (
    "salary",
    "rent",
    "groceries",
    "dining",
    "transport",
    "utilities",
    "entertainment",
    "health",
    "emi_loan",
    "investment",
    "transfer",
    "other",
)


# Buckets whose typical transactions are inflows (positive amounts).
# Used by the panel aggregator to apply the signed-amount convention
# (+ for income, - for spend) and by the scheduler when projecting
# scheduled events.
INCOME_BUCKETS: frozenset[str] = frozenset({"salary"})
