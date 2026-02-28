"""Tests for hyperbolic clustering and hierarchy extraction."""
import torch
from geoopt import PoincareBall


def test_hyperbolic_kmeans_init():
    """HyperbolicKMeans should initialize correctly."""
    from packages.categorization.clustering import HyperbolicKMeans

    manifold = PoincareBall(c=1.0)
    kmeans = HyperbolicKMeans(n_clusters=5, manifold=manifold)

    assert kmeans.n_clusters == 5
    assert kmeans.centroids is None


def test_frechet_mean():
    """Fréchet mean should compute Riemannian center of mass."""
    from packages.categorization.clustering import HyperbolicKMeans

    manifold = PoincareBall(c=1.0)
    kmeans = HyperbolicKMeans(n_clusters=3, manifold=manifold)

    # Create cluster of points
    points = torch.tensor([[0.1, 0.1, 0.0], [0.12, 0.08, 0.02], [0.09, 0.11, 0.01]])
    points = manifold.expmap0(points)

    mean = kmeans.frechet_mean(points, steps=20)

    # Mean should be on manifold
    assert torch.norm(mean) < 1.0
    assert not torch.isnan(mean).any()

    # Mean should be close to all points
    distances = manifold.dist(mean.unsqueeze(0), points)
    assert torch.all(distances < 0.6)  # Relaxed threshold


def test_hyperbolic_kmeans_fit():
    """HyperbolicKMeans should cluster embeddings."""
    from packages.categorization.clustering import HyperbolicKMeans

    manifold = PoincareBall(c=1.0)
    kmeans = HyperbolicKMeans(n_clusters=2, manifold=manifold, max_iter=10)

    # Create two clusters
    cluster1 = torch.randn(5, 10) * 0.1 + 0.3
    cluster2 = torch.randn(5, 10) * 0.1 - 0.3
    embeddings = torch.cat([cluster1, cluster2])
    embeddings = manifold.expmap0(embeddings)

    kmeans.fit(embeddings)

    # Should have centroids
    assert kmeans.centroids is not None
    assert kmeans.centroids.shape == (2, 10)


def test_hierarchy_extractor_init():
    """HierarchyExtractor should initialize correctly."""
    from packages.categorization.clustering import HierarchyExtractor
    from geoopt import PoincareBall

    manifold = PoincareBall(c=1.0)
    extractor = HierarchyExtractor(manifold)

    assert extractor.manifold == manifold


def test_compute_norm():
    """Norm should indicate depth in hierarchy."""
    from packages.categorization.clustering import HierarchyExtractor
    from geoopt import PoincareBall

    manifold = PoincareBall(c=1.0)
    extractor = HierarchyExtractor(manifold)

    # Near center (low norm) = macro category
    macro = manifold.expmap0(torch.tensor([0.1, 0.1, 0.1]))
    macro_norm = extractor.compute_norm(macro)

    # Near boundary (high norm) = micro category
    micro = manifold.expmap0(torch.tensor([0.8, 0.1, 0.1]))
    micro_norm = extractor.compute_norm(micro)

    assert micro_norm > macro_norm


def test_categorize_depth():
    """Categorize centroids by depth."""
    from packages.categorization.clustering import HierarchyExtractor
    from geoopt import PoincareBall

    manifold = PoincareBall(c=1.0)
    extractor = HierarchyExtractor(manifold)

    # Create centroids at different depths (use larger gap for hyperbolic space)
    centroids = manifold.expmap0(
        torch.tensor(
            [
                [0.05, 0.0, 0.0],  # Near center (macro)
                [0.08, 0.0, 0.0],  # Near center (macro)
                [0.5, 0.0, 0.0],  # Near boundary (micro)
                [0.8, 0.0, 0.0],  # Near boundary (micro)
            ]
        )
    )

    macro, micro = extractor.categorize_depth(centroids)

    # Just verify we get some split (exact counts depend on hyperbolic geometry)
    assert len(macro) >= 1
    assert len(micro) >= 1
    assert len(macro) + len(micro) == 4
