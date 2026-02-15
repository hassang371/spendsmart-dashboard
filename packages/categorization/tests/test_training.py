"""Tests for HypCD training pipeline."""
import torch
from geoopt import PoincareBall


def test_hypcd_trainer_init():
    """HypCDTrainer should initialize with RiemannianAdam."""
    from packages.categorization.training import HypCDTrainer
    from packages.categorization.hypcd import HyperbolicProjector

    projector = HyperbolicProjector(768, 256, 128)
    manifold = PoincareBall(c=1.0)

    trainer = HypCDTrainer(projector, manifold, lr=1e-4)

    assert trainer.projector == projector
    assert trainer.manifold == manifold
    assert trainer.optimizer is not None


def test_hyperbolic_distance_loss():
    """Distance loss should measure hyperbolic distances."""
    from packages.categorization.training import HypCDTrainer
    from packages.categorization.hypcd import HyperbolicProjector

    projector = HyperbolicProjector(10, 8, 5)
    manifold = PoincareBall(c=1.0)
    trainer = HypCDTrainer(projector, manifold)

    # Create sample hyperbolic embeddings
    z_i = torch.tensor([[0.1, 0.2, 0.3, 0.1, 0.0]])
    z_j = torch.tensor([[0.2, 0.1, 0.2, 0.2, 0.1]])
    # New format: (batch, n_neg, dim)
    negatives = torch.tensor([[[0.5, 0.5, 0.5, 0.5, 0.5]]])

    loss = trainer.hyperbolic_distance_loss(z_i, z_j, negatives)

    # Loss should be a valid number (InfoNCE can be negative)
    assert not torch.isnan(loss)
    assert not torch.isinf(loss)


def test_angle_loss():
    """Angle loss should measure cosine similarity in tangent space."""
    from packages.categorization.training import HypCDTrainer
    from packages.categorization.hypcd import HyperbolicProjector

    projector = HyperbolicProjector(10, 8, 5)
    manifold = PoincareBall(c=1.0)
    trainer = HypCDTrainer(projector, manifold)

    z_i = torch.tensor([[0.1, 0.2, 0.3, 0.1, 0.0]])
    z_j = torch.tensor([[0.2, 0.1, 0.2, 0.2, 0.1]])

    loss = trainer.angle_loss(z_i, z_j)

    assert loss.item() >= 0
    assert loss.item() <= 2  # Cosine similarity range mapped to [0, 2]
    assert not torch.isnan(loss)
