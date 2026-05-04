"""RFC-006 §4 — TrainingConfig dataclass + DEFAULT/GROKKING presets.

The harness maps ``TrainingConfig.patience`` →
``trainer.run_training(early_stop_patience=...)``. Defaults are chosen to
preserve current production behaviour exactly so an unchanged callsite
yields unchanged training results.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingConfig:
    """Hyperparameter bundle passed to ``trainer.run_training``.

    Field map:
        name           → identifier carried in run JSON + reports
        max_epochs     → ``run_training(max_epochs=...)``
        patience       → ``run_training(early_stop_patience=...)``
        weight_decay   → ``run_training(weight_decay=...)``
        batch_size     → ``run_training(batch_size=...)``
        learning_rate  → ``run_training(learning_rate=...)``
    """

    name: str
    max_epochs: int
    patience: int
    weight_decay: float
    batch_size: int
    learning_rate: float


# RFC-006 §4 — current LLD 009 production-ish hyperparameters.
DEFAULT: TrainingConfig = TrainingConfig(
    name="default",
    max_epochs=30,
    patience=5,
    weight_decay=0.0,
    batch_size=64,
    learning_rate=3e-4,
)


# RFC-006 §4 — extended-patience grokking regime (Cowork synthesis hypothesis).
GROKKING: TrainingConfig = TrainingConfig(
    name="grokking",
    max_epochs=150,
    patience=50,
    weight_decay=1e-4,
    batch_size=16,
    learning_rate=3e-4,
)


_PRESETS: dict[str, TrainingConfig] = {
    "default": DEFAULT,
    "grokking": GROKKING,
}


def resolve_config(name: str) -> TrainingConfig:
    """Look up a preset config by name (``"default"`` or ``"grokking"``).

    Raises ``KeyError`` for unknown names; the CLI catches and rewrites
    this to a friendly argparse error.
    """
    if name not in _PRESETS:
        raise KeyError(f"Unknown training config: {name!r}. " f"Available presets: {sorted(_PRESETS.keys())}")
    return _PRESETS[name]
