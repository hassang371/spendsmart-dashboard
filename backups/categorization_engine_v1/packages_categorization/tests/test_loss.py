"""Tests for HypCDTrainer loss functions in training.py (losses.py deleted)."""

import torch
from geoopt import PoincareBall

from packages.categorization.hypcd import HyperbolicProjector
from packages.categorization.training import HypCDTrainer


def make_trainer():
    manifold = PoincareBall(c=1.0)
    projector = HyperbolicProjector(input_dim=4, hidden_dim=4, output_dim=2)
    return HypCDTrainer(projector=projector, manifold=manifold, lr=1e-4)


def test_hyperbolic_distance_loss_positive_pair_beats_negative():
    """Distance loss should be lower when positive pair is closer."""
    trainer = make_trainer()
    manifold = trainer.manifold

    # Anchor at 0.1 on x-axis
    z_i = torch.tensor([[0.1, 0.0]])
    # Positive: very close
    z_j_close = torch.tensor([[0.11, 0.0]])
    # Positive: very far
    z_j_far = torch.tensor([[0.7, 0.0]])
    # Negatives
    negatives = torch.tensor([[[0.5, 0.5]]])  # (1, 1, 2)

    loss_close = trainer.hyperbolic_distance_loss(z_i, z_j_close, negatives)
    loss_far = trainer.hyperbolic_distance_loss(z_i, z_j_far, negatives)

    assert loss_close < loss_far


def test_angle_loss_aligned_beats_orthogonal():
    """Angle loss should be lower for aligned vectors than orthogonal ones."""
    trainer = make_trainer()

    z_i = torch.tensor([[0.3, 0.0]])
    z_j_aligned = torch.tensor([[0.25, 0.0]])  # Same direction
    z_j_ortho = torch.tensor([[0.0, 0.3]])  # Perpendicular

    loss_aligned = trainer.angle_loss(z_i, z_j_aligned)
    loss_ortho = trainer.angle_loss(z_i, z_j_ortho)

    assert loss_aligned < loss_ortho
