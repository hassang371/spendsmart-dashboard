# packages/categorization/backends/mobile.py
import torch
from transformers import DistilBertTokenizer, DistilBertModel
from typing import List

from .base import BackendBase


class MobileBackend(BackendBase):
    """
    Mobile backend using DistilBERT for efficient on-device inference.

    Uses distilbert-base-uncased (66M parameters) - 40% smaller than BERT
    with 97% of performance. Optimized for ONNX export and mobile deployment.
    """

    def __init__(self, model_name: str = "distilbert-base-uncased", dim: int = 768):
        """
        Initialize DistilBERT backend.

        Args:
            model_name: HuggingFace model name (default: distilbert-base-uncased)
            dim: Output dimension (768 for DistilBERT base)
        """
        self._dim = dim
        self._device = torch.device("cpu")  # Mobile targets CPU

        # Load tokenizer and model
        self.tokenizer = DistilBertTokenizer.from_pretrained(model_name)
        self.model = DistilBertModel.from_pretrained(model_name).to(self._device)
        self.model.eval()

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def device(self) -> torch.device:
        return self._device

    def embed(self, texts: List[str]) -> torch.Tensor:
        """
        Embed texts using DistilBERT [CLS] token.

        Args:
            texts: List of text strings

        Returns:
            Tensor of shape (batch_size, dim) with DistilBERT embeddings
        """
        # Tokenize
        inputs = self.tokenizer(
            texts, return_tensors="pt", padding=True, truncation=True, max_length=128
        ).to(self._device)

        # Get [CLS] embeddings
        with torch.no_grad():
            outputs = self.model(**inputs)
            # DistilBERT also uses first token as [CLS]-like representation
            cls_embeddings = outputs.last_hidden_state[:, 0, :]

        return cls_embeddings

    def embed_batch(self, texts: List[str]) -> torch.Tensor:
        """Alias for embed() - MobileBackend already handles batching."""
        return self.embed(texts)
