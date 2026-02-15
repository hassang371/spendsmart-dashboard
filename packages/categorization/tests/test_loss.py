import torch
from packages.categorization.losses import HyperbolicDistanceLoss, CosineLoss


def test_hyperbolic_distance_loss():
    # Loss should decrease as points get closer in hyperbolic space
    criterion = HyperbolicDistanceLoss(c=1.0)

    # Two points
    v1 = torch.tensor([[0.1, 0.0]])
    v2_close = torch.tensor([[0.11, 0.0]])
    v2_far = torch.tensor([[0.8, 0.0]])

    loss_close = criterion(
        v1, v2_close, torch.tensor([1.0])
    )  # Label 1 = Positive pair (pull together)
    loss_far = criterion(v1, v2_far, torch.tensor([1.0]))

    assert loss_close < loss_far


def test_cosine_loss():
    # Loss should optimize angles
    criterion = CosineLoss()

    v1 = torch.tensor([[1.0, 0.0]])
    v2_aligned = torch.tensor([[0.9, 0.1]])  # Small angle
    v2_ortho = torch.tensor([[0.0, 1.0]])  # 90 deg

    loss_aligned = criterion(v1, v2_aligned, torch.tensor([1.0]))
    loss_ortho = criterion(v1, v2_ortho, torch.tensor([1.0]))

    assert loss_aligned < loss_ortho
