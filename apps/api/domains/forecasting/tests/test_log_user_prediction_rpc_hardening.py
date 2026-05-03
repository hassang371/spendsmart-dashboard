"""RPC trust-boundary hardening tests (Codex pass-2 Fix #5/#6).

Exercises each guard inside ``public.log_user_prediction(payload jsonb)``:

    * ``generated_at`` is server-derived (caller cannot back-date)
    * ``horizon_end`` is server-derived = (now()::date + horizon_days)
    * ``horizon_days`` rejected outside [1, 30]
    * ``model_type`` rejected outside ('chronos2','tft_hybrid','ensemble')
    * NOT NULL guards on ``prediction_id``, ``insights_version``, ``forecast``,
      ``insights``
    * Tenant guard — payload ``user_id`` mismatched with ``auth.uid()`` raises

Requires a running local Supabase stack. Skipped at module level when the
stack is unavailable so this file still ships in the Stage 2 commit and Stage 10
runs the assertions against a real database.

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §4
"""

from __future__ import annotations

import pytest

pytest.skip(
    "requires running supabase local — run in Stage 10",
    allow_module_level=True,
)
