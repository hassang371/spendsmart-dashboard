# packages/categorization/backends/base.py
from abc import ABC, abstractmethod
from typing import List
import torch


class BackendBase(ABC):
    """
    Abstract base class for HypCD backends.

    Provides interface for both cloud (BERT) and mobile (DistilBERT) backends.
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
        """
        Embed texts into Euclidean space (before hyperbolic projection).

        Args:
            texts: List of text strings

        Returns:
            Tensor of shape (batch_size, dim) with Euclidean embeddings
        """
        pass
