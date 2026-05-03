"""Chronos-2 zero-shot forecasting engine.

Provides immediate probabilistic forecasts for users without trained
TFT models (cold-start path). Uses Amazon Chronos-2-Small (28M params).

Per RFC-003 §1 ("Chronos-path quantile expansion") the engine emits
all seven of the RFC-003 quantiles per forecast point — p2, p10, p25,
p50, p75, p90, p98 — matching the TFT path's quantile shape. The
module-level ``QUANTILES`` tensor is the single source of truth.
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
# package is absent we set ``ChronosPipeline = None`` so that:
#   - the patch path remains valid for tests
#   - any direct (un-patched) instantiation fails fast with a clear error
try:  # pragma: no cover - exercised by environment, not unit tests
    from chronos import ChronosPipeline  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised by environment, not unit tests
    ChronosPipeline = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# RFC-003 §1 — seven-quantile contract shared with the TFT path.
QUANTILES = torch.tensor([0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98])
QUANTILE_LABELS: tuple[str, ...] = ("p2", "p10", "p25", "p50", "p75", "p90", "p98")

# Singleton engine: loaded once, reused across requests.
_ENGINE: "ChronosEngine | None" = None


class ChronosEngine:
    """Zero-shot probabilistic forecasting via Amazon Chronos-2."""

    def __init__(
        self,
        model_name: str = "amazon/chronos-2-small",
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self._pipeline: Any = None

    @property
    def pipeline(self) -> Any:
        if self._pipeline is None:
            if ChronosPipeline is None:
                raise RuntimeError(
                    "chronos-forecasting is not installed; install "
                    "'chronos-forecasting>=1.3,<2.0' to run the Chronos engine."
                )
            logger.info("Loading Chronos model: %s", self.model_name)
            self._pipeline = ChronosPipeline.from_pretrained(self.model_name, device_map=self.device)
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
            num_samples: Monte-Carlo sample count for the underlying
                probabilistic generator.

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

        samples = self.pipeline.predict(context, prediction_length=horizon, num_samples=num_samples)
        # samples shape: [1, num_samples, horizon]

        quantile_tensor = torch.quantile(
            samples[0].float(),
            QUANTILES,
            dim=0,
        )
        # quantile_tensor shape: [len(QUANTILES), horizon]

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
            "model_version": "chronos-2-small",
            "horizon": horizon,
        }


def get_chronos_engine() -> ChronosEngine:
    """Returns a singleton ``ChronosEngine`` instance."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = ChronosEngine()
    return _ENGINE
