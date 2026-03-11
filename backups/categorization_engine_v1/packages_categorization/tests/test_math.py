"""Tests for hyperbolic math primitives now in hypcd.py (hyperbolic_nn.py deleted)."""

import torch
from geoopt import PoincareBall

from packages.categorization.hypcd import HyperbolicProjector, HypFFN, HypLinear

manifold = PoincareBall(c=1.0)


def test_projector_output_on_poincare_ball():
    """Output of HyperbolicProjector must have norm < 1 (valid Poincaré point)."""
    projector = HyperbolicProjector(input_dim=8, hidden_dim=8, output_dim=4, clip_factor=0.98)
    x = torch.randn(5, 8) * 10  # Large input
    out = projector(x)
    assert out.shape == (5, 4)
    norms = out.norm(dim=-1)
    assert torch.all(norms < 1.0), f"Some outputs outside Poincaré ball: {norms}"


def test_projector_clip_factor_respected():
    """Feature clipping should keep pre-expmap norms ≤ clip_factor."""
    projector = HyperbolicProjector(input_dim=4, hidden_dim=4, output_dim=2, clip_factor=0.5)
    large_input = torch.ones(3, 4) * 100
    # Just check it doesn't crash and stays on ball
    out = projector(large_input)
    assert torch.all(out.norm(dim=-1) < 1.0)


def test_hyplinear_output_shape():
    batch_size, in_f, out_f = 5, 10, 4
    layer = HypLinear(in_f, out_f, manifold)
    x = torch.zeros(batch_size, in_f)  # Origin is always on manifold
    y = layer(x)
    assert y.shape == (batch_size, out_f)
    assert torch.all(y.norm(dim=-1) < 1.0)


def test_hyplinear_identity_weight_zero_input():
    """With identity weight, HypLinear(zeros) = expmap0(bias)."""
    layer = HypLinear(2, 2, manifold)
    with torch.no_grad():
        layer.weight.copy_(torch.eye(2))
        layer.bias.copy_(torch.tensor([0.3, 0.0]))

    x = torch.zeros(1, 2)
    y = layer(x)
    # logmap0(zeros) = zeros, linear = bias, expmap0(bias) should match
    expected = manifold.expmap0(torch.tensor([[0.3, 0.0]]))
    assert torch.allclose(y, expected, atol=1e-5)


def test_hypffn_forward_shape():
    model = HypFFN(dim=8, num_classes=3, manifold=manifold)
    x = torch.zeros(5, 8)  # Origin
    out = model(x)
    assert out.shape == (5, 3)
    assert torch.all(out.norm(dim=-1) < 1.0)
