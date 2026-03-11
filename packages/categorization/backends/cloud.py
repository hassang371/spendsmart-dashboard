# packages/categorization/backends/cloud.py
"""Cloud backend using MiniLM for lightweight, high-accuracy embeddings.

Uses sentence-transformers/all-MiniLM-L6-v2 (22MB, 384-dim) for
maximum portability across cloud, web, and mobile platforms.
"""

from typing import List

import torch
from sentence_transformers import SentenceTransformer

from .base import BackendBase


class CloudBackend(BackendBase):
    """Cloud backend using MiniLM for semantic embeddings.

    Uses all-MiniLM-L6-v2 (22MB, 384-dim) — lightweight and mobile-ready.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        dim: int = 384,
    ):
        self._dim = dim
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        if torch.backends.mps.is_available():
            self._device = torch.device("mps")

        self._model = SentenceTransformer(model_name)
        self._model.eval()

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def device(self) -> torch.device:
        return self._device

    def embed(self, texts: List[str]) -> torch.Tensor:
        """Embed texts using MiniLM with mean pooling.

        Args:
            texts: List of text strings

        Returns:
            Tensor of shape (batch_size, 384) with sentence embeddings
        """
        embeddings = self._model.encode(texts, convert_to_tensor=True, show_progress_bar=False)
        return embeddings.to(self._device)

    def embed_batch(self, texts: List[str]) -> torch.Tensor:
        """Alias for embed() — MiniLM handles batching natively."""
        return self.embed(texts)
