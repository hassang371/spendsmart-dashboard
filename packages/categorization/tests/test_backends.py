"""Tests for backend base class."""
import pytest
import torch
from packages.categorization.backends.base import BackendBase


class MockBackend(BackendBase):
    """Mock implementation for testing."""

    def __init__(self):
        self._dim = 768

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def device(self) -> torch.device:
        return torch.device("cpu")

    def embed(self, texts):
        # Return random embeddings for testing
        return torch.randn(len(texts), self._dim)


def test_backend_base_is_abstract():
    """BackendBase should be abstract and require implementation."""
    with pytest.raises(TypeError):
        BackendBase()  # Cannot instantiate abstract class


def test_mock_backend_implements_interface():
    """Mock backend should implement all abstract methods."""
    backend = MockBackend()

    assert backend.dim == 768
    assert isinstance(backend.device, torch.device)

    # Test embed
    texts = ["test 1", "test 2"]
    embeddings = backend.embed(texts)
    assert embeddings.shape == (2, 768)
