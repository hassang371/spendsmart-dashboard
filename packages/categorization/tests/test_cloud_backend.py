# packages/categorization/tests/test_cloud_backend.py
import torch
from packages.categorization.backends.cloud import CloudBackend


def test_cloud_backend_init():
    """CloudBackend should initialize with BERT model."""
    # Use tiny model for fast testing
    backend = CloudBackend(model_name="prajjwal1/bert-tiny", dim=128)

    assert backend.dim == 128
    assert isinstance(backend.device, torch.device)


def test_cloud_backend_embed():
    """CloudBackend should embed texts to correct dimension."""
    backend = CloudBackend(model_name="prajjwal1/bert-tiny", dim=128)

    texts = ["food delivery", "taxi ride"]
    embeddings = backend.embed(texts)

    assert embeddings.shape == (2, 128)
    assert not torch.isnan(embeddings).any()


def test_cloud_backend_embed_single():
    """CloudBackend should handle single text."""
    backend = CloudBackend(model_name="prajjwal1/bert-tiny", dim=128)

    embedding = backend.embed(["test text"])
    assert embedding.shape == (1, 128)


def test_finbert_model_name():
    """CloudBackend must use ProsusAI/finbert, not bert-base-uncased."""
    import inspect
    from packages.categorization.backends.cloud import CloudBackend
    src = inspect.getsource(CloudBackend.__init__)
    assert "finbert" in src.lower(), (
        "CloudBackend must use ProsusAI/finbert as default model. "
        "Update model_name default to 'ProsusAI/finbert'."
    )
