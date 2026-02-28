import torch
from packages.categorization.hypcd import HyperbolicEmbedder, HypCDClassifier
from geoopt import PoincareBall


def test_hyperbolic_embedder_initialization():
    """Test HyperbolicEmbedder with backend."""
    from packages.categorization.backends.mobile import MobileBackend

    backend = MobileBackend()
    embedder = HyperbolicEmbedder(backend=backend, proj_dim=128)
    assert embedder.backend is not None
    assert embedder.projector is not None
    assert isinstance(embedder.projector.manifold, PoincareBall)


def test_embed_transaction():
    """Test embedding a transaction."""
    from packages.categorization.backends.mobile import MobileBackend

    backend = MobileBackend()
    embedder = HyperbolicEmbedder(backend=backend, proj_dim=128)
    text = "STARBUCKS COFFEE 0324"
    embedding = embedder.embed(text)

    # Check shape (proj_dim)
    assert embedding.shape[0] == 128

    # Check if point is on manifold (norm < 1 for Poincare Ball)
    norm = embedding.norm(dim=-1)
    assert torch.all(norm < 1.0)


def test_poincare_distance():
    """Test Poincare distance computation."""
    manifold = PoincareBall(c=1.0)
    # Center of the ball
    p1 = torch.zeros(1, 128)
    # Another point
    p2 = torch.zeros(1, 128)
    p2[0, 0] = 0.5

    dist = manifold.dist(p1, p2)
    # Distance from 0 to 0.5 in Poincare ball with c=1 is 2 * arctanh(0.5)
    expected_dist = 2 * torch.atanh(torch.tensor(0.5))

    assert torch.isclose(dist, expected_dist, atol=1e-4)


def test_classifier_predict_mock():
    """Test classifier prediction with mock backend."""

    # Create mock backend and projector
    class MockBackend:
        def __init__(self):
            self.device = "cpu"
            self.dim = 384

        def embed(self, text):
            # Single text embedding
            return torch.randn(self.dim)

        def embed_batch(self, texts):
            # Batch embedding - return 2D tensor
            return torch.randn(len(texts), self.dim)

    backend = MockBackend()
    classifier = HypCDClassifier(backend=backend, proj_dim=128, num_classes=11)

    # Test prediction
    result = classifier.predict("BURGER KING")
    assert "category" in result
    assert "confidence" in result
    assert "embedding" in result
    assert result["category"] in classifier.labels


def test_classifier_batch_predict_mock():
    """Test classifier batch prediction."""

    class MockBackend:
        def __init__(self):
            self.device = "cpu"
            self.dim = 384

        def embed(self, text):
            # Single text embedding
            return torch.randn(self.dim)

        def embed_batch(self, texts):
            # Batch embedding - return 2D tensor
            return torch.randn(len(texts), self.dim)

    backend = MockBackend()
    classifier = HypCDClassifier(backend=backend, proj_dim=128, num_classes=11)

    results = classifier.predict_batch(["BURGER KING", "UBER"])
    assert len(results) == 2
    assert results[0]["category"] in classifier.labels
    assert results[1]["category"] in classifier.labels


def test_hyperbolic_projector_init():
    """HyperbolicProjector should initialize with correct dimensions."""
    from packages.categorization.hypcd import HyperbolicProjector

    projector = HyperbolicProjector(input_dim=768, hidden_dim=256, output_dim=128)

    assert projector.mlp[0].in_features == 768
    assert projector.mlp[0].out_features == 256
    assert projector.mlp[2].out_features == 128


def test_hyperbolic_projector_forward():
    """HyperbolicProjector should output valid hyperbolic embeddings."""
    from packages.categorization.hypcd import HyperbolicProjector

    projector = HyperbolicProjector(input_dim=768, hidden_dim=256, output_dim=128)

    # Input batch
    x = torch.randn(4, 768)
    z = projector(x)

    # Output should be on Poincaré ball (norm < 1)
    assert z.shape == (4, 128)
    norms = torch.norm(z, dim=-1)
    assert torch.all(norms < 1.0), "Embeddings should be inside Poincaré ball"
    assert torch.all(norms < 0.99), "Embeddings should be within clipping boundary"
    assert not torch.isnan(z).any(), "No NaN values allowed"
    assert not torch.isinf(z).any(), "No Inf values allowed"


def test_feature_clipping():
    """Feature clipping should prevent boundary violations."""
    from packages.categorization.hypcd import HyperbolicProjector

    projector = HyperbolicProjector(
        input_dim=10, hidden_dim=8, output_dim=5, clip_factor=0.9
    )

    # Create input that would produce large output
    x = torch.randn(1, 10) * 10
    h = projector.mlp(x)
    h_clipped = projector.clip_features(h)

    # Clipped features should respect boundary
    norms = torch.norm(h_clipped, dim=-1)
    assert torch.all(norms <= 0.9 + 1e-6), "Features should be clipped to 0.9"


def test_hyperbolic_embedder_with_backend():
    """HyperbolicEmbedder should work with new backend architecture."""
    from packages.categorization.hypcd import HyperbolicEmbedder
    from packages.categorization.backends.cloud import CloudBackend

    backend = CloudBackend(model_name="prajjwal1/bert-tiny", dim=128)
    embedder = HyperbolicEmbedder(backend=backend, proj_dim=64)

    # Should have projector
    assert embedder.projector is not None

    # Should predict
    result = embedder.embed("food delivery")
    assert result is not None
    assert result.shape == torch.Size([64])  # Single embedding


def test_hyp_linear_init():
    """HypLinear should initialize with correct dimensions."""
    from packages.categorization.hypcd import HypLinear
    from geoopt import PoincareBall

    manifold = PoincareBall(c=1.0)
    layer = HypLinear(128, 64, manifold)

    assert layer.weight.shape == (64, 128)
    assert layer.bias.shape == (64,)


def test_hyp_linear_forward():
    """HypLinear should perform Möbius matrix multiplication."""
    from packages.categorization.hypcd import HypLinear
    from geoopt import PoincareBall

    manifold = PoincareBall(c=1.0)
    layer = HypLinear(10, 5, manifold)

    # Input on Poincaré ball
    x = torch.tensor([[0.1, 0.2, 0.3, 0.1, 0.0, 0.2, 0.1, 0.3, 0.1, 0.0]])
    x = manifold.expmap0(x)  # Ensure on manifold

    out = layer(x)

    # Output should also be on Poincaré ball
    assert out.shape == (1, 5)
    norms = torch.norm(out, dim=-1)
    assert torch.all(norms < 1.0), "Output should be on Poincaré ball"
    assert not torch.isnan(out).any()


def test_hyp_ffn_init():
    """HypFFN should initialize with correct dimensions."""
    from packages.categorization.hypcd import HypFFN
    from geoopt import PoincareBall

    manifold = PoincareBall(c=1.0)
    classifier = HypFFN(dim=128, num_classes=11, manifold=manifold)

    assert classifier.fc1.in_features == 128
    assert classifier.fc1.out_features == 64  # dim // 2
    assert classifier.fc2.out_features == 11


def test_hyp_ffn_forward():
    """HypFFN should classify hyperbolic embeddings."""
    from packages.categorization.hypcd import HypFFN
    from geoopt import PoincareBall

    manifold = PoincareBall(c=1.0)
    classifier = HypFFN(dim=128, num_classes=11, manifold=manifold)

    # Input embeddings
    x = torch.randn(4, 128) * 0.1  # Small values for stability
    x = manifold.expmap0(x)

    logits = classifier(x)

    assert logits.shape == (4, 11)
    norms = torch.norm(logits, dim=-1)
    assert torch.all(norms < 1.0), "Output should be on Poincaré ball"
    assert not torch.isnan(logits).any()


def test_hypcd_classifier_with_backend():
    """HypCDClassifier should work with backend architecture."""
    from packages.categorization.hypcd import HypCDClassifier
    from packages.categorization.backends.cloud import CloudBackend

    backend = CloudBackend(model_name="prajjwal1/bert-tiny", dim=128)
    classifier = HypCDClassifier(backend=backend, num_classes=5, proj_dim=64)

    # Should have classifier
    assert classifier.classifier is not None

    # Should predict
    result = classifier.predict("food delivery")
    assert "category" in result
    assert "confidence" in result


def test_hypcd_classifier_predict_batch():
    """HypCDClassifier should handle batch predictions."""
    from packages.categorization.hypcd import HypCDClassifier
    from packages.categorization.backends.cloud import CloudBackend

    backend = CloudBackend(model_name="prajjwal1/bert-tiny", dim=128)
    classifier = HypCDClassifier(backend=backend, num_classes=5, proj_dim=64)

    texts = ["food delivery", "taxi ride", "movie ticket"]
    results = classifier.predict_batch(texts)

    assert len(results) == 3
    for r in results:
        assert "category" in r
        assert "confidence" in r
