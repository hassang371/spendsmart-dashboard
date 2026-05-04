"""RFC-006 forecast evaluation harness.

Public API surface — re-exported for convenience:

    from packages.forecasting.eval import (
        run_walk_forward,
        TrainingConfig,
        DEFAULT,
        GROKKING,
        mean_pinball_loss,
        pinball_loss_all_quantiles,
        mape,
        coverage,
        interval_width,
        calibration_error,
        select_stratified_users,
        evaluate_thresholds,
        render_markdown,
    )

The harness is offline-only — it never writes to ``user_predictions`` or
touches the production cache. See ``docs/rfcs/RFC-006-forecast-evaluation-
harness.md`` for the full design.
"""

from packages.forecasting.eval.configs import (
    DEFAULT,
    GROKKING,
    TrainingConfig,
    resolve_config,
)
from packages.forecasting.eval.harness import run_walk_forward
from packages.forecasting.eval.metrics import (
    QUANTILE_LEVELS,
    calibration_error,
    coverage,
    interval_width,
    mape,
    mean_pinball_loss,
    pinball_loss,
    pinball_loss_all_quantiles,
)
from packages.forecasting.eval.report import (
    DEFAULT_THRESHOLDS,
    evaluate_thresholds,
    render_markdown,
)
from packages.forecasting.eval.sampling import select_stratified_users

__all__ = [
    "DEFAULT",
    "DEFAULT_THRESHOLDS",
    "GROKKING",
    "QUANTILE_LEVELS",
    "TrainingConfig",
    "calibration_error",
    "coverage",
    "evaluate_thresholds",
    "interval_width",
    "mape",
    "mean_pinball_loss",
    "pinball_loss",
    "pinball_loss_all_quantiles",
    "render_markdown",
    "resolve_config",
    "run_walk_forward",
    "select_stratified_users",
]
