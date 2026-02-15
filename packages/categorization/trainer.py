import torch
import geoopt
from .losses import HyperbolicDistanceLoss, CosineLoss


class HypCDTrainer:
    def __init__(self, model, lr=0.01, c=1.0):
        self.model = model
        self.c = c
        self.manifold = geoopt.PoincareBall(c=c)

        # Loss Functions
        self.hyp_loss = HyperbolicDistanceLoss(c=c)
        self.cosine_loss = CosineLoss()

        # Optimizer: RiemannianAdam
        # Ensure model needs gradients
        # HypLinear bias is ManifoldParameter, handled automatically by geoopt.optim
        self.optimizer = geoopt.optim.RiemannianAdam(model.parameters(), lr=lr)

    def train_step(self, anchor, positive, target):
        """
        Single training step.
        anchor: [Batch, Dim]
        positive: [Batch, Dim]
        target: [Batch] (1 for pos, -1/0 for neg)
        """
        self.model.train()
        self.optimizer.zero_grad()

        # Forward pass
        # We assume the model handles the input correctly (whether raw or hyperbolic)
        # In our architecture, if passing raw text embeddings, we might need Projector first.
        # But for this class, we assume 'anchor' and 'positive' are inputs compatible with 'model'.

        z_anchor = self.model(anchor)
        z_positive = self.model(positive)

        # Calculate Losses
        # 1. Hyperbolic Distance Loss
        l_hyp = self.hyp_loss(z_anchor, z_positive, target)

        # 2. Cosine Loss
        l_cos = self.cosine_loss(z_anchor, z_positive, target)

        # Hybrid Weighting (dynamic ramping mentioned in paper, but static for now)
        # alpha * L_hyp + beta * L_cos
        total_loss = l_hyp + 0.1 * l_cos

        # Backward
        total_loss.backward()

        # Optimizer step (Riemannian)
        self.optimizer.step()

        return total_loss.item()

    def train(self, dataloader, epochs=5):
        """
        Training loop.
        dataloader: Iterable yielding (anchor, positive, target)
        """
        metrics = {"loss": []}

        for epoch in range(epochs):
            epoch_loss = 0.0
            count = 0

            for batch in dataloader:
                anchor, positive, target = batch
                if len(anchor) == 0:
                    continue

                loss = self.train_step(anchor, positive, target)
                epoch_loss += loss
                count += 1

            avg_loss = epoch_loss / count if count > 0 else 0
            metrics["loss"].append(avg_loss)
            print(f"Epoch {epoch+1}/{epochs}: Loss = {avg_loss:.4f}")

        self.save_checkpoint("final_model.pt")
        return metrics

    def save_checkpoint(self, path):
        torch.save(self.model.state_dict(), path)

    def train_supervised_step(self, text_emb, target_anchor):
        """
        Supervised step.
        text_emb: [Batch, Dim] (Euclidean BERT embedding)
        target_anchor: [Batch, Dim] (Hyperbolic Centroid)
        """
        self.model.train()
        self.optimizer.zero_grad()

        # 1. Project Text to Manifold
        z_text = self.model(text_emb)

        # 2. Target is already on manifold (Anchor)
        z_target = target_anchor

        # 3. Minimize Distance
        # We want z_text to be close to z_target.
        dist = self.model.manifold.dist(z_text, z_target)

        # Simple distance loss
        loss = dist.mean()

        loss.backward()
        self.optimizer.step()

        return loss.item()

    def train_supervised(self, dataloader, epochs=5):
        metrics = {"loss": []}
        for epoch in range(epochs):
            epoch_loss = 0.0
            count = 0
            for batch in dataloader:
                text_emb, target_anchor = batch
                loss = self.train_supervised_step(text_emb, target_anchor)
                epoch_loss += loss
                count += 1

            avg_loss = epoch_loss / count if count > 0 else 0
            metrics["loss"].append(avg_loss)
            print(f"Epoch {epoch+1}/{epochs} (Supervised): Loss = {avg_loss:.4f}")

        return metrics
