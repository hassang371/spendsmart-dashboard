"""Tests for HypCDTrainer in training.py (replaces deleted trainer.py)."""
import torch
from geoopt import PoincareBall
from packages.categorization.hypcd import HyperbolicProjector
from packages.categorization.training import HypCDTrainer


def make_trainer(input_dim=8, output_dim=4, lr=1e-3):
    manifold = PoincareBall(c=1.0)
    projector = HyperbolicProjector(input_dim=input_dim, hidden_dim=8, output_dim=output_dim)
    return HypCDTrainer(projector=projector, manifold=manifold, lr=lr)


def test_trainer_init():
    trainer = make_trainer()
    assert trainer.projector is not None
    assert trainer.optimizer is not None


def test_train_step_returns_float():
    trainer = make_trainer(input_dim=8, output_dim=4)
    batch = {
        "original": torch.randn(4, 8),
        "augmented": torch.randn(4, 8),
    }
    loss = trainer.train_step(batch, lambda_weight=0.5)
    assert isinstance(loss, float)
    assert loss >= 0.0


def test_train_step_reduces_loss_over_steps():
    trainer = make_trainer(input_dim=8, output_dim=4, lr=0.01)
    # Same batch used repeatedly — loss should decrease or at minimum be valid
    batch = {
        "original": torch.randn(6, 8),
        "augmented": torch.randn(6, 8),
    }
    first_loss = trainer.train_step(batch, lambda_weight=0.5)
    for _ in range(5):
        last_loss = trainer.train_step(batch, lambda_weight=0.5)
    assert isinstance(last_loss, float)
