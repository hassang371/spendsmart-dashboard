import torch
import geoopt
from packages.categorization.hyperbolic_nn import HypLinear, HyperbolicProjector, HypFFN

# Establish the Manifold
manifold = geoopt.PoincareBall(c=1.0)


def test_projector_clipping():
    # Input vector with large norm (> 1)
    large_vector = torch.tensor([[10.0, 10.0]])

    # Projector with max_norm=0.9
    projector = HyperbolicProjector(input_dim=2, output_dim=2, max_norm=0.9)

    # The output in hyperbolic space should have norm < 1 (Poincare constraint)
    # But specifically, the input to expmap should have been clipped to 0.9

    # Let's mock the manifold to check what expmap receives?
    # Or just check the mathematical property.

    hyp_out = projector(large_vector)
    norm = hyp_out.norm(dim=-1)
    assert torch.all(norm < 1.0)

    # Verify clipping logic explicitly if possible?
    # For now, functional test: Does it crash? No. Does it produce valid output? Yes.


def test_hyplinear_shapes():
    batch_size = 5
    in_features = 10
    out_features = 4

    layer = HypLinear(in_features, out_features, c=1.0)

    # Input must be on manifold. Let's create some zero vectors (origin is safe)
    x = torch.zeros(batch_size, in_features)

    y = layer(x)

    assert y.shape == (batch_size, out_features)

    # Check if output is on manifold
    norm = y.norm(dim=-1)
    assert torch.all(norm < 1.0)


def test_hyplinear_mobius_add():
    # Test if bias translation works.
    # HypLinear(x) = M @ x + b (mobius addition)
    # If x is 0, output should be bias.

    layer = HypLinear(2, 2, c=1.0)
    with torch.no_grad():
        # Set weight to Identity and Bias to something known
        layer.weight.copy_(torch.eye(2))
        layer.bias.copy_(torch.tensor([0.5, 0.0]))

    x = torch.zeros(1, 2)
    y = layer(x)

    # 0 + b = b in Mobius addition too
    assert torch.allclose(y, torch.tensor([[0.5, 0.0]]))


def test_hypffn_forward():
    # Test full network flow
    model = HypFFN(input_dim=10, hidden_dim=8, output_dim=3, c=1.0)

    x = torch.zeros(5, 10)  # 5 samples on manifold
    output = model(x)

    assert output.shape == (5, 3)
    assert torch.all(output.norm(dim=-1) < 1.0)
