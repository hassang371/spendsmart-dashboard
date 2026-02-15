import torch
from packages.categorization.discovery import HyperbolicKMeans


def test_kmeans_init():
    kmeans = HyperbolicKMeans(n_clusters=3, c=1.0)
    assert kmeans.n_clusters == 3
    assert hasattr(kmeans, "centroids")


def test_kmeans_fit_predict():
    # Create simple data: 3 clusters of points
    # Cluster 1: near (0.5, 0)
    # Cluster 2: near (-0.5, 0)
    # Cluster 3: near (0, 0.5)

    c1 = torch.tensor([[0.5, 0.0], [0.55, 0.05], [0.45, -0.05]])
    c2 = torch.tensor([[-0.5, 0.0], [-0.55, 0.05], [-0.45, -0.05]])

    # Combined data [6, 2]
    X = torch.cat([c1, c2], dim=0)

    kmeans = HyperbolicKMeans(n_clusters=2, c=1.0)
    labels = kmeans.fit_predict(X)

    # Check shape
    assert labels.shape == (6,)

    # Ideally, first 3 should share a label, last 3 share a label
    assert labels[0] == labels[1]
    assert labels[0] == labels[2]
    assert labels[3] == labels[4]
    assert labels[3] == labels[5]
    assert labels[0] != labels[3]


def test_frechet_mean_update():
    # Test if centroids move
    kmeans = HyperbolicKMeans(n_clusters=1, c=1.0)

    # Data centered at 0.5, 0
    X = torch.tensor([[0.4, 0.0], [0.6, 0.0]])

    # Initialize centroid at 0, 0
    kmeans.centroids = torch.zeros(1, 2)

    # Determine new centroids (fit)
    kmeans.fit(X, max_iter=5)

    # Centroid should move towards 0.5, 0
    # In Poincaré/Euclidean, mean of 0.4 and 0.6 is 0.5.
    # In Hyperbolic, it's slightly different but should be positive on X axis.
    assert kmeans.centroids[0, 0] > 0.1
