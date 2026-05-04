"""Schema-drift CI guardrail.

Regenerates the JSON-Schema bundle from the Pydantic models in
``apps.api.domains.forecasting.schemas`` and asserts equality with the
checked-in snapshot at ``apps/web/lib/api/forecast.schema.json``.

If this test fails, the backend Pydantic surface diverged from the
frontend's hand-written types — re-run the generator (see the failure
message) and commit the updated snapshot alongside any frontend type
changes.

Refs:
  docs/features/011-ai-insights-page.md §Scope
  docs/features/011-ai-insights-page.md §Testing Strategy → Contract tests
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from apps.api.domains.forecasting.schemas import (
    ForecastInsights,
    ForecastPoint,
    ForecastResponse,
    IntentCreateRequest,
    IntentUpdateRequest,
    ScenarioDelta,
    ScenarioRequest,
    ScenarioResponse,
    UserIntent,
)

# Repo root resolves four levels up: this file lives at
# apps/api/domains/forecasting/tests/test_frontend_schema_drift.py
_REPO_ROOT = Path(__file__).resolve().parents[5]
_SNAPSHOT_PATH = _REPO_ROOT / "apps" / "web" / "lib" / "api" / "forecast.schema.json"

# Order matters only for readability of the snapshot — sort_keys=True
# normalises the comparison anyway.
_SCHEMA_CLASSES: tuple[tuple[str, type], ...] = (
    ("ForecastResponse", ForecastResponse),
    ("UserIntent", UserIntent),
    ("IntentCreateRequest", IntentCreateRequest),
    ("IntentUpdateRequest", IntentUpdateRequest),
    ("ScenarioRequest", ScenarioRequest),
    ("ScenarioResponse", ScenarioResponse),
    ("ForecastInsights", ForecastInsights),
    ("ForecastPoint", ForecastPoint),
    ("ScenarioDelta", ScenarioDelta),
)


def _generate_bundle() -> dict[str, dict]:
    return {name: cls.model_json_schema() for name, cls in _SCHEMA_CLASSES}


_REGENERATE_INSTRUCTIONS = textwrap.dedent(
    """
    Frontend schema drift detected. Re-run the generator and commit the snapshot:

        .venv/bin/python -c "import json; from apps.api.domains.forecasting.schemas import (
            ForecastResponse, UserIntent, IntentCreateRequest, IntentUpdateRequest,
            ScenarioRequest, ScenarioResponse, ForecastInsights, ForecastPoint, ScenarioDelta,
        ); bundle = {name: cls.model_json_schema() for name, cls in [
            ('ForecastResponse', ForecastResponse),
            ('UserIntent', UserIntent),
            ('IntentCreateRequest', IntentCreateRequest),
            ('IntentUpdateRequest', IntentUpdateRequest),
            ('ScenarioRequest', ScenarioRequest),
            ('ScenarioResponse', ScenarioResponse),
            ('ForecastInsights', ForecastInsights),
            ('ForecastPoint', ForecastPoint),
            ('ScenarioDelta', ScenarioDelta),
        ]}; print(json.dumps(bundle, indent=2, sort_keys=True))" \\
            > apps/web/lib/api/forecast.schema.json

    AND review apps/web/lib/api/forecast.types.ts so the FE types stay aligned.
    """
).strip()


def test_snapshot_file_exists() -> None:
    assert _SNAPSHOT_PATH.is_file(), f"Missing snapshot {_SNAPSHOT_PATH}. {_REGENERATE_INSTRUCTIONS}"


def test_pydantic_schemas_match_committed_snapshot() -> None:
    fresh = _generate_bundle()
    committed = json.loads(_SNAPSHOT_PATH.read_text())

    if fresh == committed:
        return

    # Surface the first diverging top-level model + a sample diff hint.
    drift_models: list[str] = []
    for name in sorted(set(fresh) | set(committed)):
        if fresh.get(name) != committed.get(name):
            drift_models.append(name)

    pytest.fail("Pydantic ↔ forecast.schema.json drift in models: " f"{drift_models}\n\n{_REGENERATE_INSTRUCTIONS}")
