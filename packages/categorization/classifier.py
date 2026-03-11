"""Transaction classifier v2: Frozen MiniLM + Cosine Similarity + Linear Adapter.

Architecture:
  1. KeywordMatcher (rules.py) — O(1) deterministic match for known merchants
  2. Frozen MiniLM embeddings — semantic vector for each transaction
  3. Cosine similarity — compare transaction embedding against category anchors
  4. Linear Adapter — per-user trainable layer for personalized classification

The base MiniLM model is NEVER trained. Only the tiny Linear Adapter
is updated when a user reclassifies transactions.
"""

import os

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    import structlog

    logger = structlog.get_logger()
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from typing import Optional

from sentence_transformers import SentenceTransformer

from packages.categorization.cleaner import process_description
from packages.categorization.constants import DEFAULT_CATEGORY_KEYWORDS, Category
from packages.categorization.rules import KeywordMatcher

# Configurable confidence threshold (lowered from 0.90 to 0.75)
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.75"))


class LinearAdapter(nn.Module):
    """Per-user linear classification head.

    Trained only on user reclassification corrections.
    Tiny (~10KB) — syncs between cloud and mobile.
    """

    def __init__(self, input_dim: int, num_classes: int, dropout: float = 0.3):
        super().__init__()
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(input_dim, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(x)


class TransactionClassifier:
    """Lightweight transaction classifier.

    Uses frozen MiniLM for embeddings and cosine similarity against
    category anchors for zero-shot classification.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        confidence_threshold: Optional[float] = None,
    ):
        self._model_name = model_name
        self.confidence_threshold = confidence_threshold or CONFIDENCE_THRESHOLD
        self._keyword_matcher = KeywordMatcher()

        # Load frozen embedding model
        self._model = SentenceTransformer(model_name)
        self._model.eval()
        self.embedding_dim = self._model.get_sentence_embedding_dimension()

        # Build category anchors (pre-computed embeddings for each category)
        self._category_names: list[str] = []
        self._category_anchors: Optional[torch.Tensor] = None
        self._build_category_anchors()

        logger.info(
            "classifier_initialized",
            model=model_name,
            dim=self.embedding_dim,
            categories=len(self._category_names),
            threshold=self.confidence_threshold,
        )

    def _build_category_anchors(self) -> None:
        """Pre-compute mean embeddings for each category from seed phrases."""
        category_embeddings = []
        self._category_names = []

        for cat in Category:
            seeds = DEFAULT_CATEGORY_KEYWORDS.get(cat.value, [])
            if not seeds:
                continue

            # Encode all seed phrases and average them into a single anchor
            embeddings = self._model.encode(seeds, convert_to_tensor=True)
            anchor = embeddings.mean(dim=0)
            anchor = F.normalize(anchor, dim=0)  # unit normalize for cosine sim

            category_embeddings.append(anchor)
            self._category_names.append(cat.value)

        self._category_anchors = torch.stack(category_embeddings)

    def _cosine_classify(self, embeddings: torch.Tensor) -> list[dict]:
        """Classify embeddings via cosine similarity against category anchors.

        Args:
            embeddings: Tensor of shape (batch_size, dim)

        Returns:
            List of {"category": str, "confidence": float}
        """
        # Normalize input embeddings
        normed = F.normalize(embeddings, dim=1)

        # Cosine similarity: (batch, dim) @ (dim, n_categories) = (batch, n_categories)
        similarities = normed @ self._category_anchors.T

        # Convert to probabilities via softmax (temperature-scaled)
        temperature = 0.1  # Sharp distribution
        probs = F.softmax(similarities / temperature, dim=1)

        results = []
        for i in range(probs.shape[0]):
            best_idx = probs[i].argmax().item()
            best_prob = probs[i][best_idx].item()
            best_category = self._category_names[best_idx]

            results.append(
                {
                    "category": best_category,
                    "confidence": round(best_prob, 4),
                }
            )

        return results

    def _adapter_classify(self, embeddings: torch.Tensor, adapter: LinearAdapter) -> list[dict]:
        """Classify embeddings using a user-specific trained adapter."""
        adapter.eval()
        with torch.no_grad():
            logits = adapter(embeddings)
            probs = F.softmax(logits, dim=1)

        results = []
        for i in range(probs.shape[0]):
            best_idx = probs[i].argmax().item()
            best_prob = probs[i][best_idx].item()
            best_category = self._category_names[best_idx]

            results.append(
                {
                    "category": best_category,
                    "confidence": round(best_prob, 4),
                }
            )
        return results

    def predict(self, text: str, adapter: Optional[LinearAdapter] = None) -> dict:
        """Classify a single transaction description.

        Args:
            text: Raw or informative transaction description.

        Returns:
            {"category": str, "confidence": float}
        """
        results = self.predict_batch([text], adapter=adapter)
        return results[0]

    def predict_batch(self, texts: list[str], adapter: Optional[LinearAdapter] = None) -> list[dict]:
        """Classify a batch of transaction descriptions.

        Pipeline:
          1. Process text through cleaner for informative representation
          2. Check keyword rules for deterministic match
          3. Embed remaining with MiniLM
          4. Cosine similarity classification

        Args:
            texts: List of raw transaction descriptions.

        Returns:
            List of {"category": str, "confidence": float}
        """
        if not texts:
            return []

        results: list[Optional[dict]] = [None] * len(texts)
        remaining_indices: list[int] = []
        remaining_texts: list[str] = []

        for i, text in enumerate(texts):
            if not text or not text.strip():
                results[i] = {
                    "category": Category.UNCATEGORIZED.value,
                    "confidence": 0.0,
                }
                continue

            # Process through cleaner
            processed = process_description(text)
            informative = processed.informative

            # Try keyword rules first (O(1) deterministic match)
            rule_match = self._keyword_matcher.predict(informative)
            if rule_match:
                results[i] = rule_match
                continue

            # Also try matching on the raw text (fallback)
            rule_match_raw = self._keyword_matcher.predict(text)
            if rule_match_raw:
                results[i] = rule_match_raw
                continue

            # Queue for neural network classification
            remaining_indices.append(i)
            remaining_texts.append(informative if informative else text)

        # Batch embed and classify remaining texts
        if remaining_texts:
            with torch.no_grad():
                embeddings = self._model.encode(remaining_texts, convert_to_tensor=True)
                if adapter is not None:
                    cosine_results = self._adapter_classify(embeddings, adapter)
                else:
                    cosine_results = self._cosine_classify(embeddings)

            for idx, cosine_result in zip(remaining_indices, cosine_results):
                results[idx] = cosine_result

        return results

    def train_adapter(
        self,
        texts: list[str],
        categories: list[str],
        epochs: int = 5,
        lr: float = 1e-3,
    ) -> LinearAdapter:
        """Train a linear adapter on user corrections.

        Args:
            texts: Transaction descriptions (informative text preferred).
            categories: Corrected category labels.
            epochs: Number of training epochs.
            lr: Learning rate.

        Returns:
            Trained LinearAdapter ready for saving.
        """
        # Map category names to indices
        cat_to_idx = {name: i for i, name in enumerate(self._category_names)}
        valid_pairs = [(t, cat_to_idx[c]) for t, c in zip(texts, categories) if c in cat_to_idx]

        if not valid_pairs:
            logger.warning("no_valid_corrections_for_adapter")
            return LinearAdapter(self.embedding_dim, len(self._category_names))

        train_texts, train_labels = zip(*valid_pairs)

        # Encode texts
        with torch.no_grad():
            embeddings = self._model.encode(list(train_texts), convert_to_tensor=True)

        labels = torch.tensor(list(train_labels), dtype=torch.long)

        # Train adapter
        adapter = LinearAdapter(self.embedding_dim, len(self._category_names))
        optimizer = torch.optim.AdamW(adapter.parameters(), lr=lr, weight_decay=1e-4)

        adapter.train()
        for epoch in range(epochs):
            logits = adapter(embeddings)
            loss = F.cross_entropy(logits, labels)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        adapter.eval()
        logger.info(
            "adapter_trained",
            corrections=len(train_texts),
            epochs=epochs,
            final_loss=round(loss.item(), 4),
        )
        return adapter
