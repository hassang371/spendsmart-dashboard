"""Chronos-Bolt zero-shot forecasting engine.

Provides immediate probabilistic forecasts for users without trained
TFT models (cold-start path). Uses Amazon Chronos-Bolt-Small (47M
params) — the V2 successor to chronos-t5 with direct quantile output
and no Monte-Carlo sampling overhead.

Per RFC-003 §1 ("Chronos-path quantile expansion") the engine emits
all seven of the RFC-003 quantiles per forecast point — p2, p10, p25,
p50, p75, p90, p98 — matching the TFT path's quantile shape. The
module-level ``QUANTILES`` list is the single source of truth.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import torch

# chronos-forecasting is an optional runtime dependency. The module must
# remain import-safe in environments where it is not installed (e.g. CI
# unit tests use unittest.mock.patch on this attribute, and the schema
# review harness should not require the heavy model package). When the
# package is absent we set ``BaseChronosPipeline = None`` so that:
#   - the patch path remains valid for tests
#   - any direct (un-patched) instantiation fails fast with a clear error
try:  # pragma: no cover - exercised by environment, not unit tests
    from chronos import BaseChronosPipeline  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised by environment, not unit tests
    BaseChronosPipeline = None  # type: ignore[assignment]

# Backwards-compat alias retained for tests that patch
# ``packages.forecasting.chronos_engine.ChronosPipeline`` (Stage 1
# legacy). ChronosPipeline still exists in the chronos package but
# only handles the older T5 family; the engine now loads Bolt via
# BaseChronosPipeline auto-routing.
try:  # pragma: no cover
    from chronos import ChronosPipeline  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    ChronosPipeline = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# RFC-003 §1 — seven-quantile contract shared with the TFT path.
QUANTILE_LEVELS: list[float] = [0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98]
QUANTILES = torch.tensor(QUANTILE_LEVELS)
QUANTILE_LABELS: tuple[str, ...] = ("p2", "p10", "p25", "p50", "p75", "p90", "p98")

# Singleton engine: loaded once, reused across requests.
_ENGINE: "ChronosEngine | None" = None


class ChronosEngine:
    """Zero-shot probabilistic forecasting via Amazon Chronos-Bolt."""

    def __init__(
        self,
        model_name: str = "amazon/chronos-bolt-small",
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self._pipeline: Any = None

    @property
    def pipeline(self) -> Any:
        if self._pipeline is None:
            if BaseChronosPipeline is None:
                raise RuntimeError(
                    "chronos-forecasting is not installed; install "
                    "'chronos-forecasting>=1.3,<2.0' to run the Chronos engine."
                )
            logger.info("Loading Chronos model: %s", self.model_name)
            self._pipeline = BaseChronosPipeline.from_pretrained(self.model_name, device_map=self.device)
        return self._pipeline

    def predict(
        self,
        daily_df: pd.DataFrame,
        horizon: int = 30,
        num_samples: int = 100,
    ) -> dict[str, Any]:
        """Run a zero-shot probabilistic forecast.

        Args:
            daily_df: DataFrame with at least a ``closing_balance`` column
                and either a ``date`` column or a DatetimeIndex.
            horizon: Number of days to predict.
            num_samples: Monte-Carlo sample count. Used only on the legacy
                ChronosPipeline path; ChronosBoltPipeline emits quantiles
                directly and ignores this argument.

        Returns:
            Dict with a ``forecast`` list of seven-quantile dicts per day,
            plus ``model_type``, ``model_version``, and ``horizon``.

        Raises:
            ValueError: If ``daily_df`` is empty or missing
                ``closing_balance``.
        """
        if daily_df.empty or "closing_balance" not in daily_df.columns:
            raise ValueError("No transaction data available for forecasting")

        context = torch.tensor(daily_df["closing_balance"].values, dtype=torch.float32).unsqueeze(
            0
        )  # shape: [1, seq_len]

        pipeline = self.pipeline

        if hasattr(pipeline, "predict_quantiles"):
            # Bolt path: direct quantile output, no MC sampling.
            quantiles, _mean = pipeline.predict_quantiles(
                context=context,
                prediction_length=horizon,
                quantile_levels=QUANTILE_LEVELS,
            )
            # quantiles shape: [batch=1, horizon, len(QUANTILE_LEVELS)]
            quantile_tensor = quantiles[0].T.float()
            # quantile_tensor shape: [len(QUANTILES), horizon]
        else:
            # Legacy T5 path: sample then quantile. Retained so a config
            # override (e.g. amazon/chronos-t5-small) keeps working.
            samples = pipeline.predict(context, prediction_length=horizon, num_samples=num_samples)
            quantile_tensor = torch.quantile(
                samples[0].float(),
                QUANTILES,
                dim=0,
            )

        # Determine future dates.
        if "date" in daily_df.columns:
            last_date = pd.to_datetime(daily_df["date"]).max()
        elif isinstance(daily_df.index, pd.DatetimeIndex):
            last_date = daily_df.index.max()
        else:
            last_date = pd.Timestamp.now()

        future_dates = pd.date_range(
            start=last_date + pd.Timedelta(days=1),
            periods=horizon,
            freq="D",
        )

        forecast: list[dict[str, Any]] = []
        for i in range(horizon):
            point: dict[str, Any] = {"date": future_dates[i].strftime("%Y-%m-%d")}
            for q_idx, label in enumerate(QUANTILE_LABELS):
                point[label] = round(float(quantile_tensor[q_idx, i]), 2)
            forecast.append(point)

        return {
            "forecast": forecast,
            "model_type": "chronos2",
            "model_version": self.model_name.split("/")[-1],
            "horizon": horizon,
        }


def get_chronos_engine() -> ChronosEngine:
    """Returns a singleton ``ChronosEngine`` instance."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = ChronosEngine()
    return _ENGINE
