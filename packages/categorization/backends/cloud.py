# packages/categorization/backends/cloud.py
import torch
from transformers import BertTokenizer, BertModel
from typing import List

from .base import BackendBase


class CloudBackend(BackendBase):
    """
    Cloud backend using BERT for high-accuracy embeddings.

    Uses bert-base-uncased (110M parameters) for maximum accuracy.
    Deployed on Modal with GPU acceleration.
    """

    def __init__(self, model_name: str = "bert-base-uncased", dim: int = 768):
        """
        Initialize BERT backend.

        Args:
            model_name: HuggingFace model name (default: bert-base-uncased)
            dim: Output dimension (768 for BERT base)
        """
        self._dim = dim
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Handle MPS (Mac)
        if torch.backends.mps.is_available():
            self._device = torch.device("mps")

        # Load tokenizer and model
        self.tokenizer = BertTokenizer.from_pretrained(model_name)
        self.model = BertModel.from_pretrained(model_name).to(self._device)
        self.model.eval()  # Inference mode

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def device(self) -> torch.device:
        return self._device

    def embed(self, texts: List[str]) -> torch.Tensor:
        """
        Embed texts using BERT [CLS] token.

        Args:
            texts: List of text strings

        Returns:
            Tensor of shape (batch_size, dim) with BERT [CLS] embeddings
        """
        # Tokenize
        inputs = self.tokenizer(
            texts, return_tensors="pt", padding=True, truncation=True, max_length=128
        ).to(self._device)

        # Get [CLS] embeddings
        with torch.no_grad():
            outputs = self.model(**inputs)
            # Use [CLS] token representation (first token)
            cls_embeddings = outputs.last_hidden_state[:, 0, :]

        return cls_embeddings

    def embed_batch(self, texts: List[str]) -> torch.Tensor:
        """Alias for embed() - CloudBackend already handles batching."""
        return self.embed(texts)
