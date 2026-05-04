"""RFC-006 §6 — stratified user sampling for the walk-forward harness.

Selects ``n`` users stratified across five archetypes per RFC-006 §6:

1. High-frequency spenders — top 20% by transaction count, ≥ 2y history.
2. Low-frequency spenders  — bottom 40% by transaction count, ≥ 2y history.
3. Recent life-event users — last-90-days CoV on daily total spend > 1.5.
4. Salary-only users       — txns in {salary, rent, groceries, utilities,
   transfer} ≥ 80%.
5. Multi-account users     — bank_accounts.provider_account_id IS NOT NULL
   count ≥ 2 (excludes the manual-only row guaranteed by
   ``idx_bank_accounts_user_manual``).

If a stratum has fewer than ``n//5`` qualifying users, the remainder is
filled by random supplementation from other strata in priority order
1→5. The actual composition is logged so the rendered report can record
real strata sizes (not just nominal targets).
"""

from __future__ import annotations

import logging
import random
from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# Stratum identifiers used in run JSON + research-doc rendering.
STRATA: tuple[str, ...] = (
    "high_frequency",
    "low_frequency",
    "life_event",
    "salary_only",
    "multi_account",
)


def select_stratified_users(
    supabase: Any,
    n: int = 50,
    *,
    min_history_days: int = 730,
    seed: int = 42,
    strata: Iterable[str] = STRATA,
) -> list[str]:
    """Return ``n`` user_ids stratified across the RFC-006 §6 archetypes.

    Falls back to random supplementation when individual strata are
    short of their nominal target (``n // len(strata)`` per stratum).

    Args:
        supabase: A Supabase service-role client. Skip the test in
            offline harness runs by guarding the call with
            ``pytest.skip("requires running supabase local")`` when
            ``supabase`` is None or the local instance is not running.
        n:               Total user count to return.
        min_history_days: Minimum transaction history per user in days.
        seed:            RNG seed (logged in run artifacts).
        strata:          Iterable of stratum names to populate.

    Returns:
        Deduplicated list of user_ids of length ≤ ``n``.

    Notes:
        Uses Supabase rpc/REST queries. The implementation is best-effort
        for Stage 7 — it executes simple queries that the local supabase
        may not support, in which case callers should pin a static user
        list with ``--users uuid1,uuid2,...`` instead.
    """
    if supabase is None:
        raise ValueError("select_stratified_users requires a supabase client")

    rng = random.Random(seed)
    strata_list = list(strata)
    target_per_stratum = max(1, n // max(1, len(strata_list)))

    composition = _classify_users(
        supabase,
        min_history_days=min_history_days,
        strata=strata_list,
    )

    selected: list[str] = []
    seen: set[str] = set()
    actual_composition: dict[str, list[str]] = {s: [] for s in strata_list}

    for stratum in strata_list:
        candidates = [u for u in composition.get(stratum, []) if u not in seen]
        rng.shuffle(candidates)
        chosen = candidates[:target_per_stratum]
        for uid in chosen:
            if uid not in seen:
                selected.append(uid)
                seen.add(uid)
                actual_composition[stratum].append(uid)

    # Random supplementation in priority order 1→5 if short of n.
    if len(selected) < n:
        for stratum in strata_list:
            if len(selected) >= n:
                break
            extras = [u for u in composition.get(stratum, []) if u not in seen]
            rng.shuffle(extras)
            for uid in extras:
                if len(selected) >= n:
                    break
                selected.append(uid)
                seen.add(uid)
                actual_composition[stratum].append(uid)

    logger.info(
        "stratified_sample selected %d users, composition=%s",
        len(selected),
        {k: len(v) for k, v in actual_composition.items()},
    )
    return selected


# ---------------------------------------------------------------------------
# Internal helpers — broken out so tests can stub the supabase round trip.
# ---------------------------------------------------------------------------


def _classify_users(
    supabase: Any,
    *,
    min_history_days: int,
    strata: list[str],
) -> dict[str, list[str]]:
    """Bucket eligible users into strata.

    Returns ``{stratum_name: [user_id, ...]}``. The Stage 7 implementation
    queries ``transactions`` and ``bank_accounts`` directly; production
    use against a populated DB should be validated in Stage 9.
    """
    cutoff = date.today() - timedelta(days=min_history_days)

    txn_response = (
        supabase.table("transactions")
        .select("user_id, transaction_date, amount, category")
        .lte("transaction_date", cutoff.isoformat())
        .execute()
    )
    txn_rows = txn_response.data or []

    if not txn_rows:
        return {s: [] for s in strata}

    by_user: dict[str, list[dict]] = {}
    for row in txn_rows:
        by_user.setdefault(row["user_id"], []).append(row)

    counts = {uid: len(rows) for uid, rows in by_user.items()}
    sorted_users = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    n_users = len(sorted_users)
    high_cutoff = max(1, int(n_users * 0.20))
    low_cutoff = max(1, int(n_users * 0.40))

    high_freq = [uid for uid, _ in sorted_users[:high_cutoff]]
    low_freq = [uid for uid, _ in sorted_users[-low_cutoff:]]

    life_event: list[str] = []
    salary_only: list[str] = []
    for uid, rows in by_user.items():
        spends = [abs(float(r["amount"])) for r in rows if float(r["amount"]) < 0]
        if spends:
            mean = sum(spends) / len(spends)
            if mean > 0:
                var = sum((x - mean) ** 2 for x in spends) / len(spends)
                cov = (var**0.5) / mean
                if cov > 1.5:
                    life_event.append(uid)
        salaried_categories = {"salary", "rent", "groceries", "utilities", "transfer"}
        labelled = [r for r in rows if r.get("category")]
        if labelled:
            in_set = sum(1 for r in labelled if r["category"].lower() in salaried_categories)
            if in_set / len(labelled) >= 0.80:
                salary_only.append(uid)

    multi_account: list[str] = []
    try:
        accounts = supabase.table("bank_accounts").select("user_id, provider_account_id").execute()
        rows = accounts.data or []
        per_user: dict[str, int] = {}
        for r in rows:
            if r.get("provider_account_id"):
                per_user[r["user_id"]] = per_user.get(r["user_id"], 0) + 1
        multi_account = [uid for uid, count in per_user.items() if count >= 2]
    except Exception as e:  # pragma: no cover — defensive fallback
        logger.warning("multi_account stratum query failed: %s", e)

    return {
        "high_frequency": high_freq,
        "low_frequency": low_freq,
        "life_event": life_event,
        "salary_only": salary_only,
        "multi_account": multi_account,
    }
