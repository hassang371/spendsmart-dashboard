import torch
import geoopt


class HyperbolicKMeans:
    def __init__(self, n_clusters=5, c=1.0, max_iter=100, tol=1e-4):
        self.n_clusters = n_clusters
        self.c = c
        self.max_iter = max_iter
        self.tol = tol
        self.manifold = geoopt.PoincareBall(c=c)
        self.centroids = None

    def fit(self, X, max_iter=None):
        """
        Compute hyperbolic k-means clustering.
        X: [N, Dim] points in Poincare ball
        """
        if max_iter is None:
            max_iter = self.max_iter

        N, D = X.shape

        # 1. Initialize Centroids
        # Random pick from data is better than random noise
        # Or K-Means++ logic (harder to impl cleanly in 1 file)
        # Let's simple random pick
        indices = torch.randperm(N)[: self.n_clusters]
        self.centroids = X[indices].clone().detach()
        # Ensure centroids are trainable parameters on manifold
        self.centroids = geoopt.ManifoldParameter(
            self.centroids, manifold=self.manifold
        )

        # Optimization for Fréchet Mean
        # We optimize centroids to minimize sum of squared distances
        # But standard K-Means is Expectation-Maximization
        # E-step: Assign labels
        # M-step: Update centroids

        prev_centroids = None

        for i in range(max_iter):
            # --- E-Step: Assignment ---
            # Broadcast to get [N, K] distance matrix
            # X: [N, D] -> [N, 1, D]
            # Centroids: [K, D] -> [1, K, D]
            dist_matrix = self.manifold.dist2(
                X.unsqueeze(1), self.centroids.unsqueeze(0)
            )
            labels = torch.argmin(dist_matrix, dim=1)

            # Check convergence (if labels didn't change? or centroids)
            if prev_centroids is not None:
                dist_shift = self.manifold.dist(self.centroids, prev_centroids).max()
                if dist_shift < self.tol:
                    break
            prev_centroids = self.centroids.clone().detach()

            # --- M-Step: Update Centroids ---
            # For each cluster, find Fréchet mean
            new_centroids_list = []

            for k in range(self.n_clusters):
                mask = labels == k
                points = X[mask]

                if len(points) == 0:
                    # Keep old centroid or re-init?
                    # Keep old for stability
                    new_centroids_list.append(self.centroids[k : k + 1])
                    continue

                # Compute Mean
                # Option A: Mobius Mean (Avg in Gyrovector space) -> Closed form approx?
                # Option B: Gradient Descent to find Fréchet Mean

                # Let's use Gradient Descent (Riemannian) for accurate mean
                k_centroid = self.centroids[k : k + 1].clone().detach()
                k_centroid = geoopt.ManifoldParameter(
                    k_centroid, manifold=self.manifold
                )

                # Optimizer for this single point
                optimizer = geoopt.optim.RiemannianAdam([k_centroid], lr=0.1)

                # Few steps of optimization
                for _ in range(20):  # 20 steps usually enough for mean
                    optimizer.zero_grad()
                    # Loss = sum of squared distances
                    # dists = self.manifold.dist(points, k_centroid)
                    # loss = (dists ** 2).mean() # Mean or Sum? Fréchet is min expected dist^2

                    # geoopt has efficient dist calc
                    loss = self.manifold.dist2(points, k_centroid).mean()
                    loss.backward()
                    optimizer.step()

                new_centroids_list.append(k_centroid.detach())

            # Stack new centroids
            self.centroids = torch.cat(new_centroids_list, dim=0)
            self.centroids = geoopt.ManifoldParameter(
                self.centroids, manifold=self.manifold
            )

        return self

    def predict(self, X):
        """
        Predict the closest cluster each sample in X belongs to on the manifold.
        """
        if self.centroids is None:
            raise ValueError("Model not fitted yet")

        dist_matrix = self.manifold.dist2(X.unsqueeze(1), self.centroids.unsqueeze(0))
        labels = torch.argmin(dist_matrix, dim=1)
        return labels

    def fit_predict(self, X):
        self.fit(X)
        return self.predict(X)
