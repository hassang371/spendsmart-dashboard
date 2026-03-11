"""AdapterManager — load/save/fine-tune per-user model adapters.

Storage priority:
  1. Supabase Storage bucket "models" (production)
  2. Local filesystem under local_dir (dev/fallback)

Adapter = projector state_dict + classifier state_dict (~0.4 MB total).
Global base model stored at: global/base_model.pt
Per-user adapter stored at:  users/{user_id}/adapter.pt
"""

import io
import os
from typing import TYPE_CHECKING

import structlog
import torch

if TYPE_CHECKING:
    from packages.categorization.hypcd import HypCDClassifier

logger = structlog.get_logger()

_BUCKET = "models"


class AdapterManager:
    """Manages checkpoint persistence and per-user adapter fine-tuning."""

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        local_dir: str = "checkpoints",
    ):
        self._supabase_url = supabase_url if supabase_url is not None else os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
        self._supabase_key = (
            supabase_key
            if supabase_key is not None
            else (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", ""))
        )
        self.local_dir = local_dir

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _storage(self):
        from supabase import create_client

        return create_client(self._supabase_url, self._supabase_key).storage

    def _load_from_path(self, storage_path: str) -> dict | None:
        """Load state dict from Supabase Storage, falling back to local."""
        # 1. Supabase Storage
        try:
            if self._supabase_url and self._supabase_key:
                data = self._storage().from_(_BUCKET).download(storage_path)
                return torch.load(io.BytesIO(data), map_location="cpu", weights_only=True)
        except Exception as e:
            logger.debug("adapter_supabase_load_miss", path=storage_path, error=str(e))

        # 2. Local filesystem
        local_path = os.path.join(self.local_dir, storage_path)
        if os.path.exists(local_path):
            return torch.load(local_path, map_location="cpu", weights_only=True)

        return None

    def _save_to_path(self, storage_path: str, state: dict) -> None:
        """Save state dict locally first, then upload to Supabase Storage."""
        buf = io.BytesIO()
        torch.save(state, buf)
        blob = buf.getvalue()

        # Always write locally
        local_path = os.path.join(self.local_dir, storage_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(blob)

        # Best-effort upload to Supabase Storage
        try:
            if self._supabase_url and self._supabase_key:
                self._storage().from_(_BUCKET).upload(
                    path=storage_path,
                    file=blob,
                    file_options={
                        "content-type": "application/octet-stream",
                        "upsert": "true",
                    },
                )
                logger.info("adapter_uploaded", path=storage_path)
        except Exception as e:
            logger.warning("adapter_supabase_upload_failed", path=storage_path, error=str(e))

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def load_global_base(self) -> dict | None:
        """Load global base model checkpoint."""
        return self._load_from_path("global/base_model.pt")

    def save_global_base(self, state: dict) -> None:
        """Save global base model checkpoint."""
        self._save_to_path("global/base_model.pt", state)

    def load_user_adapter(self, user_id: str) -> dict | None:
        """Load per-user adapter weights."""
        return self._load_from_path(f"users/{user_id}/adapter.pt")

    def save_user_adapter(self, user_id: str, state: dict) -> None:
        """Persist per-user adapter weights."""
        self._save_to_path(f"users/{user_id}/adapter.pt", state)

    # ------------------------------------------------------------------ #
    #  Fine-tuning                                                         #
    # ------------------------------------------------------------------ #

    def run_contrastive_pretraining(
        self,
        classifier: "HypCDClassifier",
        texts: list[str],
        epochs: int = 3,
    ) -> None:
        """Unsupervised contrastive pretraining on raw transaction texts.

        Uses augmented positive pairs — no labels required.
        Updates the HyperbolicProjector weights (shared with fine-tuning).
        """
        from packages.categorization.cleaner import TextAugmenter
        from packages.categorization.training import HypCDTrainer

        if len(texts) < 4:
            logger.debug(
                "contrastive_pretraining_skipped",
                reason="too_few_texts",
                count=len(texts),
            )
            return

        augmenter = TextAugmenter(texts)
        trainer = HypCDTrainer(
            projector=classifier.embedder.projector,
            manifold=classifier.manifold,
            lr=1e-4,
        )

        classifier.train()
        try:
            for epoch in range(epochs):
                lw = _lambda_schedule(epoch, epochs)
                augmented = [augmenter.augment(t) for t in texts]

                original_embs = classifier.backend.embed_batch(texts)
                aug_embs = classifier.backend.embed_batch(augmented)

                trainer.train_step(
                    {"original": original_embs, "augmented": aug_embs},
                    lambda_weight=lw,
                )
            logger.info("contrastive_pretraining_complete", epochs=epochs, texts=len(texts))
        finally:
            classifier.eval()

    def fine_tune_supervised(
        self,
        classifier: "HypCDClassifier",
        texts: list[str],
        categories: list[str],
        epochs: int = 5,
    ) -> None:
        """Supervised fine-tuning of projector + HypFFN on labeled examples.

        Called after merchant-batch reclassification with verified (text, category) pairs.
        """
        import torch.nn.functional as F
        from geoopt import PoincareBall

        if not texts or len(texts) != len(categories):
            return

        label_map = {label: i for i, label in enumerate(classifier.labels)}
        indices = [label_map.get(c, len(classifier.labels) - 1) for c in categories]

        from packages.categorization.training import HypCDTrainer

        device = classifier.backend.device
        labels = torch.tensor(indices, dtype=torch.long, device=device)
        manifold = PoincareBall(c=1.0)

        trainer = HypCDTrainer(
            projector=classifier.embedder.projector,
            manifold=classifier.manifold,
            lr=1e-4,
        )

        classifier.train()
        try:
            embeddings = classifier.backend.embed_batch(texts)

            for epoch in range(epochs):
                trainer.optimizer.zero_grad()
                hyp_embs = classifier.embedder.projector(embeddings)
                logits = classifier.classifier(hyp_embs)
                logits_tan = manifold.logmap0(logits)
                loss = F.cross_entropy(logits_tan, labels)
                loss.backward()
                trainer.optimizer.step()

            logger.info("supervised_finetuning_complete", epochs=epochs, examples=len(texts))
        finally:
            classifier.eval()


# ------------------------------------------------------------------ #
#  Shared helpers                                                      #
# ------------------------------------------------------------------ #


def _lambda_schedule(epoch: int, total_epochs: int) -> float:
    """Dynamic lambda for hybrid loss: ramp from 0->0.5 over first 20% of epochs.

    Per §3.6.2: start with angle optimization (easier convergence), then
    gradually enforce hyperbolic distance structure.
    """
    warmup = max(1, int(0.2 * total_epochs))
    if epoch < warmup:
        return 0.5 * (epoch / warmup)
    return 0.5
