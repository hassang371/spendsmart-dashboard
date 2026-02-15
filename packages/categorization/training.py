"""Training pipeline for HypCD with RiemannianAdam and hybrid loss."""
import torch
import torch.nn.functional as F
from geoopt.optim import RiemannianAdam
from typing import List


class HypCDTrainer:
    """
    Full training pipeline per HypCD paper Section 3.6.

    Implements:
    - RiemannianAdam optimizer (Section 3.6.3)
    - Hybrid loss: L = λ * L_d + (1-λ) * L_a (Section 3.6.2)
    - Dynamic λ scheduling
    """

    def __init__(
        self, projector, manifold, lr: float = 1e-4, weight_decay: float = 0.0
    ):
        """
        Initialize trainer.

        Args:
            projector: HyperbolicProjector instance
            manifold: PoincaréBall manifold
            lr: Learning rate for RiemannianAdam
            weight_decay: Weight decay for regularization
        """
        self.projector = projector
        self.manifold = manifold

        # RiemannianAdam handles hyperbolic gradients correctly
        self.optimizer = RiemannianAdam(
            projector.parameters(), lr=lr, weight_decay=weight_decay
        )

    def hyperbolic_distance_loss(
        self, z_i: torch.Tensor, z_j: torch.Tensor, negatives: torch.Tensor
    ) -> torch.Tensor:
        """
        L_d: Pull positives together, push negatives apart.

        Per Section 3.6.2: InfoNCE-style loss in hyperbolic space.

        Args:
            z_i: Anchor embedding (batch, dim)
            z_j: Positive embedding (batch, dim)
            negatives: Negative embeddings (batch, n_neg, dim)

        Returns:
            Distance loss value
        """
        # Distance to positive: (batch,)
        pos_dist = self.manifold.dist(z_i, z_j)

        # Distances to negatives: (batch, n_neg)
        # Expand z_i for broadcasting: (batch, 1, dim)
        z_i_expanded = z_i.unsqueeze(1)
        # Compute distance to each negative
        neg_dists = self.manifold.dist(z_i_expanded, negatives)

        # InfoNCE-style loss per sample: pos_dist + log(sum(exp(-neg_dists)))
        # neg_dists is (batch, n_neg), sum over negatives
        loss = pos_dist + torch.logsumexp(-neg_dists, dim=1)

        return loss.mean()

    def angle_loss(self, z_i: torch.Tensor, z_j: torch.Tensor) -> torch.Tensor:
        """
        L_a: Cosine similarity for semantic clustering.

        Per Section 3.6.2: Measured in tangent space at origin.

        Args:
            z_i: First embedding (batch, dim)
            z_j: Second embedding (batch, dim)

        Returns:
            Angle loss value (1 - cosine_similarity)
        """
        # Map to tangent space at origin
        v_i = self.manifold.logmap0(z_i)
        v_j = self.manifold.logmap0(z_j)

        # Cosine similarity in tangent space
        cosine_sim = F.cosine_similarity(v_i, v_j, dim=-1)

        # Loss is 1 - cosine_similarity (range [0, 2])
        return (1 - cosine_sim).mean()

    def hybrid_loss(
        self,
        z_i: torch.Tensor,
        z_j: torch.Tensor,
        negatives: List[torch.Tensor],
        lambda_weight: float = 0.5,
    ) -> torch.Tensor:
        """
        Total Loss: L = λ * L_d + (1 - λ) * L_a

        Per Section 3.6.2: Combine distance and angle losses.

        Args:
            z_i: Anchor embedding
            z_j: Positive embedding
            negatives: List of negative embeddings
            lambda_weight: Balance between distance (λ) and angle (1-λ)

        Returns:
            Combined loss value
        """
        L_d = self.hyperbolic_distance_loss(z_i, z_j, negatives)
        L_a = self.angle_loss(z_i, z_j)

        return lambda_weight * L_d + (1 - lambda_weight) * L_a

    def train_step(self, batch: dict, lambda_weight: float = 0.5) -> float:
        """
        Single training step.

        Args:
            batch: Dictionary with 'original' and 'augmented' texts
            lambda_weight: Current λ value for loss balance

        Returns:
            Loss value
        """
        self.optimizer.zero_grad()

        # Forward pass for original and augmented
        z_orig = self.projector(batch["original"])
        z_aug = self.projector(batch["augmented"])

        # Generate negatives (random other samples in batch)
        negatives = self._sample_negatives(z_orig, z_aug)

        # Compute hybrid loss
        loss = self.hybrid_loss(z_orig, z_aug, negatives, lambda_weight)

        # Backward pass
        loss.backward()

        # Gradient clipping for stability
        torch.nn.utils.clip_grad_norm_(self.projector.parameters(), max_norm=1.0)

        # Optimizer step
        self.optimizer.step()

        return loss.item()

    def _sample_negatives(
        self, z_orig: torch.Tensor, z_aug: torch.Tensor
    ) -> torch.Tensor:
        """
        Sample negative examples from batch.
        
        Returns:
            negatives: Tensor of shape (batch, n_neg, dim)
        """
        batch_size = z_orig.shape[0]
        dim = z_orig.shape[1]
        
        # Combine original and augmented: (2*batch, dim)
        all_samples = torch.cat([z_orig, z_aug], dim=0)
        total_samples = 2 * batch_size
        
        # Build a mask to exclude self (each row i should exclude i and i+batch)
        # Result: (batch, total_samples) boolean mask
        mask = torch.ones(batch_size, total_samples, dtype=torch.bool, device=z_orig.device)
        for i in range(batch_size):
            mask[i, i] = False  # Exclude self in original
            mask[i, i + batch_size] = False  # Exclude self in augmented
        
        # For each sample, gather valid negatives
        # We'll take up to n_neg negatives per sample
        n_neg = min(10, total_samples - 2)
        negatives = torch.zeros(batch_size, n_neg, dim, device=z_orig.device)
        
        for i in range(batch_size):
            valid_negs = all_samples[mask[i]]  # (total_samples - 2, dim)
            # Shuffle and take n_neg
            perm = torch.randperm(len(valid_negs))
            negatives[i] = valid_negs[perm[:n_neg]]
        
        return negatives
