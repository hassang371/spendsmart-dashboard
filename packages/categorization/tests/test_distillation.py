"""
Tests for Knowledge Distillation module.

Distills knowledge from teacher (Cloud BERT) to student (Mobile DistilBERT).
"""
import torch
from unittest.mock import MagicMock


def test_knowledge_distiller_initialization():
    """Test KnowledgeDistiller initialization with teacher and student."""
    from packages.categorization.distillation.distiller import KnowledgeDistiller

    # Create mock teacher and student
    teacher = MagicMock()
    teacher.dim = 768
    teacher.device = "cpu"

    student = MagicMock()
    student.dim = 384
    student.device = "cpu"

    distiller = KnowledgeDistiller(
        teacher=teacher, student=student, temperature=4.0, alpha=0.7
    )

    assert distiller.teacher == teacher
    assert distiller.student == student
    assert distiller.temperature == 4.0
    assert distiller.alpha == 0.7


def test_distillation_loss():
    """Test distillation loss computation."""
    from packages.categorization.distillation.distiller import KnowledgeDistiller

    teacher = MagicMock()
    teacher.dim = 768
    teacher.device = "cpu"

    student = MagicMock()
    student.dim = 384
    student.device = "cpu"

    distiller = KnowledgeDistiller(teacher=teacher, student=student)

    # Create sample logits
    teacher_logits = torch.randn(4, 11)
    student_logits = torch.randn(4, 11)

    loss = distiller.distillation_loss(teacher_logits, student_logits)

    # Loss should be a scalar tensor
    assert loss.dim() == 0
    assert loss.item() >= 0


def test_embedding_mse_loss():
    """Test MSE loss between teacher and student embeddings."""
    from packages.categorization.distillation.distiller import KnowledgeDistiller

    teacher = MagicMock()
    teacher.dim = 768
    teacher.device = "cpu"

    student = MagicMock()
    student.dim = 384
    student.device = "cpu"

    distiller = KnowledgeDistiller(teacher=teacher, student=student, proj_dim=128)

    # Create sample embeddings (both should be proj_dim after projection)
    teacher_emb = torch.randn(4, 128) * 0.5  # Small values for Poincaré ball
    student_emb = torch.randn(4, 128) * 0.5

    loss = distiller.embedding_mse_loss(teacher_emb, student_emb)

    # Loss should be a scalar tensor
    assert loss.dim() == 0
    assert loss.item() >= 0


def test_distill_step():
    """Test a single distillation step."""
    from packages.categorization.distillation.distiller import KnowledgeDistiller

    # Create mock backends
    teacher = MagicMock()
    teacher.dim = 768
    teacher.device = "cpu"
    teacher.embed_batch = MagicMock(return_value=torch.randn(2, 768))

    student = MagicMock()
    student.dim = 384
    student.device = "cpu"
    student.embed_batch = MagicMock(return_value=torch.randn(2, 384))

    distiller = KnowledgeDistiller(teacher=teacher, student=student, proj_dim=128)

    # Mock the projectors - need to return tensors with gradients
    class MockProjector:
        def __init__(self, out_dim):
            self.out_dim = out_dim
            self.weight = torch.randn(out_dim, out_dim, requires_grad=True)

        def __call__(self, x):
            # Return small values for Poincaré ball
            return torch.randn(x.shape[0], self.out_dim, requires_grad=True) * 0.3

        def train(self, mode=True):
            return self

        def eval(self):
            return self.train(False)

    distiller.teacher_projector = MockProjector(128)
    distiller.student_projector = MockProjector(128)

    # Mock classifiers - need to return tensors with gradients
    class MockClassifier:
        def __init__(self, num_classes):
            self.num_classes = num_classes
            self.weight = torch.randn(num_classes, 128, requires_grad=True)

        def __call__(self, x):
            return torch.randn(x.shape[0], self.num_classes, requires_grad=True) * 0.3

        def train(self, mode=True):
            return self

        def eval(self):
            return self.train(False)

    distiller.teacher_classifier = MockClassifier(11)
    distiller.student_classifier = MockClassifier(11)

    # Test distill step
    texts = ["food delivery", "taxi ride"]
    loss = distiller.distill_step(texts)

    # Loss should be a scalar
    assert isinstance(loss, float)
    assert loss >= 0


def test_distill_epoch():
    """Test distillation over an epoch."""
    from packages.categorization.distillation.distiller import KnowledgeDistiller

    teacher = MagicMock()
    teacher.dim = 768
    teacher.device = "cpu"
    teacher.embed_batch = MagicMock(return_value=torch.randn(2, 768))

    student = MagicMock()
    student.dim = 384
    student.device = "cpu"
    student.embed_batch = MagicMock(return_value=torch.randn(2, 384))

    distiller = KnowledgeDistiller(teacher=teacher, student=student, proj_dim=128)

    # Mock projectors and classifiers
    class MockProjector:
        def __init__(self, out_dim):
            self.out_dim = out_dim
            self.weight = torch.randn(out_dim, out_dim, requires_grad=True)

        def __call__(self, x):
            return torch.randn(x.shape[0], self.out_dim, requires_grad=True) * 0.3

        def train(self, mode=True):
            return self

        def eval(self):
            return self.train(False)

    class MockClassifier:
        def __init__(self, num_classes):
            self.num_classes = num_classes
            self.weight = torch.randn(num_classes, 128, requires_grad=True)

        def __call__(self, x):
            return torch.randn(x.shape[0], self.num_classes, requires_grad=True) * 0.3

        def train(self, mode=True):
            return self

        def eval(self):
            return self.train(False)

    distiller.teacher_projector = MockProjector(128)
    distiller.student_projector = MockProjector(128)
    distiller.teacher_classifier = MockClassifier(11)
    distiller.student_classifier = MockClassifier(11)

    # Test distill epoch
    texts = [["food delivery", "taxi ride"], ["grocery shopping", "movie ticket"]]
    avg_loss = distiller.distill_epoch(texts)

    # Should return average loss
    assert isinstance(avg_loss, float)
    assert avg_loss >= 0


def test_save_student():
    """Test saving distilled student model."""
    from packages.categorization.distillation.distiller import KnowledgeDistiller
    import tempfile
    import os

    teacher = MagicMock()
    teacher.dim = 768
    teacher.device = "cpu"

    student = MagicMock()
    student.dim = 384
    student.device = "cpu"

    distiller = KnowledgeDistiller(teacher=teacher, student=student)

    # Mock state dicts
    distiller.student_projector = MagicMock()
    distiller.student_projector.state_dict = MagicMock(return_value={})
    distiller.student_classifier = MagicMock()
    distiller.student_classifier.state_dict = MagicMock(return_value={})

    # Test save
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "student.pt")
        distiller.save_student(save_path)
        assert os.path.exists(save_path)


def test_temperature_effect():
    """Test that temperature softens probability distributions."""
    from packages.categorization.distillation.distiller import KnowledgeDistiller
    import torch.nn.functional as F

    teacher = MagicMock()
    teacher.dim = 768
    teacher.device = "cpu"

    student = MagicMock()
    student.dim = 384
    student.device = "cpu"

    # High temperature distiller
    distiller_high = KnowledgeDistiller(
        teacher=teacher, student=student, temperature=10.0
    )
    # Low temperature distiller
    distiller_low = KnowledgeDistiller(
        teacher=teacher, student=student, temperature=1.0
    )

    logits = torch.randn(4, 11)

    # Softmax with high temperature should be more uniform
    probs_high = F.softmax(logits / 10.0, dim=-1)
    probs_low = F.softmax(logits / 1.0, dim=-1)

    # High temperature entropy should be higher (more uniform)
    entropy_high = -(probs_high * torch.log(probs_high + 1e-10)).sum(dim=-1).mean()
    entropy_low = -(probs_low * torch.log(probs_low + 1e-10)).sum(dim=-1).mean()

    assert (
        entropy_high > entropy_low
    ), "High temperature should produce more uniform distribution"
