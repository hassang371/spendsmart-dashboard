import torch
import torch.nn as nn
import geoopt


class HyperbolicDistanceLoss(nn.Module):
    """
    Minimizes hyperbolic distance between positive pairs.
    Can be used as a contrastive loss or simple regression.
    """

    def __init__(self, c=1.0, margin=0.1):
        super().__init__()
        self.c = c
        self.margin = margin
        self.manifold = geoopt.PoincareBall(c=c)

    def forward(self, input1, input2, target):
        """
        input1, input2: Embeddings in Poincaré ball
        target: 1 for positive pair (pull together), -1 for negative (push apart)
        """
        dist = self.manifold.dist(input1, input2)

        # Contrastive Loss
        # If target == 1: loss = dist^2
        # If target == -1: loss = max(0, margin - dist)^2

        loss_pos = dist.pow(2)
        loss_neg = torch.clamp(self.margin - dist, min=0.0).pow(2)

        # Create mask
        # Target usually {1, -1} or {1, 0}
        # Assuming target 1 = positive

        target_pos = (target == 1).float()
        target_neg = (target != 1).float()

        loss = target_pos * loss_pos + target_neg * loss_neg
        return loss.mean()


class CosineLoss(nn.Module):
    """
    Optimizes cosine similarity (angle) in the embedding space (viewed from origin).
    """

    def __init__(self):
        super().__init__()
        self.cosine_sim = nn.CosineSimilarity(dim=-1)
        self.mse = nn.MSELoss()

    def forward(self, input1, input2, target):
        """
        Maximizes cosine similarity for positive pairs.
        Minimizes for negative pairs?
        Target should be 1.0 for positive, -1.0 (or 0) for negative.
        """
        sim = self.cosine_sim(input1, input2)

        # Loss = MSE(sim, target)
        # If target is 1, we want sim -> 1
        # If target is -1, we want sim -> -1 (opposite)
        # If target is 0, we want sim -> 0 (orthogonal)

        return self.mse(sim, target)
