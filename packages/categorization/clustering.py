"""Hyperbolic clustering with Fréchet mean and hierarchy extraction."""
import torch
from geoopt.optim import RiemannianSGD
from typing import Optional


class HyperbolicKMeans:
    """
    Hyperbolic K-Means with Fréchet Mean (Section 3.7.2).

    Implements clustering in Poincaré ball for Generalized Category Discovery.
    """

    def __init__(
        self, n_clusters: int, manifold, max_iter: int = 100, tol: float = 1e-4
    ):
        """
        Initialize hyperbolic K-means.

        Args:
            n_clusters: Number of clusters
            manifold: PoincaréBall manifold
            max_iter: Maximum iterations
            tol: Convergence tolerance
        """
        self.n_clusters = n_clusters
        self.manifold = manifold
        self.max_iter = max_iter
        self.tol = tol
        self.centroids = None

    def frechet_mean(
        self,
        points: torch.Tensor,
        weights: Optional[torch.Tensor] = None,
        lr: float = 0.1,
        steps: int = 50,
    ) -> torch.Tensor:
        """
        Compute Fréchet mean (Riemannian Center of Mass).

        No closed-form in Poincaré ball - use gradient descent.

        Args:
            points: Points to average (n, dim) on manifold
            weights: Optional weights for weighted mean
            lr: Learning rate for optimization
            steps: Number of gradient steps

        Returns:
            Fréchet mean on manifold
        """
        # Initialize as Euclidean mean in tangent space
        points_tan = self.manifold.logmap0(points)

        if weights is not None:
            mean_tan = (points_tan * weights.unsqueeze(-1)).sum(dim=0) / weights.sum()
        else:
            mean_tan = points_tan.mean(dim=0)

        centroid = self.manifold.expmap0(mean_tan)
        centroid = centroid.unsqueeze(0)  # Add batch dimension
        centroid.requires_grad = True

        # Optimize with Riemannian SGD
        optimizer = RiemannianSGD([centroid], lr=lr)

        for _ in range(steps):
            optimizer.zero_grad()

            # Sum of squared hyperbolic distances
            dists = self.manifold.dist(centroid, points)
            loss = (dists**2).sum()

            loss.backward()
            optimizer.step()

        return centroid.detach().squeeze(0)

    def fit(self, embeddings: torch.Tensor):
        """
        Cluster embeddings in hyperbolic space.

        Args:
            embeddings: Hyperbolic embeddings (n_samples, dim)
        """
        n_samples = embeddings.shape[0]

        # Initialize centroids randomly
        indices = torch.randperm(n_samples)[: self.n_clusters]
        self.centroids = embeddings[indices].clone()

        for iteration in range(self.max_iter):
            # Assignment: nearest centroid by hyperbolic distance
            distances = torch.stack(
                [
                    self.manifold.dist(embeddings, c.unsqueeze(0))
                    for c in self.centroids
                ],
                dim=1,
            )

            labels = distances.argmin(dim=1)

            # Update: Fréchet mean for each cluster
            new_centroids = []
            for k in range(self.n_clusters):
                mask = labels == k
                if mask.sum() > 0:
                    cluster_points = embeddings[mask]
                    new_centroids.append(self.frechet_mean(cluster_points))
                else:
                    # Reinitialize empty cluster
                    new_centroids.append(self.centroids[k])

            new_centroids = torch.stack(new_centroids)

            # Check convergence
            centroid_shift = self.manifold.dist(self.centroids, new_centroids).max()
            self.centroids = new_centroids

            if centroid_shift < self.tol:
                break

    def predict(self, embeddings: torch.Tensor, confidence_threshold: float = 0.7):
        """
        Classify knowns vs discover unknowns (Section 3.7.1).

        Args:
            embeddings: Hyperbolic embeddings to classify
            confidence_threshold: Threshold for novel detection

        Returns:
            labels: Assigned cluster labels
            confidence: Confidence scores
            is_known: Boolean mask (True = known, False = novel)
        """
        if self.centroids is None:
            raise ValueError("Must call fit() before predict()")

        # Compute distances to all centroids
        distances = torch.stack(
            [self.manifold.dist(embeddings, c.unsqueeze(0)) for c in self.centroids],
            dim=1,
        )

        # Get nearest centroid and distance
        min_dist, labels = distances.min(dim=1)

        # Convert distance to confidence (closer = higher confidence)
        # Use exponential decay: confidence = exp(-distance)
        confidence = torch.exp(-min_dist)

        # Mark low-confidence as "novel"
        is_known = confidence > confidence_threshold

        return labels, confidence, is_known


class HierarchyExtractor:
    """
    Extract hierarchy from hyperbolic norms (Section 3.8).

    Norm = Depth: Low norm = macro (near center), High norm = micro (near boundary)
    """

    def __init__(self, manifold):
        """
        Initialize hierarchy extractor.

        Args:
            manifold: PoincaréBall manifold
        """
        self.manifold = manifold

    def compute_norm(self, embedding: torch.Tensor) -> torch.Tensor:
        """
        Compute hyperbolic norm from origin.

        Args:
            embedding: Hyperbolic embedding

        Returns:
            Norm (distance from origin)
        """
        origin = torch.zeros_like(embedding)
        return self.manifold.dist(embedding, origin)

    def categorize_depth(self, centroids: torch.Tensor):
        """
        Classify centroids by depth in hierarchy.

        Args:
            centroids: Category centroids (n_clusters, dim)

        Returns:
            macro: List of (index, norm) for macro categories (near center)
            micro: List of (index, norm) for micro categories (near boundary)
        """
        # Compute norms for all centroids
        norms = torch.stack([self.compute_norm(c) for c in centroids])
        median_norm = torch.median(norms)

        macro = []  # Near center (low norm)
        micro = []  # Near boundary (high norm)

        for i, norm in enumerate(norms):
            if norm < median_norm:
                macro.append((i, norm.item()))
            else:
                micro.append((i, norm.item()))

        return macro, micro

    def build_taxonomy(self, centroids: torch.Tensor, labels: list) -> dict:
        """
        Build hierarchical taxonomy from embeddings.

        Args:
            centroids: Category centroids (n_clusters, dim)
            labels: List of category labels

        Returns:
            Taxonomy dictionary with macro and micro categories
        """
        macro, micro = self.categorize_depth(centroids)

        taxonomy = {
            "macro": [
                {
                    "id": i,
                    "label": labels[i] if i < len(labels) else f"category_{i}",
                    "depth": "center",
                    "norm": n,
                }
                for i, n in macro
            ],
            "micro": [
                {
                    "id": i,
                    "label": labels[i] if i < len(labels) else f"category_{i}",
                    "depth": "boundary",
                    "norm": n,
                }
                for i, n in micro
            ],
        }

        return taxonomy
