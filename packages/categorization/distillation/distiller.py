"""
Knowledge Distillation for HypCD.

Implements distillation from teacher (Cloud BERT-768) to student (Mobile DistilBERT-384).
Combines:
1. Embedding MSE: Match hyperbolic embeddings
2. Logit KL: Match softened class distributions

Temperature τ softens probabilities:
    p_i = exp(z_i / τ) / Σ_j exp(z_j / τ)

Distillation loss:
    L_distill = α * KL(p_teacher || p_student) + (1-α) * MSE(embed_teacher, embed_student)
"""

import torch
import torch.nn.functional as F
from typing import List, Optional
from geoopt import PoincareBall

from ..hypcd import HyperbolicProjector, HypFFN


class KnowledgeDistiller:
    """
    Distills knowledge from teacher to student for HypCD.

    The teacher is typically a larger model (BERT-768) with higher accuracy.
    The student is a smaller model (DistilBERT-384) for mobile deployment.

    Args:
        teacher: Teacher backend (CloudBackend)
        student: Student backend (MobileBackend)
        proj_dim: Projected dimension for hyperbolic space (default: 128)
        num_classes: Number of output classes (default: 11)
        temperature: Softmax temperature for distillation (default: 4.0)
        alpha: Weight for distillation loss vs embedding loss (default: 0.7)
        device: Device for computation
    """

    def __init__(
        self,
        teacher,
        student,
        proj_dim: int = 128,
        num_classes: int = 11,
        temperature: float = 4.0,
        alpha: float = 0.7,
        device: str = "cpu",
    ):
        self.teacher = teacher
        self.student = student
        self.proj_dim = proj_dim
        self.num_classes = num_classes
        self.temperature = temperature
        self.alpha = alpha
        self.device = torch.device(device)
        self.manifold = PoincareBall(c=1.0)

        # Initialize projectors
        self.teacher_projector = HyperbolicProjector(
            input_dim=teacher.dim, hidden_dim=256, output_dim=proj_dim
        ).to(self.device)

        self.student_projector = HyperbolicProjector(
            input_dim=student.dim, hidden_dim=256, output_dim=proj_dim
        ).to(self.device)

        # Initialize classifiers
        self.teacher_classifier = HypFFN(
            dim=proj_dim, num_classes=num_classes, manifold=self.manifold
        ).to(self.device)

        self.student_classifier = HypFFN(
            dim=proj_dim, num_classes=num_classes, manifold=self.manifold
        ).to(self.device)

        # Optimizer for student components
        self.optimizer = torch.optim.Adam(
            list(self.student_projector.parameters())
            + list(self.student_classifier.parameters()),
            lr=1e-4,
        )

    def distillation_loss(
        self, teacher_logits: torch.Tensor, student_logits: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute KL divergence loss between softened distributions.

        Args:
            teacher_logits: Teacher model logits (batch_size, num_classes)
            student_logits: Student model logits (batch_size, num_classes)

        Returns:
            KL divergence loss
        """
        # Softmax with temperature
        teacher_probs = F.softmax(teacher_logits / self.temperature, dim=-1)
        student_log_probs = F.log_softmax(student_logits / self.temperature, dim=-1)

        # KL divergence
        kl_loss = F.kl_div(student_log_probs, teacher_probs, reduction="batchmean") * (
            self.temperature**2
        )  # Scale by T^2 as per Hinton et al.

        return kl_loss

    def embedding_mse_loss(
        self, teacher_embeddings: torch.Tensor, student_embeddings: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute MSE loss between teacher and student hyperbolic embeddings.

        Note: We compare embeddings in the tangent space (Euclidean) for stability.

        Args:
            teacher_embeddings: Teacher hyperbolic embeddings (batch_size, proj_dim)
            student_embeddings: Student hyperbolic embeddings (batch_size, proj_dim)

        Returns:
            MSE loss
        """
        # Map to tangent space at origin for comparison
        teacher_tan = self.manifold.logmap0(teacher_embeddings)
        student_tan = self.manifold.logmap0(student_embeddings)

        # MSE in tangent space
        mse_loss = F.mse_loss(student_tan, teacher_tan)

        return mse_loss

    def distill_step(self, texts: List[str]) -> float:
        """
        Perform one distillation step.

        Args:
            texts: List of text samples

        Returns:
            Loss value
        """
        self.optimizer.zero_grad()

        # Get embeddings from backends
        with torch.no_grad():
            teacher_euclidean = self.teacher.embed_batch(texts)
        student_euclidean = self.student.embed_batch(texts)

        # Project to hyperbolic space
        with torch.no_grad():
            teacher_hyperbolic = self.teacher_projector(teacher_euclidean)
        student_hyperbolic = self.student_projector(student_euclidean)

        # Get logits from classifiers
        with torch.no_grad():
            teacher_logits_tan = self.teacher_classifier(teacher_hyperbolic)
            teacher_logits = self.manifold.logmap0(teacher_logits_tan)

        student_logits_tan = self.student_classifier(student_hyperbolic)
        student_logits = self.manifold.logmap0(student_logits_tan)

        # Compute losses
        distill_loss = self.distillation_loss(teacher_logits, student_logits)
        embed_loss = self.embedding_mse_loss(teacher_hyperbolic, student_hyperbolic)

        # Combined loss
        total_loss = self.alpha * distill_loss + (1 - self.alpha) * embed_loss

        # Backpropagation
        total_loss.backward()
        self.optimizer.step()

        return total_loss.item()

    def distill_epoch(self, batches: List[List[str]]) -> float:
        """
        Distill for one epoch over multiple batches.

        Args:
            batches: List of text batches

        Returns:
            Average loss
        """
        self.student_projector.train()
        self.student_classifier.train()

        total_loss = 0.0
        num_batches = 0

        for batch_texts in batches:
            if not batch_texts:
                continue

            loss = self.distill_step(batch_texts)
            total_loss += loss
            num_batches += 1

        avg_loss = total_loss / max(num_batches, 1)
        return avg_loss

    def save_student(self, path: str):
        """
        Save distilled student model components.

        Args:
            path: Path to save checkpoint
        """
        checkpoint = {
            "student_projector": self.student_projector.state_dict(),
            "student_classifier": self.student_classifier.state_dict(),
            "proj_dim": self.proj_dim,
            "num_classes": self.num_classes,
            "temperature": self.temperature,
            "alpha": self.alpha,
        }
        torch.save(checkpoint, path)

    def load_student(self, path: str):
        """
        Load distilled student model components.

        Args:
            path: Path to checkpoint
        """
        checkpoint = torch.load(path, map_location=self.device)
        self.student_projector.load_state_dict(checkpoint["student_projector"])
        self.student_classifier.load_state_dict(checkpoint["student_classifier"])

    def evaluate(self, texts: List[str], labels: Optional[torch.Tensor] = None) -> dict:
        """
        Evaluate student model on validation data.

        Args:
            texts: List of text samples
            labels: Optional ground truth labels

        Returns:
            Dictionary with evaluation metrics
        """
        self.student_projector.eval()
        self.student_classifier.eval()

        with torch.no_grad():
            # Get student predictions
            student_euclidean = self.student.embed_batch(texts)
            student_hyperbolic = self.student_projector(student_euclidean)
            student_logits_tan = self.student_classifier(student_hyperbolic)
            student_logits = self.manifold.logmap0(student_logits_tan)
            student_preds = student_logits.argmax(dim=-1)

            # Get teacher predictions for comparison
            teacher_euclidean = self.teacher.embed_batch(texts)
            teacher_hyperbolic = self.teacher_projector(teacher_euclidean)
            teacher_logits_tan = self.teacher_classifier(teacher_hyperbolic)
            teacher_logits = self.manifold.logmap0(teacher_logits_tan)
            teacher_preds = teacher_logits.argmax(dim=-1)

            # Agreement rate
            agreement = (student_preds == teacher_preds).float().mean().item()

            metrics = {
                "teacher_student_agreement": agreement,
                "num_samples": len(texts),
            }

            # If labels provided, compute accuracy
            if labels is not None:
                student_acc = (student_preds == labels).float().mean().item()
                teacher_acc = (teacher_preds == labels).float().mean().item()
                metrics["student_accuracy"] = student_acc
                metrics["teacher_accuracy"] = teacher_acc

        return metrics
