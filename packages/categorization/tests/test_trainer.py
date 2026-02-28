import torch
from unittest.mock import patch
from packages.categorization.trainer import HypCDTrainer
from packages.categorization.hyperbolic_nn import HypFFN


def test_trainer_init():
    model = HypFFN(10, 8, 4)
    trainer = HypCDTrainer(model)
    assert trainer.model == model
    assert trainer.optimizer is not None
    # Check if optimizer is RiemannianAdam (or handling parameters correctly)


def test_train_step():
    # Mock model and data
    model = HypFFN(10, 8, 4)
    trainer = HypCDTrainer(model, lr=0.01)

    # Input data
    # Anchor: [Batch, Dim]
    # Positive: [Batch, Dim]
    # Target: [Batch]
    anchor = torch.zeros(2, 10)
    positive = torch.zeros(2, 10)
    target = torch.ones(2)

    # Run a step
    loss = trainer.train_step(anchor, positive, target)

    assert isinstance(loss, float)
    assert loss >= 0.0


@patch("packages.categorization.trainer.HypCDTrainer.save_checkpoint")
def test_train_loop_runs(mock_save):
    # Mock dataloader
    model = HypFFN(10, 8, 4)
    trainer = HypCDTrainer(model)

    # Create simple iterable for dataloader
    # Yields (anchor, positive, target)
    dataloader = [
        (torch.randn(2, 10), torch.randn(2, 10), torch.ones(2)) for _ in range(3)
    ]

    metrics = trainer.train(dataloader, epochs=1)

    assert "loss" in metrics
    assert len(metrics["loss"]) == 1  # 1 epoch
