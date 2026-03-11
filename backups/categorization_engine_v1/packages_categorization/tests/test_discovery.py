"""Tests for HyperbolicKMeans in clustering.py (replaces deleted discovery.py)."""

import torch
from geoopt import PoincareBall

from packages.categorization.clustering import HyperbolicKMeans


def _manifold():
    return PoincareBall(c=1.0)


def test_kmeans_init():
    kmeans = HyperbolicKMeans(n_clusters=3, manifold=_manifold())
    assert kmeans.n_clusters == 3
    assert kmeans.centroids is None  # Not fitted yet


def test_kmeans_fit_and_predict():
    # Two well-separated clusters on the Poincaré ball
    c1 = torch.tensor([[0.6, 0.0], [0.62, 0.02], [0.58, -0.02]])
    c2 = torch.tensor([[-0.6, 0.0], [-0.62, 0.02], [-0.58, -0.02]])
    X = torch.cat([c1, c2], dim=0)

    kmeans = HyperbolicKMeans(n_clusters=2, manifold=_manifold())
    kmeans.fit(X)

    assert kmeans.centroids is not None
    assert kmeans.centroids.shape == (2, 2)

    labels, confidence, is_known = kmeans.predict(X)
    assert labels.shape == (6,)
    # First 3 should share a label, last 3 share a label
    assert labels[0] == labels[1] == labels[2]
    assert labels[3] == labels[4] == labels[5]
    assert labels[0] != labels[3]


def test_kmeans_centroids_move_toward_data():
    X = torch.tensor([[0.3, 0.0], [0.35, 0.0]])
    kmeans = HyperbolicKMeans(n_clusters=1, manifold=_manifold())
    kmeans.fit(X)
    # Centroid should be positive on the x-axis
    assert kmeans.centroids[0, 0] > 0.1
