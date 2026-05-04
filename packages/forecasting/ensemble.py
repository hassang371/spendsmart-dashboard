"""Weighted ensemble of TFT and Chronos-2 forecasts.

Blends across all seven RFC-003 quantiles (p2, p10, p25, p50, p75,
p90, p98) so the API response shape stays consistent regardless of
which engine(s) actually produced the forecast.
"""

from __future__ import annotations

from typing import Any

# Single source of truth for the RFC-003 quantile keys. Imported here
# (rather than re-declared) so any future RFC change touches one
# constant.
from packages.forecasting.chronos_engine import QUANTILE_LABELS


def ensemble_forecasts(
    tft_result: dict[str, Any] | None,
    chronos_result: dict[str, Any],
    tft_weight: float = 0.7,
    chronos_weight: float = 0.3,
) -> dict[str, Any]:
    """Blend TFT and Chronos-2 forecasts with configurable weights.

    Args:
        tft_result: Forecast dict produced by the TFT path, or ``None``
            when no TFT model is available (cold-start users).
        chronos_result: Forecast dict produced by ``ChronosEngine.predict``.
        tft_weight: Weight applied to the TFT quantile values.
        chronos_weight: Weight applied to the Chronos quantile values.

    Returns:
        Blended forecast dict with the same seven-quantile shape as the
        inputs. When ``tft_result`` is ``None``, returns ``chronos_result``
        unchanged so the caller does not need to special-case cold-start.

    Raises:
        ValueError: If the two forecasts have different horizons.
    """
    if tft_result is None:
        return chronos_result

    tft_fc = tft_result["forecast"]
    chr_fc = chronos_result["forecast"]

    if len(tft_fc) != len(chr_fc):
        raise ValueError(f"Forecast horizon mismatch: TFT={len(tft_fc)}, Chronos={len(chr_fc)}")

    blended: list[dict[str, Any]] = []
    for t, c in zip(tft_fc, chr_fc, strict=True):
        # Blend each quantile, then sort to guarantee monotonicity.
        # Two engines blended at different weights can produce crossing
        # (e.g. TFT noise on p2 lifting it above p10), which would make
        # the frontend fan chart hide every band as a defensive guard.
        # QuantileLoss expects monotonic quantiles by construction; we
        # restore that invariant at the API boundary.
        values = sorted(tft_weight * float(t[key]) + chronos_weight * float(c[key]) for key in QUANTILE_LABELS)
        point: dict[str, Any] = {"date": t["date"]}
        for key, val in zip(QUANTILE_LABELS, values, strict=True):
            point[key] = round(val, 2)
        blended.append(point)

    return {
        "forecast": blended,
        "model_type": "ensemble",
        "model_version": f"tft({tft_weight})+chronos({chronos_weight})",
        "horizon": len(blended),
    }
