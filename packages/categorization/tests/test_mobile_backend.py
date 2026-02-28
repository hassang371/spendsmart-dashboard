"""Tests for mobile backend with DistilBERT."""
import torch
from packages.categorization.backends.mobile import MobileBackend


def test_mobile_backend_init():
    """MobileBackend should initialize with DistilBERT."""
    backend = MobileBackend()

    assert backend.dim == 768
    assert isinstance(backend.device, torch.device)


def test_mobile_backend_embed():
    """MobileBackend should embed texts to correct dimension."""
    backend = MobileBackend()

    texts = ["food delivery", "taxi ride"]
    embeddings = backend.embed(texts)

    assert embeddings.shape == (2, 768)
    assert not torch.isnan(embeddings).any()
