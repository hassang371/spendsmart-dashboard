"""AdapterManager — load/save per-user Linear Adapter weights.

Storage priority:
  1. Supabase Storage bucket "models" (production)
  2. Local filesystem under local_dir (dev/fallback)

v2: Manages Linear Adapter weights only (~10KB per user).
Removed: contrastive pretraining, HypCD references, hybrid loss.
"""

import io
import os

import torch

try:
    import structlog

    logger = structlog.get_logger()
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

_BUCKET = "models"


class AdapterManager:
    """Manages checkpoint persistence for per-user Linear Adapters."""

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        local_dir: str = "checkpoints",
    ):
        self._supabase_url = supabase_url or os.getenv("SUPABASE_URL", "")
        self._supabase_key = supabase_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self._local_dir = local_dir
        os.makedirs(local_dir, exist_ok=True)

    @property
    def _storage(self):
        from supabase import create_client

        return create_client(self._supabase_url, self._supabase_key).storage

    # ── Load / Save Helpers ──────────────────────────────────────────

    def _load_from_path(self, storage_path: str) -> dict | None:
        """Load state dict from Supabase Storage, falling back to local."""
        # Try Supabase first
        if self._supabase_url and self._supabase_key:
            try:
                data = self._storage.from_(_BUCKET).download(storage_path)
                buf = io.BytesIO(data)
                return torch.load(buf, map_location="cpu", weights_only=True)
            except Exception:
                pass

        # Local fallback
        local_path = os.path.join(self._local_dir, storage_path)
        if os.path.exists(local_path):
            return torch.load(local_path, map_location="cpu", weights_only=True)

        return None

    def _save_to_path(self, storage_path: str, state: dict) -> None:
        """Save state dict locally first, then upload to Supabase Storage."""
        local_path = os.path.join(self._local_dir, storage_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        torch.save(state, local_path)

        if self._supabase_url and self._supabase_key:
            try:
                buf = io.BytesIO()
                torch.save(state, buf)
                buf.seek(0)
                self._storage.from_(_BUCKET).upload(
                    storage_path,
                    buf.read(),
                    file_options={
                        "content-type": "application/octet-stream",
                        "upsert": "true",
                    },
                )
            except Exception as e:
                logger.warning("supabase_upload_failed", path=storage_path, error=str(e))

    # ── Public API ───────────────────────────────────────────────────
    # Note: No global base model checkpoint needed in v2.
    # MiniLM is frozen and loaded from HuggingFace/cache.
    # Only per-user adapter weights are persisted.

    def load_user_adapter(self, user_id: str) -> dict | None:
        """Load per-user adapter weights."""
        return self._load_from_path(f"users/{user_id}/adapter.pt")

    def save_user_adapter(self, user_id: str, state: dict) -> None:
        """Persist per-user adapter weights."""
        self._save_to_path(f"users/{user_id}/adapter.pt", state)

    def fine_tune_supervised(
        self,
        texts: list[str],
        categories: list[str],
        epochs: int = 5,
    ) -> dict | None:
        """Train a Linear Adapter from labeled user corrections.

        Uses the TransactionClassifier singleton to generate embeddings
        and train a small classification head.

        Returns:
            State dict of the trained adapter, or None if no valid corrections.
        """
        from packages.categorization.classifier import TransactionClassifier

        classifier = TransactionClassifier()
        adapter = classifier.train_adapter(
            texts=texts,
            categories=categories,
            epochs=epochs,
        )
        return adapter.state_dict()
