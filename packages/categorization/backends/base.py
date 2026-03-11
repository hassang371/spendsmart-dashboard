# packages/categorization/backends/base.py
from abc import ABC, abstractmethod
from typing import List

import torch


class BackendBase(ABC):
    """Abstract base class for embedding backends.

    Provides interface for generating semantic text embeddings.
    """

    @property
    @abstractmethod
    def dim(self) -> int:
        """Return embedding dimension."""
        pass

    @property
    @abstractmethod
    def device(self) -> torch.device:
        """Return torch device."""
        pass

    @abstractmethod
    def embed(self, texts: List[str]) -> torch.Tensor:
        """Embed texts into Euclidean space.

        Args:
            texts: List of text strings

        Returns:
            Tensor of shape (batch_size, dim) with embeddings
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> torch.Tensor:
        """Batch embed texts. May be identical to embed() for some backends."""
        pass
