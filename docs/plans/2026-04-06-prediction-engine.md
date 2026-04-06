# Two-Tier Prediction Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-tier forecasting engine — Chronos-2 for zero-shot cold-start users, TFT-Hybrid for personalized established users — with proper API schemas, service layer, and training integration.

**Architecture:** Tier 1 (Chronos-2-Small, 28M params) provides immediate zero-shot forecasts for all users. Tier 2 (upgraded TFT via pytorch-forecasting) adds personalized, interpretable forecasts for users with 90+ days of history. A service layer routes between tiers and optionally ensembles both.

**Tech Stack:** Python 3.14, FastAPI, pytorch-forecasting, chronos-forecasting, PyTorch Lightning, Supabase, polling worker

**LLD:** `docs/features/009-prediction-engine.md`

---

## File Structure

```
packages/forecasting/
  dataset.py              # MODIFY — consolidate prepare_training_data here
  trainer.py              # MODIFY — remove duplicate, import from dataset, upgrade config
  tft_model.py            # MODIFY — upgrade hyperparameters
  inference.py            # MODIFY — add variable importance extraction
  chronos_engine.py       # CREATE — Chronos-2 zero-shot wrapper
  ensemble.py             # CREATE — weighted blending of TFT + Chronos-2
  augmentation.py         # CREATE — time-series data augmentation
  tests/
    test_chronos.py       # CREATE
    test_ensemble.py      # CREATE
    test_augmentation.py  # CREATE

apps/api/domains/forecasting/
  schemas.py              # CREATE (replace empty stub)
  service.py              # CREATE (replace empty stub)
  router.py               # MODIFY — thin delegation to service
  tests/
    test_schemas.py       # CREATE
    test_service.py       # CREATE

apps/worker/
  main.py                 # MODIFY — fix duplicate log lines
```

---

### Task 1: Consolidate `prepare_training_data` into `dataset.py`

**Why first:** Every downstream task imports from `dataset.py`. Fixing the duplication now prevents confusion.

**Files:**
- Modify: `packages/forecasting/dataset.py:162-171`
- Modify: `packages/forecasting/trainer.py:96-121`
- Test: `packages/forecasting/tests/test_dataset.py`

- [ ] **Step 1: Write failing test for consolidated `prepare_training_data` with payday detection**

Add to `packages/forecasting/tests/test_dataset.py`:

```python
def test_prepare_training_data_includes_payday_detection():
    """prepare_training_data should enrich with is_payday column."""
    import numpy as np

    dates = pd.date_range("2026-01-01", periods=100, freq="D")
    amounts = np.random.choice([-50, -20, -10, 1000], size=100)
    # Simulate payday on the 1st of each month
    for i, d in enumerate(dates):
        if d.day == 1:
            amounts[i] = 5000.0

    df = pd.DataFrame({"date": dates, "amount": amounts})
    result = prepare_training_data(df)

    assert "is_payday" in result.columns
    assert "time_idx" in result.columns
    assert "day_of_week" in result.columns
    assert "day_of_month" in result.columns
    assert "group_id" in result.columns
    assert len(result) == 100


def test_prepare_training_data_rejects_short_history():
    """prepare_training_data should raise ValueError if < 90 days."""
    import pytest

    from packages.forecasting.dataset import prepare_training_data

    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    amounts = [-50.0] * 30
    df = pd.DataFrame({"date": dates, "amount": amounts})

    with pytest.raises(ValueError, match="Insufficient data"):
        prepare_training_data(df, min_days=90)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/forecasting/tests/test_dataset.py::test_prepare_training_data_includes_payday_detection -v`
Expected: FAIL (current `prepare_training_data` in `dataset.py` doesn't have payday detection or `min_days` param)

- [ ] **Step 3: Consolidate `prepare_training_data` in `dataset.py`**

Replace `packages/forecasting/dataset.py` lines 162-171 with the full version that includes payday detection, min_days validation, and month feature:

```python
def prepare_training_data(
    transactions: pd.DataFrame,
    start_date=None,
    end_date=None,
    min_days: int = 0,
) -> pd.DataFrame:
    """Canonical data preparation: aggregate -> validate -> payday detect -> enrich.

    Args:
        transactions: Raw transactions with 'date' and 'amount' columns.
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        min_days: Minimum required days of history. 0 = no check.

    Returns:
        Enriched DataFrame ready for TFT training/inference.

    Raises:
        ValueError: If history is shorter than min_days.
    """
    loader = TransactionLoader(transactions)
    daily_df = loader.aggregate_daily(start_date=start_date, end_date=end_date)

    if min_days > 0 and len(daily_df) < min_days:
        raise ValueError(
            f"Insufficient data: {len(daily_df)} days available, "
            f"but the model requires at least {min_days}. "
            f"Please upload more transaction history."
        )

    # Payday detection (from trainer.py)
    daily_df["is_payday"] = _detect_paydays(daily_df)

    # Standard enrichment
    enriched = loader.enrich_features(daily_df)

    # Ensure is_payday is a string categorical (required by TFT)
    enriched["is_payday"] = enriched["is_payday"].astype(str).astype("category")

    return enriched


def _detect_paydays(daily_df: pd.DataFrame, threshold_percentile: float = 90) -> pd.Series:
    """Detect payday pattern: days with income above the 90th percentile
    that recur on a similar day_of_month across >=2 months.

    Returns an integer Series (0/1) aligned with daily_df index.
    """
    if "daily_income" not in daily_df.columns:
        return pd.Series(0, index=daily_df.index)

    income = daily_df["daily_income"]
    positive_income = income[income > 0]

    if positive_income.empty:
        return pd.Series(0, index=daily_df.index)

    threshold = positive_income.quantile(threshold_percentile / 100)
    large_deposit = income >= threshold

    if isinstance(daily_df.index, pd.DatetimeIndex):
        dom = daily_df.index.day
    elif "date" in daily_df.columns:
        dom = pd.to_datetime(daily_df["date"]).dt.day
    else:
        return large_deposit.astype(int)

    payday_days = []
    for day in dom[large_deposit].unique():
        if large_deposit[dom == day].sum() >= 2:
            payday_days.append(day)

    return pd.Series(dom.isin(payday_days).astype(int), index=daily_df.index)
```

- [ ] **Step 4: Update `trainer.py` to import from `dataset.py`**

In `packages/forecasting/trainer.py`, remove the `detect_paydays` function (lines 35-69) and the `prepare_training_data` function (lines 96-121). Update imports:

```python
from packages.forecasting.dataset import (
    TransactionLoader,
    create_timeseries_dataset,
    prepare_training_data,
)
```

Update `trainer.py`'s internal callers: the `prepare_training_data` call at line 102 in `trainer.py` is now the one from `dataset.py` with `min_days=MINIMUM_DAYS`.

- [ ] **Step 5: Run all forecasting tests**

Run: `.venv/bin/python -m pytest packages/forecasting/tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add packages/forecasting/dataset.py packages/forecasting/trainer.py packages/forecasting/tests/test_dataset.py
git commit -m "refactor: consolidate prepare_training_data into dataset.py

Removes duplication between dataset.py and trainer.py. The canonical
prepare_training_data now lives in dataset.py with payday detection,
min_days validation, and month feature support.

Refs: docs/features/009-prediction-engine.md"
```

---

### Task 1.5: Update `inference.py` and `test_trainer.py` imports after consolidation

**Why:** Task 1 moved `prepare_training_data` and `detect_paydays` to `dataset.py`. Files that import from `trainer.py` must be updated or they'll break.

**Files:**
- Modify: `packages/forecasting/inference.py:16-19`
- Modify: `packages/forecasting/tests/test_trainer.py:4-7`

- [ ] **Step 1: Update `inference.py` imports**

In `packages/forecasting/inference.py`, change lines 16-19 from:

```python
from packages.forecasting.trainer import (
    MAX_ENCODER_LENGTH,
    prepare_training_data,
)
```

To:

```python
from packages.forecasting.dataset import prepare_training_data
from packages.forecasting.trainer import MAX_ENCODER_LENGTH
```

- [ ] **Step 2: Add `extract_variable_importance` to `inference.py`**

Add to `packages/forecasting/inference.py`:

```python
def extract_variable_importance(
    model: TemporalFusionTransformer,
    df: pd.DataFrame,
) -> list[dict[str, float]] | None:
    """Extract variable importance from TFT model using interpret_output.

    Returns list of {"feature": name, "weight": float} or None on failure.
    """
    try:
        history_df = prepare_training_data(df)
        if len(history_df) < MAX_ENCODER_LENGTH:
            return None

        # Rebuild reference dataset from model's saved parameters
        params = model.dataset_parameters
        from packages.forecasting.dataset import create_timeseries_dataset

        reference_ds = create_timeseries_dataset(
            history_df,
            max_encoder_length=params.get("max_encoder_length", MAX_ENCODER_LENGTH),
            max_prediction_length=params.get("max_prediction_length", 30),
        )
        pred_dl = reference_ds.to_dataloader(train=False, batch_size=64, num_workers=0)

        raw_predictions = model.predict(pred_dl, mode="raw", return_x=True)
        interpretation = model.interpret_output(raw_predictions, reduction="sum")

        weights = interpretation.get("encoder_variables", {})
        return [
            {"feature": k, "weight": round(float(v), 4)}
            for k, v in weights.items()
        ]
    except Exception as e:
        logger.warning(f"Variable importance extraction failed: {e}")
        return None
```

- [ ] **Step 3: Update `test_trainer.py` imports**

In `packages/forecasting/tests/test_trainer.py`, change lines 4-7 from:

```python
from packages.forecasting.trainer import (
    detect_paydays,
    prepare_training_data,
)
```

To:

```python
from packages.forecasting.dataset import _detect_paydays as detect_paydays
from packages.forecasting.dataset import prepare_training_data
```

- [ ] **Step 4: Run all forecasting tests**

Run: `.venv/bin/python -m pytest packages/forecasting/tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/forecasting/inference.py packages/forecasting/tests/test_trainer.py
git commit -m "refactor: update imports after prepare_training_data consolidation

Updates inference.py and test_trainer.py to import from dataset.py
instead of trainer.py. Adds extract_variable_importance() to
inference.py using proper DataLoader construction.

Refs: docs/features/009-prediction-engine.md"
```

---

### Task 2: Upgrade TFT model hyperparameters

**Files:**
- Modify: `packages/forecasting/tft_model.py`
- Test: `packages/forecasting/tests/test_model.py`

- [ ] **Step 1: Write failing test for upgraded model dimensions**

Add to `packages/forecasting/tests/test_model.py`:

```python
def test_create_tft_model_upgraded_defaults():
    """Model should use upgraded defaults: hidden=64, heads=4, lstm=2."""
    from packages.forecasting.tft_model import create_tft_model
    from packages.forecasting.tests.conftest import make_dummy_dataset

    dataset = make_dummy_dataset()
    model = create_tft_model(dataset)

    assert model.hparams.hidden_size == 64
    assert model.hparams.attention_head_size == 4
    assert model.hparams.lstm_layers == 2
    assert model.hparams.hidden_continuous_size == 32
```

Also create `packages/forecasting/tests/conftest.py` if it doesn't exist, with a shared helper:

```python
import numpy as np
import pandas as pd
from pytorch_forecasting import TimeSeriesDataSet


def make_dummy_dataset(n_days=120):
    """Create a minimal TimeSeriesDataSet for testing."""
    dates = pd.date_range("2025-01-01", periods=n_days, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "time_idx": range(n_days),
        "group_id": "test_user",
        "daily_spend": np.random.uniform(10, 100, n_days),
        "daily_income": np.random.uniform(0, 50, n_days),
        "closing_balance": np.cumsum(np.random.uniform(-20, 30, n_days)),
        "day_of_week": [str(d.dayofweek) for d in dates],
        "day_of_month": [str(d.day) for d in dates],
        "is_payday": ["0"] * n_days,
    })
    for col in ["day_of_week", "day_of_month", "is_payday"]:
        df[col] = df[col].astype("category")

    return TimeSeriesDataSet(
        df,
        time_idx="time_idx",
        target="closing_balance",
        group_ids=["group_id"],
        max_encoder_length=60,
        max_prediction_length=30,
        min_encoder_length=30,
        min_prediction_length=1,
        static_categoricals=["group_id"],
        time_varying_known_categoricals=["day_of_week", "day_of_month", "is_payday"],
        time_varying_known_reals=["time_idx", "daily_income", "daily_spend"],
        time_varying_unknown_reals=["closing_balance"],
        add_relative_time_idx=True,
        add_target_scales=True,
        add_encoder_length=True,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/forecasting/tests/test_model.py::test_create_tft_model_upgraded_defaults -v`
Expected: FAIL (current defaults are hidden_size=16, attention_head_size=1, etc.)

- [ ] **Step 3: Update `tft_model.py` defaults**

Replace `packages/forecasting/tft_model.py`:

```python
from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet
from pytorch_forecasting.metrics import QuantileLoss


def create_tft_model(
    training_dataset: TimeSeriesDataSet,
    learning_rate=3e-4,
    hidden_size=64,
    attention_head_size=4,
    dropout=0.1,
    hidden_continuous_size=32,
    lstm_layers=2,
):
    """Creates a TemporalFusionTransformer model from the training dataset."""
    tft = TemporalFusionTransformer.from_dataset(
        training_dataset,
        learning_rate=learning_rate,
        hidden_size=hidden_size,
        attention_head_size=attention_head_size,
        dropout=dropout,
        hidden_continuous_size=hidden_continuous_size,
        output_size=7,  # 7 quantiles: [0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98]
        loss=QuantileLoss(),
        log_interval=10,
        reduce_on_plateau_patience=4,
        lstm_layers=lstm_layers,
    )
    return tft
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest packages/forecasting/tests/test_model.py -v`
Expected: ALL PASS

- [ ] **Step 5: Update `trainer.py` gradient clip and learning rate**

In `packages/forecasting/trainer.py`, update `run_training`:
- Change `gradient_clip_val=0.1` to `gradient_clip_val=1.0`
- Change `learning_rate=0.01` in `create_tft_model(training_dataset, learning_rate=0.01)` to `learning_rate=3e-4`

- [ ] **Step 6: Run all forecasting tests**

Run: `.venv/bin/python -m pytest packages/forecasting/tests/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add packages/forecasting/tft_model.py packages/forecasting/trainer.py packages/forecasting/tests/
git commit -m "refactor: upgrade TFT model hyperparameters

hidden_size 16->64, attention_heads 1->4, lstm_layers 1->2,
hidden_continuous_size 8->32, learning_rate 0.01->3e-4,
gradient_clip_val 0.1->1.0. Based on research analysis.

Refs: docs/features/009-prediction-engine.md"
```

---

### Task 3: Create `chronos_engine.py` — Chronos-2 zero-shot wrapper

**Files:**
- Create: `packages/forecasting/chronos_engine.py`
- Create: `packages/forecasting/tests/test_chronos.py`

- [ ] **Step 1: Add `chronos-forecasting` to requirements**

Append to `packages/forecasting/requirements.txt`:

```
chronos-forecasting>=1.3,<2.0
```

- [ ] **Step 2: Write failing tests**

Create `packages/forecasting/tests/test_chronos.py`:

```python
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import torch


def _make_daily_df(n_days=60):
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    return pd.DataFrame({
        "date": dates,
        "daily_spend": np.random.uniform(10, 100, n_days),
        "daily_income": np.random.uniform(0, 200, n_days),
        "closing_balance": np.cumsum(np.random.uniform(-20, 30, n_days)),
    })


class TestChronosEngine:
    def test_predict_returns_correct_shape(self):
        """Predict should return a dict with 'forecast' list of length=horizon."""
        from packages.forecasting.chronos_engine import ChronosEngine

        # Mock the pipeline to avoid downloading the real model
        with patch("packages.forecasting.chronos_engine.ChronosPipeline") as MockPipeline:
            mock_instance = MagicMock()
            # Simulate predict output: [1, num_samples, horizon]
            mock_instance.predict.return_value = torch.randn(1, 100, 30).abs()
            MockPipeline.from_pretrained.return_value = mock_instance

            engine = ChronosEngine(model_name="mock-model")
            result = engine.predict(_make_daily_df(), horizon=30)

        assert "forecast" in result
        assert len(result["forecast"]) == 30
        assert result["model_type"] == "chronos2"
        assert result["horizon"] == 30

    def test_predict_quantile_ordering(self):
        """P10 <= P50 <= P90 for every forecast point."""
        from packages.forecasting.chronos_engine import ChronosEngine

        with patch("packages.forecasting.chronos_engine.ChronosPipeline") as MockPipeline:
            mock_instance = MagicMock()
            # Use sorted samples so quantiles are ordered
            samples = torch.sort(torch.randn(1, 100, 30).abs(), dim=1).values
            mock_instance.predict.return_value = samples
            MockPipeline.from_pretrained.return_value = mock_instance

            engine = ChronosEngine(model_name="mock-model")
            result = engine.predict(_make_daily_df(), horizon=30)

        for point in result["forecast"]:
            assert point["p10"] <= point["p50"], f"p10 > p50 on {point['date']}"
            assert point["p50"] <= point["p90"], f"p50 > p90 on {point['date']}"

    def test_predict_empty_df_raises(self):
        """Empty DataFrame should raise ValueError."""
        from packages.forecasting.chronos_engine import ChronosEngine

        with patch("packages.forecasting.chronos_engine.ChronosPipeline") as MockPipeline:
            MockPipeline.from_pretrained.return_value = MagicMock()
            engine = ChronosEngine(model_name="mock-model")

            with pytest.raises(ValueError, match="No transaction data"):
                engine.predict(pd.DataFrame(), horizon=30)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest packages/forecasting/tests/test_chronos.py -v`
Expected: FAIL (module does not exist)

- [ ] **Step 4: Implement `chronos_engine.py`**

Create `packages/forecasting/chronos_engine.py`:

```python
"""Chronos-2 zero-shot forecasting engine.

Provides immediate probabilistic forecasts for users without trained
TFT models (cold-start). Uses Amazon Chronos-2-Small (28M params).
"""

import logging
from typing import Any

import pandas as pd
import torch

from chronos import ChronosPipeline

logger = logging.getLogger(__name__)

# Singleton engine: loaded once, reused across requests
_ENGINE: "ChronosEngine | None" = None


class ChronosEngine:
    """Zero-shot forecasting via Amazon Chronos-2."""

    def __init__(self, model_name: str = "amazon/chronos-2-small", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._pipeline: ChronosPipeline | None = None

    @property
    def pipeline(self) -> ChronosPipeline:
        if self._pipeline is None:
            logger.info(f"Loading Chronos model: {self.model_name}")
            self._pipeline = ChronosPipeline.from_pretrained(
                self.model_name, device_map=self.device
            )
        return self._pipeline

    def predict(
        self,
        daily_df: pd.DataFrame,
        horizon: int = 30,
        num_samples: int = 100,
    ) -> dict[str, Any]:
        """Run zero-shot probabilistic forecast.

        Args:
            daily_df: DataFrame with at least a 'closing_balance' column
                      and a 'date' column (or DatetimeIndex).
            horizon: Number of days to predict.
            num_samples: Monte Carlo samples for quantile estimation.

        Returns:
            Dict with 'forecast' list of {date, p10, p50, p90} per day,
            plus 'model_type', 'model_version', 'horizon'.
        """
        if daily_df.empty or "closing_balance" not in daily_df.columns:
            raise ValueError("No transaction data available for forecasting")

        context = torch.tensor(
            daily_df["closing_balance"].values, dtype=torch.float32
        ).unsqueeze(0)  # shape: [1, seq_len]

        samples = self.pipeline.predict(
            context, prediction_length=horizon, num_samples=num_samples
        )
        # samples shape: [1, num_samples, horizon]

        quantiles = torch.quantile(
            samples[0].float(),
            torch.tensor([0.1, 0.5, 0.9]),
            dim=0,
        )
        # quantiles shape: [3, horizon]

        # Determine future dates
        if "date" in daily_df.columns:
            last_date = pd.to_datetime(daily_df["date"]).max()
        elif isinstance(daily_df.index, pd.DatetimeIndex):
            last_date = daily_df.index.max()
        else:
            last_date = pd.Timestamp.now()

        future_dates = pd.date_range(
            start=last_date + pd.Timedelta(days=1), periods=horizon, freq="D"
        )

        forecast = []
        for i in range(horizon):
            forecast.append({
                "date": future_dates[i].strftime("%Y-%m-%d"),
                "p10": round(float(quantiles[0, i]), 2),
                "p50": round(float(quantiles[1, i]), 2),
                "p90": round(float(quantiles[2, i]), 2),
            })

        return {
            "forecast": forecast,
            "model_type": "chronos2",
            "model_version": "chronos-2-small",
            "horizon": horizon,
        }


def get_chronos_engine() -> ChronosEngine:
    """Returns a singleton ChronosEngine instance."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = ChronosEngine()
    return _ENGINE
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest packages/forecasting/tests/test_chronos.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add packages/forecasting/chronos_engine.py packages/forecasting/tests/test_chronos.py packages/forecasting/requirements.txt
git commit -m "feat: add Chronos-2 zero-shot forecasting engine

Wraps Amazon Chronos-2-Small (28M params) for immediate probabilistic
forecasts. Singleton pattern for model loading. Returns P10/P50/P90
quantiles for 30-day horizon.

Refs: docs/features/009-prediction-engine.md"
```

---

### Task 4: Create `ensemble.py` — weighted blending

**Files:**
- Create: `packages/forecasting/ensemble.py`
- Create: `packages/forecasting/tests/test_ensemble.py`

- [ ] **Step 1: Write failing tests**

Create `packages/forecasting/tests/test_ensemble.py`:

```python
import pytest

from packages.forecasting.ensemble import ensemble_forecasts


def _make_forecast(offset=0.0):
    return {
        "forecast": [
            {"date": "2026-04-07", "p10": 100 + offset, "p50": 200 + offset, "p90": 300 + offset},
            {"date": "2026-04-08", "p10": 110 + offset, "p50": 210 + offset, "p90": 310 + offset},
        ],
        "model_type": "test",
        "model_version": "v1",
        "horizon": 2,
    }


def test_ensemble_blends_at_configured_weights():
    tft = _make_forecast(0.0)  # p50: [200, 210]
    chronos = _make_forecast(100.0)  # p50: [300, 310]

    result = ensemble_forecasts(tft, chronos, tft_weight=0.7, chronos_weight=0.3)

    # 0.7 * 200 + 0.3 * 300 = 140 + 90 = 230
    assert result["forecast"][0]["p50"] == pytest.approx(230.0, abs=0.01)
    assert result["model_type"] == "ensemble"


def test_ensemble_handles_missing_tft():
    chronos = _make_forecast(100.0)
    result = ensemble_forecasts(None, chronos, tft_weight=0.7, chronos_weight=0.3)

    assert result["forecast"][0]["p50"] == pytest.approx(300.0, abs=0.01)
    assert result["model_type"] == "chronos2"


def test_ensemble_requires_matching_horizons():
    tft = _make_forecast()
    chronos = {"forecast": [{"date": "2026-04-07", "p10": 1, "p50": 2, "p90": 3}], "model_type": "c", "model_version": "v", "horizon": 1}

    with pytest.raises(ValueError, match="horizon"):
        ensemble_forecasts(tft, chronos)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest packages/forecasting/tests/test_ensemble.py -v`
Expected: FAIL (module does not exist)

- [ ] **Step 3: Implement `ensemble.py`**

Create `packages/forecasting/ensemble.py`:

```python
"""Weighted ensemble of TFT and Chronos-2 forecasts."""

from typing import Any


def ensemble_forecasts(
    tft_result: dict[str, Any] | None,
    chronos_result: dict[str, Any],
    tft_weight: float = 0.7,
    chronos_weight: float = 0.3,
) -> dict[str, Any]:
    """Blend TFT and Chronos-2 forecasts with configurable weights.

    If tft_result is None, returns chronos_result unchanged.
    """
    if tft_result is None:
        return chronos_result

    tft_fc = tft_result["forecast"]
    chr_fc = chronos_result["forecast"]

    if len(tft_fc) != len(chr_fc):
        raise ValueError(
            f"Forecast horizon mismatch: TFT={len(tft_fc)}, Chronos={len(chr_fc)}"
        )

    blended = []
    for t, c in zip(tft_fc, chr_fc):
        blended.append({
            "date": t["date"],
            "p10": round(tft_weight * t["p10"] + chronos_weight * c["p10"], 2),
            "p50": round(tft_weight * t["p50"] + chronos_weight * c["p50"], 2),
            "p90": round(tft_weight * t["p90"] + chronos_weight * c["p90"], 2),
        })

    return {
        "forecast": blended,
        "model_type": "ensemble",
        "model_version": f"tft({tft_weight})+chronos({chronos_weight})",
        "horizon": len(blended),
    }
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest packages/forecasting/tests/test_ensemble.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/forecasting/ensemble.py packages/forecasting/tests/test_ensemble.py
git commit -m "feat: add weighted ensemble for TFT + Chronos-2 blending

Blends quantile forecasts at configurable weights (default 70/30).
Falls back to Chronos-only when TFT result is None.

Refs: docs/features/009-prediction-engine.md"
```

---

### Task 5: Create `augmentation.py` — time-series data augmentation

**Files:**
- Create: `packages/forecasting/augmentation.py`
- Create: `packages/forecasting/tests/test_augmentation.py`

- [ ] **Step 1: Write failing tests**

Create `packages/forecasting/tests/test_augmentation.py`:

```python
import numpy as np
import pandas as pd
import pytest

from packages.forecasting.augmentation import jitter, scale, magnitude_warp


def _make_series(n=100):
    return pd.Series(np.random.uniform(10, 100, n))


def test_jitter_preserves_shape():
    s = _make_series()
    result = jitter(s, sigma=0.02)
    assert len(result) == len(s)


def test_jitter_adds_noise():
    s = _make_series()
    result = jitter(s, sigma=0.05)
    assert not np.allclose(result.values, s.values)


def test_scale_preserves_shape():
    s = _make_series()
    result = scale(s, low=0.8, high=1.2)
    assert len(result) == len(s)


def test_scale_changes_magnitude():
    np.random.seed(42)
    s = pd.Series([100.0] * 50)
    result = scale(s, low=0.5, high=0.5)  # deterministic scaling
    assert np.allclose(result.values, 50.0)


def test_magnitude_warp_preserves_shape():
    s = _make_series()
    result = magnitude_warp(s, sigma=0.1, knots=4)
    assert len(result) == len(s)


def test_magnitude_warp_is_smooth():
    """Warped series should not have sudden jumps relative to original."""
    s = pd.Series([100.0] * 100)
    result = magnitude_warp(s, sigma=0.1, knots=4)
    diffs = np.abs(np.diff(result.values))
    assert np.max(diffs) < 20, "Magnitude warp should produce smooth changes"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest packages/forecasting/tests/test_augmentation.py -v`
Expected: FAIL (module does not exist)

- [ ] **Step 3: Implement `augmentation.py`**

Create `packages/forecasting/augmentation.py`:

```python
"""Time-series data augmentation for financial forecasting.

All functions take a pd.Series and return a pd.Series of the same length.
Temporal order is always preserved.
"""

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline


def jitter(series: pd.Series, sigma: float = 0.02) -> pd.Series:
    """Add Gaussian noise scaled to the series standard deviation."""
    noise = np.random.normal(0, sigma * series.std(), size=len(series))
    return pd.Series(series.values + noise, index=series.index)


def scale(series: pd.Series, low: float = 0.8, high: float = 1.2) -> pd.Series:
    """Multiply entire series by a random factor in [low, high]."""
    factor = np.random.uniform(low, high)
    return pd.Series(series.values * factor, index=series.index)


def magnitude_warp(
    series: pd.Series, sigma: float = 0.1, knots: int = 4
) -> pd.Series:
    """Multiply by a smooth cubic spline curve to vary magnitude over time."""
    n = len(series)
    knot_positions = np.linspace(0, n - 1, knots + 2)
    knot_values = np.random.normal(1.0, sigma, size=knots + 2)
    spline = CubicSpline(knot_positions, knot_values)
    warp_curve = spline(np.arange(n))
    return pd.Series(series.values * warp_curve, index=series.index)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest packages/forecasting/tests/test_augmentation.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/forecasting/augmentation.py packages/forecasting/tests/test_augmentation.py
git commit -m "feat: add time-series data augmentation (jitter, scale, warp)

Jittering adds Gaussian noise, scaling changes magnitude uniformly,
magnitude warping applies smooth cubic spline distortion. All preserve
temporal order and series length.

Refs: docs/features/009-prediction-engine.md"
```

---

### Task 6: Create Pydantic schemas

**Files:**
- Modify: `apps/api/domains/forecasting/schemas.py` (replace empty stub)
- Create: `apps/api/domains/forecasting/tests/test_schemas.py`

- [ ] **Step 1: Write failing tests**

Create `apps/api/domains/forecasting/tests/test_schemas.py`:

```python
import pytest
from pydantic import ValidationError


def test_forecast_point_valid():
    from apps.api.domains.forecasting.schemas import ForecastPoint

    point = ForecastPoint(date="2026-04-07", p10=100.0, p50=200.0, p90=300.0)
    assert point.p10 == 100.0


def test_forecast_response_valid():
    from apps.api.domains.forecasting.schemas import ForecastPoint, ForecastResponse

    resp = ForecastResponse(
        forecast=[ForecastPoint(date="2026-04-07", p10=100, p50=200, p90=300)],
        model_type="chronos2",
        model_version="chronos-2-small",
        horizon=1,
        variable_importance=None,
        confidence="medium",
    )
    assert resp.model_type == "chronos2"
    assert resp.variable_importance is None


def test_forecast_response_with_variable_importance():
    from apps.api.domains.forecasting.schemas import (
        ForecastPoint,
        ForecastResponse,
        VariableImportance,
    )

    resp = ForecastResponse(
        forecast=[ForecastPoint(date="2026-04-07", p10=100, p50=200, p90=300)],
        model_type="tft_hybrid",
        model_version="tft-hybrid-v1",
        horizon=1,
        variable_importance=[
            VariableImportance(feature="is_payday", weight=0.6),
            VariableImportance(feature="day_of_week", weight=0.4),
        ],
        confidence="high",
    )
    assert len(resp.variable_importance) == 2


def test_train_status_response_valid():
    from apps.api.domains.forecasting.schemas import TrainStatusResponse

    resp = TrainStatusResponse(
        status="completed",
        last_trained="2026-04-06T12:00:00Z",
        checkpoint_path="checkpoints/user1/job1/tft_best.ckpt",
        training_days=120,
    )
    assert resp.status == "completed"


def test_forecast_response_rejects_invalid_confidence():
    from apps.api.domains.forecasting.schemas import ForecastPoint, ForecastResponse

    with pytest.raises(ValidationError):
        ForecastResponse(
            forecast=[ForecastPoint(date="2026-04-07", p10=100, p50=200, p90=300)],
            model_type="chronos2",
            model_version="v1",
            horizon=1,
            variable_importance=None,
            confidence="very_high",  # invalid
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest apps/api/domains/forecasting/tests/test_schemas.py -v`
Expected: FAIL (schemas module is empty)

- [ ] **Step 3: Implement schemas**

Write `apps/api/domains/forecasting/schemas.py`:

```python
"""Pydantic schemas for forecasting API."""

from typing import Literal

from pydantic import BaseModel


class ForecastPoint(BaseModel):
    date: str
    p10: float
    p50: float
    p90: float


class VariableImportance(BaseModel):
    feature: str
    weight: float


class ForecastResponse(BaseModel):
    forecast: list[ForecastPoint]
    model_type: str
    model_version: str
    horizon: int
    variable_importance: list[VariableImportance] | None
    confidence: Literal["low", "medium", "high"]


class TrainRequest(BaseModel):
    force: bool = False


class TrainStatusResponse(BaseModel):
    status: str
    last_trained: str | None = None
    checkpoint_path: str | None = None
    training_days: int | None = None
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest apps/api/domains/forecasting/tests/test_schemas.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/domains/forecasting/schemas.py apps/api/domains/forecasting/tests/test_schemas.py
git commit -m "feat: add Pydantic schemas for forecast API

ForecastPoint, ForecastResponse, VariableImportance,
TrainRequest, TrainStatusResponse. Confidence is typed
as Literal['low', 'medium', 'high'].

Refs: docs/features/009-prediction-engine.md"
```

---

### Task 7: Create `service.py` — two-tier routing logic

**Files:**
- Modify: `apps/api/domains/forecasting/service.py` (replace empty stub)
- Create: `apps/api/domains/forecasting/tests/test_service.py`

- [ ] **Step 1: Write failing tests**

Create `apps/api/domains/forecasting/tests/test_service.py`:

```python
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


def _make_transactions(n_days=100):
    dates = pd.date_range("2025-10-01", periods=n_days, freq="D")
    amounts = np.random.choice([-50, -20, 1000, -10], size=n_days).astype(float)
    return pd.DataFrame({"date": dates, "amount": amounts})


class TestForecastService:
    def test_cold_start_uses_chronos(self):
        """Users with < 90 days should get Chronos-2 predictions."""
        from apps.api.domains.forecasting.service import ForecastService

        mock_supabase = MagicMock()
        svc = ForecastService(mock_supabase)

        short_df = _make_transactions(n_days=30)
        mock_chronos = MagicMock()
        mock_chronos.predict.return_value = {
            "forecast": [{"date": "2026-04-07", "p10": 100, "p50": 200, "p90": 300}],
            "model_type": "chronos2",
            "model_version": "v1",
            "horizon": 1,
        }

        with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=mock_chronos):
            result = svc.predict(short_df, user_id="user1", horizon=1)

        assert result.model_type == "chronos2"
        assert result.confidence == "low"

    def test_established_user_without_model_triggers_training(self):
        """Users with >= 90 days but no model should get Chronos + training trigger."""
        from apps.api.domains.forecasting.service import ForecastService

        mock_supabase = MagicMock()
        # No completed training jobs
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        svc = ForecastService(mock_supabase)

        long_df = _make_transactions(n_days=120)
        mock_chronos = MagicMock()
        mock_chronos.predict.return_value = {
            "forecast": [{"date": "2026-04-07", "p10": 100, "p50": 200, "p90": 300}],
            "model_type": "chronos2",
            "model_version": "v1",
            "horizon": 1,
        }

        with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=mock_chronos):
            with patch("apps.api.domains.forecasting.service.load_model", return_value=None):
                result = svc.predict(long_df, user_id="user1", horizon=1)

        assert result.model_type == "chronos2"
        assert result.confidence == "medium"

    def test_confidence_mapping(self):
        """Verify confidence levels map correctly to days of data."""
        from apps.api.domains.forecasting.service import _compute_confidence

        assert _compute_confidence(10) == "low"
        assert _compute_confidence(30) == "low"
        assert _compute_confidence(50) == "medium"
        assert _compute_confidence(89) == "medium"
        assert _compute_confidence(90) == "medium"
        assert _compute_confidence(200, has_model=True) == "high"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest apps/api/domains/forecasting/tests/test_service.py -v`
Expected: FAIL (service module is empty)

- [ ] **Step 3: Implement `service.py`**

Write `apps/api/domains/forecasting/service.py`:

```python
"""Forecast service — two-tier routing between Chronos-2 and TFT-Hybrid."""

import logging

import pandas as pd
from supabase import Client

from apps.api.domains.forecasting.schemas import (
    ForecastPoint,
    ForecastResponse,
    TrainStatusResponse,
    VariableImportance,
)
from packages.forecasting.chronos_engine import get_chronos_engine
from packages.forecasting.dataset import TransactionLoader, prepare_training_data
from packages.forecasting.ensemble import ensemble_forecasts
from packages.forecasting.inference import extract_variable_importance, load_model, predict_with_tft

logger = logging.getLogger(__name__)

COLD_START_THRESHOLD = 90  # days


def _compute_confidence(days_of_data: int, has_model: bool = False) -> str:
    if days_of_data <= 30:
        return "low"
    if has_model and days_of_data >= 90:
        return "high"
    return "medium"


class ForecastService:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    def predict(
        self,
        transactions_df: pd.DataFrame,
        user_id: str,
        horizon: int = 30,
    ) -> ForecastResponse:
        """Route prediction to appropriate tier based on data availability."""
        # Aggregate to daily
        loader = TransactionLoader(transactions_df)
        daily_df = loader.aggregate_daily()
        days_of_data = len(daily_df)

        # Determine tier
        tft_model = None
        has_model = False
        if days_of_data >= COLD_START_THRESHOLD:
            tft_model = load_model(self.supabase, user_id)
            has_model = tft_model is not None

        confidence = _compute_confidence(days_of_data, has_model)

        # Always get Chronos-2 prediction (baseline)
        chronos = get_chronos_engine()
        chronos_result = chronos.predict(daily_df, horizon=horizon)

        if has_model:
            # Tier 2: TFT + Chronos ensemble
            tft_result = predict_with_tft(tft_model, transactions_df, horizon=horizon)
            if "error" in tft_result:
                logger.warning(f"TFT inference failed: {tft_result['error']}")
                return self._build_response(chronos_result, confidence)

            # Extract variable importance if available (delegates to inference.py)
            raw_importance = extract_variable_importance(tft_model, transactions_df)
            var_importance = (
                [VariableImportance(**vi) for vi in raw_importance]
                if raw_importance
                else None
            )

            combined = ensemble_forecasts(tft_result, chronos_result)
            combined["variable_importance"] = var_importance
            return self._build_response(combined, confidence)

        if days_of_data >= COLD_START_THRESHOLD:
            # Trigger training if not already pending/processing
            self._maybe_trigger_training(user_id)

        return self._build_response(chronos_result, confidence)

    def get_train_status(self, user_id: str) -> TrainStatusResponse:
        """Check the training job status for a user."""
        response = (
            self.supabase.table("training_jobs")
            .select("status, created_at, checkpoint_path, metrics")
            .eq("user_id", user_id)
            .eq("job_type", "forecasting")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not response.data:
            return TrainStatusResponse(status="no_model")

        job = response.data[0]
        training_days = None
        if job.get("metrics") and isinstance(job["metrics"], dict):
            training_days = job["metrics"].get("days_of_data")

        return TrainStatusResponse(
            status=job["status"],
            last_trained=job.get("created_at"),
            checkpoint_path=job.get("checkpoint_path"),
            training_days=training_days,
        )

    def trigger_training(self, user_id: str, force: bool = False) -> TrainStatusResponse:
        """Insert a training job for the polling worker to pick up."""
        if not force:
            existing = (
                self.supabase.table("training_jobs")
                .select("id, status")
                .eq("user_id", user_id)
                .eq("job_type", "forecasting")
                .in_("status", ["pending", "claimed", "processing"])
                .limit(1)
                .execute()
            )
            if existing.data:
                return TrainStatusResponse(status=existing.data[0]["status"])

        self.supabase.table("training_jobs").insert({
            "user_id": user_id,
            "job_type": "forecasting",
            "status": "pending",
            "logs": "forecasting: queued via API",
        }).execute()

        return TrainStatusResponse(status="pending")

    def _maybe_trigger_training(self, user_id: str):
        """Trigger training only if no active job exists."""
        try:
            self.trigger_training(user_id, force=False)
        except Exception as e:
            logger.warning(f"Failed to trigger training for {user_id}: {e}")

    def _build_response(
        self,
        result: dict,
        confidence: str,
    ) -> ForecastResponse:
        return ForecastResponse(
            forecast=[ForecastPoint(**p) for p in result["forecast"]],
            model_type=result["model_type"],
            model_version=result.get("model_version", "unknown"),
            horizon=result.get("horizon", len(result["forecast"])),
            variable_importance=result.get("variable_importance"),
            confidence=confidence,
        )
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest apps/api/domains/forecasting/tests/test_service.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/domains/forecasting/service.py apps/api/domains/forecasting/tests/test_service.py
git commit -m "feat: add ForecastService with two-tier routing logic

Routes to Chronos-2 for cold-start users (<90 days), TFT-Hybrid
ensemble for established users, with automatic training trigger.
Confidence mapping: low (<30d), medium (30-89d), high (90d+model).

Refs: docs/features/009-prediction-engine.md"
```

---

### Task 8: Refactor `router.py` to delegate to service

**Files:**
- Modify: `apps/api/domains/forecasting/router.py`
- Test: `apps/api/domains/forecasting/tests/test_forecast.py` (existing)

- [ ] **Step 1: Add new endpoints to router**

Rewrite `apps/api/domains/forecasting/router.py` to be a thin delegation layer. Keep the existing POST /predict with CSV upload, add GET /predict from DB, add POST /train, add GET /model-status:

```python
"""Forecasting router — predict spending, safe-to-spend, training triggers.

Delegates business logic to ForecastService.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import pandas as pd
import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from apps.api.core.auth import get_current_user_id, get_user_client
from apps.api.domains.forecasting.schemas import (
    ForecastResponse,
    TrainRequest,
    TrainStatusResponse,
)
from apps.api.domains.forecasting.service import ForecastService
from packages.forecasting.dataset import TransactionLoader
from packages.ingestion_engine.import_transactions import parse_file
from supabase import Client

router = APIRouter(prefix="/forecast", tags=["forecast"])
logger = structlog.get_logger()


def _get_service(client: Client = Depends(get_user_client)) -> ForecastService:
    return ForecastService(client)


@router.post("/predict", response_model=ForecastResponse)
async def forecast_predict_upload(
    file: UploadFile = File(...),
    horizon: int = Query(30, ge=1, le=90),
    user_id: str = Depends(get_current_user_id),
    service: ForecastService = Depends(_get_service),
    client: Client = Depends(get_user_client),
):
    """Upload CSV of transactions, return probabilistic forecast."""
    if file.content_type and "csv" not in file.content_type and "text" not in file.content_type:
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    contents = await file.read()
    file_hash = hashlib.sha256(contents).hexdigest()

    try:
        df = parse_file(contents, file.filename)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to parse CSV")

    # Deduplication check
    try:
        client.table("uploaded_files").insert({
            "user_id": user_id,
            "file_hash": file_hash,
            "filename": file.filename,
            "upload_type": "forecast",
        }).execute()
    except Exception as e:
        if "duplicate key" in str(e) or "23505" in str(e):
            raise HTTPException(status_code=400, detail="This file has already been uploaded for forecasting.")
        raise HTTPException(status_code=500, detail="Failed to register upload")

    if "transaction_date" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"transaction_date": "date"})

    try:
        return service.predict(df, user_id=user_id, horizon=horizon)
    except ValueError as e:
        client.table("uploaded_files").delete().eq("user_id", user_id).eq("file_hash", file_hash).execute()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/predict", response_model=ForecastResponse)
async def forecast_predict_db(
    horizon: int = Query(30, ge=1, le=90),
    user_id: str = Depends(get_current_user_id),
    service: ForecastService = Depends(_get_service),
    client: Client = Depends(get_user_client),
):
    """Fetch transactions from DB, return probabilistic forecast."""
    lookback_days = 365
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

    try:
        response = (
            client.table("transactions")
            .select("transaction_date, amount, description, merchant_name, category")
            .eq("user_id", user_id)
            .gte("transaction_date", cutoff)
            .order("transaction_date", desc=False)
            .limit(10000)
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch transactions")

    if not response.data:
        raise HTTPException(status_code=400, detail="No transaction data available")

    df = pd.DataFrame(response.data)
    df = df.rename(columns={"transaction_date": "date"})
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    return service.predict(df, user_id=user_id, horizon=horizon)


@router.get("/safe-to-spend")
async def safe_to_spend(
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    """Returns predicted safe-to-spend amount for the authenticated user."""
    horizon = 7
    lookback_days = 90

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        response = (
            client.table("transactions")
            .select("transaction_date, amount, status")
            .eq("user_id", user_id)
            .gte("transaction_date", cutoff)
            .order("transaction_date", desc=False)
            .limit(5000)
            .execute()
        )
        rows = response.data
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch transactions")

    if not rows:
        return {
            "safe_amount": 0.0,
            "currency": "INR",
            "horizon_days": horizon,
            "confidence": 0.0,
            "model": "none",
            "note": "No transactions found in the last 90 days.",
        }

    df = pd.DataFrame(rows)
    df = df.rename(columns={"transaction_date": "date"})
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    loader = TransactionLoader(df)
    daily_df = loader.aggregate_daily()
    days_of_data = len(daily_df)
    confidence = round(min(days_of_data / lookback_days, 1.0), 2)
    recent = daily_df.tail(min(30, len(daily_df)))

    avg_daily_income = float(recent["daily_income"].mean()) if "daily_income" in recent.columns else 0.0
    avg_daily_spend = float(recent["daily_spend"].mean()) if "daily_spend" in recent.columns else 0.0
    net = (avg_daily_income - avg_daily_spend) * horizon
    safe_amount = round(max(0.0, net), 2)
    projected_overspend = round(max(0.0, -net), 2)

    return {
        "safe_amount": safe_amount,
        "projected_overspend": projected_overspend,
        "currency": "INR",
        "horizon_days": horizon,
        "confidence": confidence,
        "avg_daily_income": round(avg_daily_income, 2),
        "avg_daily_spend": round(avg_daily_spend, 2),
        "days_analyzed": days_of_data,
        "model": "statistical_mvp",
        "note": f"Based on {days_of_data} days of transaction history.",
    }


@router.post("/train", response_model=TrainStatusResponse)
async def trigger_training(
    body: TrainRequest = TrainRequest(),
    user_id: str = Depends(get_current_user_id),
    service: ForecastService = Depends(_get_service),
):
    """Trigger async TFT model training for the current user."""
    return service.trigger_training(user_id, force=body.force)


@router.get("/model-status", response_model=TrainStatusResponse)
async def model_status(
    user_id: str = Depends(get_current_user_id),
    service: ForecastService = Depends(_get_service),
):
    """Check training job status for the current user."""
    return service.get_train_status(user_id)
```

- [ ] **Step 2: Run existing tests**

Run: `.venv/bin/python -m pytest apps/api/domains/forecasting/tests/ -v`
Expected: Existing tests may need adjustments for new response format. Fix any that break.

- [ ] **Step 3: Commit**

```bash
git add apps/api/domains/forecasting/router.py
git commit -m "feat: refactor forecast router to delegate to ForecastService

Adds GET /predict (DB-based), POST /train, GET /model-status.
Keeps POST /predict (CSV upload) for backward compatibility.
Business logic now lives in service.py.

Refs: docs/features/009-prediction-engine.md"
```

---

### Task 9: Fix worker duplicate log lines

**Files:**
- Modify: `apps/worker/main.py:91-94`

- [ ] **Step 1: Fix duplicate log lines**

In `apps/worker/main.py`, lines 91-94 are duplicated:

```python
    summary = f"Training complete. Val loss: {best_val_loss:.6f}. Checkpoint: {checkpoint_path}"
    logger.info(f"[{job_id}] {summary}")
    summary = f"Training complete. Val loss: {best_val_loss:.6f}. Checkpoint: {checkpoint_path}"
    logger.info(f"[{job_id}] {summary}")
```

Remove the duplicate (keep only one pair).

- [ ] **Step 2: Commit**

```bash
git add apps/worker/main.py
git commit -m "chore: remove duplicate log lines in worker train_model

Lines 91-94 had the summary and log statement duplicated."
```

---

### Task 10: Integration test — full predict flow

**Files:**
- Create: `apps/api/domains/forecasting/tests/test_predict_integration.py`

- [ ] **Step 1: Write integration test**

```python
"""Integration test: full predict flow through service layer."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import torch


def _mock_chronos_engine():
    engine = MagicMock()
    engine.predict.return_value = {
        "forecast": [
            {"date": f"2026-05-{str(i+1).zfill(2)}", "p10": 100 + i, "p50": 200 + i, "p90": 300 + i}
            for i in range(30)
        ],
        "model_type": "chronos2",
        "model_version": "chronos-2-small",
        "horizon": 30,
    }
    return engine


def test_cold_start_full_flow():
    """< 90 days of data -> Chronos-2 only, confidence=low."""
    from apps.api.domains.forecasting.service import ForecastService

    mock_supabase = MagicMock()
    svc = ForecastService(mock_supabase)

    dates = pd.date_range("2026-03-01", periods=20, freq="D")
    df = pd.DataFrame({"date": dates, "amount": np.random.uniform(-100, 100, 20)})

    with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=_mock_chronos_engine()):
        result = svc.predict(df, user_id="test-user", horizon=30)

    assert result.model_type == "chronos2"
    assert result.confidence == "low"
    assert len(result.forecast) == 30
    assert result.variable_importance is None


def test_established_user_no_model_triggers_training():
    """90+ days but no trained model -> Chronos-2 + trigger training."""
    from apps.api.domains.forecasting.service import ForecastService

    mock_supabase = MagicMock()
    # No existing active jobs
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    # Insert succeeds
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "job1"}])

    svc = ForecastService(mock_supabase)

    dates = pd.date_range("2025-10-01", periods=180, freq="D")
    df = pd.DataFrame({"date": dates, "amount": np.random.uniform(-100, 100, 180)})

    with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=_mock_chronos_engine()):
        with patch("apps.api.domains.forecasting.service.load_model", return_value=None):
            result = svc.predict(df, user_id="test-user", horizon=30)

    assert result.model_type == "chronos2"
    assert result.confidence == "medium"


def test_concurrent_training_dedup():
    """If a training job is already pending/processing, don't create another."""
    from apps.api.domains.forecasting.service import ForecastService

    mock_supabase = MagicMock()
    # Existing pending job
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "existing-job", "status": "processing"}]
    )

    svc = ForecastService(mock_supabase)
    result = svc.trigger_training("test-user", force=False)

    assert result.status == "processing"
    # Insert should NOT have been called
    mock_supabase.table.return_value.insert.assert_not_called()


def test_nan_prediction_falls_back_to_chronos():
    """TFT producing NaN should fall back to Chronos-2."""
    from apps.api.domains.forecasting.service import ForecastService

    mock_supabase = MagicMock()
    svc = ForecastService(mock_supabase)

    dates = pd.date_range("2025-06-01", periods=180, freq="D")
    df = pd.DataFrame({"date": dates, "amount": np.random.uniform(-100, 100, 180)})

    # TFT returns error
    tft_error_result = {"error": "NaN detected in predictions"}

    with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=_mock_chronos_engine()):
        with patch("apps.api.domains.forecasting.service.load_model", return_value=MagicMock()):
            with patch("apps.api.domains.forecasting.service.predict_with_tft", return_value=tft_error_result):
                result = svc.predict(df, user_id="test-user", horizon=30)

    # Should fall back to Chronos-2
    assert result.model_type == "chronos2"
```

- [ ] **Step 2: Run integration tests**

Run: `.venv/bin/python -m pytest apps/api/domains/forecasting/tests/test_predict_integration.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add apps/api/domains/forecasting/tests/test_predict_integration.py
git commit -m "test: add integration tests for two-tier prediction flow

Tests cold-start (Chronos-2 only) and established-user-no-model
(Chronos-2 + training trigger) flows through ForecastService.

Refs: docs/features/009-prediction-engine.md"
```

---

### Task 11: Run full test suite and verify

- [ ] **Step 1: Run all forecasting package tests**

Run: `.venv/bin/python -m pytest packages/forecasting/tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run all API forecasting tests**

Run: `.venv/bin/python -m pytest apps/api/domains/forecasting/tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Run full project tests**

Run: `make test`
Expected: ALL PASS (or document any pre-existing failures)

- [ ] **Step 4: Update LLD status to Implemented**

In `docs/features/009-prediction-engine.md`, change `Status: Draft` to `Status: Implemented`.

- [ ] **Step 5: Commit**

```bash
git add docs/features/009-prediction-engine.md
git commit -m "docs: update 009 prediction engine status to In Progress"
```
