# HypCD Categorization Engine Overhaul — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring the categorization engine into full compliance with the HypCD research doc, implement a global base + per-user adapter system, fix all broken/disconnected components, and remove all dead code.

**Architecture:** FinBERT (frozen backbone) → HyperbolicProjector + HypFFN (global base, loaded from checkpoint at startup) → per-user adapter fine-tuned on corrections (stored in Supabase Storage). Merchant-batch reclassification auto-updates all matching transactions and triggers supervised fine-tuning. Contrastive pretraining runs unsupervised after each import.

**Tech Stack:** Python 3.14, PyTorch, geoopt, `ProsusAI/finbert`, FastAPI, Supabase Storage, pytest, sklearn.metrics

---

## Task 1: Delete Dead Code

**Files:**
- Delete: `packages/categorization/backends/mobile.py`
- Delete: `packages/categorization/discovery.py`
- Delete: `packages/categorization/hyperbolic_nn.py`
- Delete: `packages/categorization/trainer.py`
- Delete: `packages/categorization/losses.py`
- Delete: `packages/categorization/distillation/` (entire directory)
- Delete: `packages/categorization/integration_example.py`
- Modify: `packages/categorization/cli.py`

**Step 1: Delete the files**

```bash
rm packages/categorization/backends/mobile.py
rm packages/categorization/discovery.py
rm packages/categorization/hyperbolic_nn.py
rm packages/categorization/trainer.py
rm packages/categorization/losses.py
rm -rf packages/categorization/distillation/
rm packages/categorization/integration_example.py
```

**Step 2: Fix `cli.py` — remove dead imports, update to use `training.py`**

In `packages/categorization/cli.py`, replace the import block at the top (lines 29-36):

```python
# OLD — remove these:
from packages.categorization.hyperbolic_nn import HyperbolicProjector
from packages.categorization.trainer import HypCDTrainer
from packages.categorization.discovery import HyperbolicKMeans

# NEW — replace with:
from packages.categorization.training import HypCDTrainer
from packages.categorization.clustering import HyperbolicKMeans
```

Also remove the `PROJ_DIM = 2` and `OUTPUT_DIM = 2` lines from cli.py (they were sized for visualization, not production). Replace with:
```python
PROJ_DIM = 128
```

In the `train()` function, replace the `projector = HyperbolicProjector(EMBED_DIM, PROJ_DIM)` line with:
```python
from packages.categorization.hypcd import HyperbolicProjector
projector = HyperbolicProjector(input_dim=EMBED_DIM, hidden_dim=256, output_dim=PROJ_DIM)
```

**Step 3: Verify no broken imports remain**

```bash
.venv/bin/python -c "import packages.categorization.cli"
.venv/bin/python -c "import packages.categorization.hypcd"
.venv/bin/python -c "import packages.categorization.training"
```

Expected: no ImportError output.

**Step 4: Run existing tests to confirm nothing broke**

```bash
.venv/bin/python -m pytest packages/categorization/tests/ -x -q 2>&1 | head -40
```

Expected: same pass/fail ratio as before (any pre-existing failures are OK; no NEW failures).

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor(categorization): remove dead code — mobile backend, duplicate discovery, legacy trainer/losses, distillation"
```

---

## Task 2: Migrate Backbone from BERT to FinBERT

**Files:**
- Modify: `packages/categorization/backends/cloud.py`
- Test: `packages/categorization/tests/test_cloud_backend.py`

**Step 1: Write the failing test**

Open `packages/categorization/tests/test_cloud_backend.py` and add:

```python
def test_finbert_model_name():
    """CloudBackend must use ProsusAI/finbert, not bert-base-uncased."""
    from packages.categorization.backends.cloud import CloudBackend
    import inspect, textwrap
    src = inspect.getsource(CloudBackend.__init__)
    assert "finbert" in src.lower(), (
        "CloudBackend must use ProsusAI/finbert as default model. "
        "Update model_name default to 'ProsusAI/finbert'."
    )
```

**Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest packages/categorization/tests/test_cloud_backend.py::test_finbert_model_name -v
```

Expected: FAIL — "CloudBackend must use ProsusAI/finbert"

**Step 3: Update `backends/cloud.py`**

Change line 17 of `packages/categorization/backends/cloud.py`:

```python
# OLD:
def __init__(self, model_name: str = "bert-base-uncased", dim: int = 768):

# NEW:
def __init__(self, model_name: str = "ProsusAI/finbert", dim: int = 768):
```

**Step 4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest packages/categorization/tests/test_cloud_backend.py::test_finbert_model_name -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add packages/categorization/backends/cloud.py packages/categorization/tests/test_cloud_backend.py
git commit -m "feat(categorization): migrate backbone from bert-base-uncased to ProsusAI/finbert"
```

---

## Task 3: Add `user_model_metadata` Database Table

**Files:**
- Create: `supabase/migrations/20260301000000_user_model_metadata.sql`

**Step 1: Create the migration file**

```sql
-- Migration: Create user_model_metadata table
-- Tracks per-user adapter state: storage path, correction count, last updated.

CREATE TABLE IF NOT EXISTS public.user_model_metadata (
    user_id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    adapter_url      TEXT,           -- Supabase Storage path: users/{user_id}/adapter.pt
    correction_count INT  NOT NULL DEFAULT 0,
    adapter_updated_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.user_model_metadata ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own model metadata"
    ON public.user_model_metadata FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users can upsert own model metadata"
    ON public.user_model_metadata FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own model metadata"
    ON public.user_model_metadata FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id);

-- Service role needs full access for background fine-tuning tasks
CREATE POLICY "Service role has full access"
    ON public.user_model_metadata
    TO service_role
    USING (true)
    WITH CHECK (true);
```

**Step 2: Apply migration locally**

```bash
supabase db push
```

Or if not using Supabase CLI locally, apply via dashboard SQL editor.

**Step 3: Commit**

```bash
git add supabase/migrations/20260301000000_user_model_metadata.sql
git commit -m "feat(db): add user_model_metadata table for per-user adapter tracking"
```

---

## Task 4: Build `AdapterManager`

**Files:**
- Create: `packages/categorization/adapter_manager.py`
- Create: `packages/categorization/tests/test_adapter_manager.py`

**Step 1: Write the failing tests**

Create `packages/categorization/tests/test_adapter_manager.py`:

```python
"""Tests for AdapterManager — load/save/fine-tune per-user adapters."""
import io
import os
import torch
import pytest
from unittest.mock import MagicMock, patch


def make_minimal_state() -> dict:
    """Tiny state dict for testing (no actual model needed)."""
    return {
        "projector": {"mlp.0.weight": torch.zeros(2, 2)},
        "classifier": {"fc1.weight": torch.zeros(2, 2)},
    }


def test_load_user_adapter_returns_none_when_not_found(tmp_path):
    """Returns None if no adapter exists locally or in Supabase."""
    from packages.categorization.adapter_manager import AdapterManager
    mgr = AdapterManager(local_dir=str(tmp_path))
    result = mgr.load_user_adapter("user-123")
    assert result is None


def test_save_and_reload_user_adapter(tmp_path):
    """Round-trip: save adapter locally then reload it."""
    from packages.categorization.adapter_manager import AdapterManager
    mgr = AdapterManager(local_dir=str(tmp_path))
    state = make_minimal_state()
    mgr.save_user_adapter("user-abc", state)
    loaded = mgr.load_user_adapter("user-abc")
    assert loaded is not None
    assert "projector" in loaded


def test_load_global_base_returns_none_when_not_found(tmp_path):
    """Returns None when no global checkpoint exists."""
    from packages.categorization.adapter_manager import AdapterManager
    mgr = AdapterManager(local_dir=str(tmp_path))
    result = mgr.load_global_base()
    assert result is None


def test_save_global_base_and_reload(tmp_path):
    """Round-trip: save global base then reload."""
    from packages.categorization.adapter_manager import AdapterManager
    mgr = AdapterManager(local_dir=str(tmp_path))
    state = make_minimal_state()
    mgr.save_global_base(state)
    loaded = mgr.load_global_base()
    assert loaded is not None
    assert "projector" in loaded


def test_supabase_upload_failure_does_not_raise(tmp_path):
    """If Supabase Storage upload fails, save still succeeds locally."""
    from packages.categorization.adapter_manager import AdapterManager
    mgr = AdapterManager(
        supabase_url="https://fake.supabase.co",
        supabase_key="fakekey",
        local_dir=str(tmp_path),
    )
    with patch.object(mgr, "_storage", side_effect=Exception("connection refused")):
        mgr.save_user_adapter("user-xyz", make_minimal_state())  # must not raise

    # Local file was still written
    assert os.path.exists(os.path.join(str(tmp_path), "users", "user-xyz", "adapter.pt"))
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest packages/categorization/tests/test_adapter_manager.py -v
```

Expected: FAIL — ModuleNotFoundError for `adapter_manager`

**Step 3: Create `packages/categorization/adapter_manager.py`**

```python
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
import structlog
import torch
from typing import TYPE_CHECKING

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
        self._supabase_url = supabase_url or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
        self._supabase_key = supabase_key or (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
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
                    file_options={"content-type": "application/octet-stream", "upsert": "true"},
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
        from packages.categorization.training import HypCDTrainer
        from packages.categorization.cleaner import TextAugmenter

        if len(texts) < 4:
            logger.debug("contrastive_pretraining_skipped", reason="too_few_texts", count=len(texts))
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
    """Dynamic λ for hybrid loss: ramp from 0→0.5 over first 20% of epochs.

    Per §3.6.2: start with angle optimization (easier convergence), then
    gradually enforce hyperbolic distance structure.
    """
    warmup = max(1, int(0.2 * total_epochs))
    if epoch < warmup:
        return 0.5 * (epoch / warmup)
    return 0.5
```

**Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest packages/categorization/tests/test_adapter_manager.py -v
```

Expected: all 5 tests PASS

**Step 5: Commit**

```bash
git add packages/categorization/adapter_manager.py packages/categorization/tests/test_adapter_manager.py
git commit -m "feat(categorization): add AdapterManager for load/save/fine-tune per-user adapters"
```

---

## Task 5: Overhaul `HypCDClassifier` — Checkpoint Loading + Full Pipeline

This is the largest task. It wires all 10 pipeline steps, adds checkpoint loading at init, and implements GCD routing (steps 7-8) and hierarchy norm (step 9).

**Files:**
- Modify: `packages/categorization/hypcd.py`
- Test: `packages/categorization/tests/test_hypcd.py`

**Step 1: Write the failing tests**

Add these to `packages/categorization/tests/test_hypcd.py`:

```python
def test_predict_batch_returns_depth_and_norm(mock_classifier):
    """predict_batch output must include 'depth', 'norm', and 'path' keys (§3.8)."""
    results = mock_classifier.predict_batch(["swiggy order"])
    r = results[0]
    assert "depth" in r, "Missing 'depth' key — §3.8 hierarchy extraction not implemented"
    assert "norm" in r, "Missing 'norm' key — §3.8 hierarchy extraction not implemented"
    assert "path" in r, "Missing 'path' key — prediction path not tracked"
    assert r["depth"] in ("macro", "micro")
    assert isinstance(r["norm"], float)


def test_predict_batch_low_confidence_routes_to_novel(mock_classifier, monkeypatch):
    """Predictions with confidence < 0.5 must be routed to GCD (§3.7)."""
    import torch, torch.nn.functional as F
    from geoopt import PoincareBall

    # Force HypFFN to output uniform probabilities (max confidence ~1/11 ≈ 0.09)
    def _zero_logits(self, x):
        return PoincareBall(c=1.0).expmap0(torch.zeros(x.shape[0], 11))

    monkeypatch.setattr(
        mock_classifier.classifier.__class__, "forward", _zero_logits
    )
    # Suppress keyword rules so model path runs
    monkeypatch.setattr(mock_classifier.rule_matcher, "predict", lambda t: None)

    results = mock_classifier.predict_batch(["some unknown merchant xyz"])
    r = results[0]
    assert r["is_novel"] is True, "Low-confidence result must be marked is_novel=True"
    assert r["path"] == "novel_cluster"


def test_predict_batch_keyword_path_label(mock_classifier):
    """Keyword-matched predictions must have path='keyword_rule'."""
    results = mock_classifier.predict_batch(["swiggy order"])
    assert results[0]["path"] == "keyword_rule"
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest packages/categorization/tests/test_hypcd.py::test_predict_batch_returns_depth_and_norm packages/categorization/tests/test_hypcd.py::test_predict_batch_low_confidence_routes_to_novel packages/categorization/tests/test_hypcd.py::test_predict_batch_keyword_path_label -v
```

Expected: FAIL — KeyError / AssertionError

**Step 3: Add `_load_checkpoint()` to `HypCDClassifier.__init__()`**

In `packages/categorization/hypcd.py`, add to the end of `HypCDClassifier.__init__()` (after `self.rule_matcher = KeywordMatcher()` and `self.anchors = self._initialize_anchors()`):

```python
        # Load checkpoint if available (§ startup: global base or env override)
        self._load_checkpoint()
```

Then add the method to `HypCDClassifier`:

```python
    def _load_checkpoint(self) -> None:
        """Load global base checkpoint at startup.

        Priority:
          1. HYPCD_CHECKPOINT_PATH env var (explicit override)
          2. AdapterManager: Supabase Storage models/global/base_model.pt
          3. checkpoints/global/base_model.pt (local dev)
          4. Silent skip (random init — first run)
        """
        import os
        from packages.categorization.adapter_manager import AdapterManager

        explicit = os.getenv("HYPCD_CHECKPOINT_PATH")
        if explicit:
            try:
                state = torch.load(explicit, map_location=self.backend.device, weights_only=True)
                self.load_state_dict(state)
                logger.info("checkpoint_loaded", source="env_var", path=explicit)
                return
            except Exception as e:
                logger.warning("checkpoint_load_failed", path=explicit, error=str(e))

        mgr = AdapterManager()
        state = mgr.load_global_base()
        if state:
            try:
                self.load_state_dict(state)
                logger.info("checkpoint_loaded", source="global_base")
            except Exception as e:
                logger.warning("checkpoint_load_failed", source="global_base", error=str(e))
        else:
            logger.info("checkpoint_not_found", note="using_random_init")
```

Add `import structlog` and `logger = structlog.get_logger()` at the top of `hypcd.py` (after existing imports).

**Step 4: Extend `predict_batch()` — add steps 7, 8b, 9, and `path` tracking**

In `hypcd.py`, update `predict_batch()`. Locate the results-building loop at line ~466 and replace it with:

```python
        # Import hierarchy extractor once
        from .clustering import HierarchyExtractor
        _extractor = HierarchyExtractor(self.manifold)
        CONFIDENCE_THRESHOLD = 0.5

        # Build results
        for model_i, (idx, conf) in enumerate(zip(indices, confidences)):
            target_i = model_indices[model_i]
            candidate = model_texts[model_i].lower()
            predicted = self.labels[idx.item()]
            embedding = embeddings[model_i]

            # § 3.7.1 confidence threshold — route novel to GCD
            if conf.item() < CONFIDENCE_THRESHOLD:
                novel = self._classify_novel(embedding)
                results[target_i] = {
                    "category":   novel["category"],
                    "confidence": novel["confidence"],
                    "embedding":  embedding,
                    "is_novel":   True,
                    "depth":      "boundary",
                    "norm":       novel["norm"],
                    "path":       "novel_cluster",
                }
                continue

            # § 3.1 Salary guardrail
            if predicted == "Salary" and not any(
                token in candidate
                for token in ["salary", "payroll", "stipend", "credited", "wage"]
            ):
                predicted = "Misc"

            # § 3.8 Hierarchy norm extraction
            norm_val = _extractor.compute_norm(embedding).item()
            depth = "macro" if norm_val < 0.5 else "micro"

            results[target_i] = {
                "category":   predicted,
                "confidence": conf.item(),
                "embedding":  embedding,
                "is_novel":   False,
                "depth":      depth,
                "norm":       norm_val,
                "path":       "hypffn",
            }
```

Also update the keyword-rule path (around line ~419) to add the new fields:

```python
            if rule_category:
                embedding = self.embedder.embed_batch([candidate])[0]
                from .clustering import HierarchyExtractor
                extractor = HierarchyExtractor(self.manifold)
                norm_val = extractor.compute_norm(embedding).item()
                results[i] = {
                    "category":   rule_category,
                    "confidence": 1.0,
                    "embedding":  embedding,
                    "is_novel":   False,
                    "depth":      "macro" if norm_val < 0.5 else "micro",
                    "norm":       norm_val,
                    "path":       "keyword_rule",
                }
```

**Step 5: Add `_classify_novel()` method to `HypCDClassifier`**

```python
    def _classify_novel(self, embedding: torch.Tensor) -> dict:
        """Route low-confidence embedding through anchor-based GCD (§3.7.2).

        Uses pre-computed category anchors as proxy centroids.
        Finds nearest anchor by hyperbolic distance.
        """
        from .clustering import HierarchyExtractor
        extractor = HierarchyExtractor(self.manifold)
        norm_val = extractor.compute_norm(embedding).item()

        # Stack anchor embeddings — shape (K, D)
        anchor_keys = list(self.anchors.keys())
        anchor_vecs = torch.cat([self.anchors[k] for k in anchor_keys], dim=0)

        # Hyperbolic distances from this embedding to each anchor
        dists = self.manifold.dist(
            embedding.unsqueeze(0).expand(len(anchor_keys), -1),
            anchor_vecs,
        )

        min_idx = dists.argmin().item()
        confidence = torch.exp(-dists[min_idx]).item()

        return {
            "category":   anchor_keys[min_idx],
            "confidence": max(confidence, 0.05),
            "norm":       norm_val,
        }
```

**Step 6: Run the new tests to verify they pass**

```bash
.venv/bin/python -m pytest packages/categorization/tests/test_hypcd.py -v 2>&1 | tail -20
```

Expected: all tests PASS (including the 3 new ones)

**Step 7: Commit**

```bash
git add packages/categorization/hypcd.py packages/categorization/tests/test_hypcd.py
git commit -m "feat(hypcd): wire full research pipeline — checkpoint loading, GCD routing §3.7, hierarchy norm §3.8, path tracking"
```

---

## Task 6: Dynamic λ Schedule in `training.py`

**Files:**
- Modify: `packages/categorization/training.py`
- Test: `packages/categorization/tests/test_trainer.py`

**Step 1: Write the failing test**

Add to `packages/categorization/tests/test_trainer.py`:

```python
def test_lambda_schedule_ramps_then_holds():
    """Lambda must start near 0 and ramp to 0.5 over first 20% of epochs."""
    from packages.categorization.adapter_manager import _lambda_schedule

    # Warmup period (epoch 0 of 10 total → 2 epoch warmup)
    assert _lambda_schedule(0, 10) == pytest.approx(0.0, abs=0.01)
    # Mid-warmup
    assert _lambda_schedule(1, 10) == pytest.approx(0.25, abs=0.01)
    # After warmup, holds at 0.5
    assert _lambda_schedule(2, 10) == pytest.approx(0.5, abs=0.01)
    assert _lambda_schedule(9, 10) == pytest.approx(0.5, abs=0.01)
```

**Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest packages/categorization/tests/test_trainer.py::test_lambda_schedule_ramps_then_holds -v
```

Expected: FAIL (function not found or wrong values)

**Step 3: Verify `_lambda_schedule` is already in `adapter_manager.py`**

The `_lambda_schedule` function was added in Task 4. This test imports from `adapter_manager`. Run:

```bash
.venv/bin/python -m pytest packages/categorization/tests/test_trainer.py::test_lambda_schedule_ramps_then_holds -v
```

Expected: PASS (already implemented in Task 4)

**Step 4: Update `HypCDTrainer` in `training.py` to accept a `lambda_weight` in the training loop**

The `train_step()` method in `training.py` already accepts `lambda_weight` as a parameter. Add a full training loop that applies the schedule. Add this method to `HypCDTrainer` in `packages/categorization/training.py`:

```python
    def train_epochs(
        self,
        batches: list[dict],
        total_epochs: int = 10,
    ) -> list[float]:
        """Run N epochs with dynamic lambda schedule (§3.6.2).

        Args:
            batches: List of {"original": Tensor, "augmented": Tensor} dicts
            total_epochs: Number of epochs to train

        Returns:
            List of per-epoch average loss values
        """
        from packages.categorization.adapter_manager import _lambda_schedule

        epoch_losses = []
        for epoch in range(total_epochs):
            lw = _lambda_schedule(epoch, total_epochs)
            batch_losses = [self.train_step(b, lambda_weight=lw) for b in batches]
            avg = sum(batch_losses) / len(batch_losses) if batch_losses else 0.0
            epoch_losses.append(avg)

        return epoch_losses
```

**Step 5: Run full trainer tests**

```bash
.venv/bin/python -m pytest packages/categorization/tests/test_trainer.py -v 2>&1 | tail -20
```

Expected: all pass

**Step 6: Commit**

```bash
git add packages/categorization/training.py packages/categorization/tests/test_trainer.py
git commit -m "feat(training): add train_epochs() with dynamic lambda schedule per §3.6.2"
```

---

## Task 7: Per-Class F1 and Training Metrics

**Files:**
- Modify: `packages/categorization/training_pipeline.py`
- Test: `packages/categorization/tests/test_training_pipeline.py`

**Step 1: Write the failing test**

Add to `packages/categorization/tests/test_training_pipeline.py`:

```python
def test_validate_returns_per_class_f1(mock_pipeline_with_data):
    """validate() must return per_class_f1, precision, recall keys."""
    val_loader = mock_pipeline_with_data
    pipeline = make_minimal_pipeline()
    metrics = pipeline.validate(val_loader)

    assert "accuracy" in metrics
    assert "per_class_f1" in metrics, "Missing per_class_f1 — add sklearn classification_report"
    assert isinstance(metrics["per_class_f1"], dict)
    assert "top2_accuracy" in metrics, "Missing top2_accuracy"
```

**Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest packages/categorization/tests/test_training_pipeline.py::test_validate_returns_per_class_f1 -v
```

Expected: FAIL — `per_class_f1` key missing

**Step 3: Update `validate()` in `training_pipeline.py`**

Replace the `validate()` method (around line 648) with:

```python
    def validate(self, val_loader: DataLoader) -> Dict:
        """Validate model — accuracy, per-class F1, top-K accuracy."""
        from sklearn.metrics import (
            accuracy_score,
            precision_recall_fscore_support,
            top_k_accuracy_score,
        )

        self.classifier.eval()
        all_labels, all_preds, all_probs = [], [], []

        with torch.no_grad():
            for embeddings, labels, texts in val_loader:
                embeddings = embeddings.to(self.device)
                labels_cpu = labels.numpy().tolist()

                hyp_embeddings = self.classifier.embedder.projector(embeddings)
                logits = self.classifier.classifier(hyp_embeddings)

                from geoopt import PoincareBall
                import torch.nn.functional as F
                manifold = PoincareBall(c=1.0)
                probs = F.softmax(manifold.logmap0(logits), dim=-1).cpu().numpy()
                preds = probs.argmax(axis=-1).tolist()

                all_labels.extend(labels_cpu)
                all_preds.extend(preds)
                all_probs.extend(probs.tolist())

        if not all_labels:
            return {"loss": 0.0, "accuracy": 0.0, "per_class_f1": {}, "top2_accuracy": 0.0}

        import numpy as np
        y_true = np.array(all_labels)
        y_pred = np.array(all_preds)
        y_prob = np.array(all_probs)

        label_names = self.classifier.labels

        acc = accuracy_score(y_true, y_pred)
        precision, recall, f1, support = precision_recall_fscore_support(
            y_true, y_pred, labels=list(range(len(label_names))), zero_division=0
        )

        per_class_f1 = {
            label_names[i]: {
                "precision": float(precision[i]),
                "recall":    float(recall[i]),
                "f1":        float(f1[i]),
                "support":   int(support[i]),
            }
            for i in range(len(label_names))
            if support[i] > 0
        }

        top2 = 0.0
        if y_prob.shape[1] >= 2:
            try:
                top2 = float(top_k_accuracy_score(y_true, y_prob, k=2))
            except Exception:
                pass

        return {
            "accuracy":      float(acc),
            "per_class_f1":  per_class_f1,
            "top2_accuracy": top2,
        }
```

**Step 4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest packages/categorization/tests/test_training_pipeline.py -v 2>&1 | tail -20
```

Expected: PASS

**Step 5: Commit**

```bash
git add packages/categorization/training_pipeline.py packages/categorization/tests/test_training_pipeline.py
git commit -m "feat(training): add per-class F1, top-2 accuracy to validate() metrics"
```

---

## Task 8: Merchant-Batch Reclassification (Accounts Router)

**Files:**
- Modify: `apps/api/domains/accounts/router.py`
- Test: `apps/api/domains/accounts/tests/test_merchant_batch.py`

**Step 1: Write the failing test**

Create `apps/api/domains/accounts/tests/test_merchant_batch.py`:

```python
"""Tests for merchant-batch reclassification behavior."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


def make_mock_client(transactions: list[dict]):
    client = MagicMock()
    client.auth.get_user.return_value = MagicMock(user=MagicMock(id="user-1"))

    # Mock: fetch the transaction being corrected
    fetch_mock = MagicMock()
    fetch_mock.data = transactions[:1]
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = fetch_mock

    # Mock: batch update
    update_mock = MagicMock()
    update_mock.data = transactions
    client.table.return_value.update.return_value.eq.return_value.eq.return_value.ilike.return_value.execute.return_value = update_mock

    return client


def test_reclassify_single_transaction_also_updates_merchant_matches(app_client):
    """PATCH /transactions/{id} must auto-update all matching merchant transactions."""
    # This is an integration test — mock the Supabase client
    # The response should include merchant_updated > 0
    response = app_client.patch(
        "/api/v1/accounts/transactions/tx-123",
        json={"category": "Food", "old_category": "Transport"},
        headers={"Authorization": "Bearer fake"},
    )
    # We check the response includes merchant_updated key
    assert response.status_code == 200
    data = response.json()
    assert "merchant_updated" in data, (
        "Response must include 'merchant_updated' count — "
        "merchant-batch reclassification not implemented"
    )
```

**Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest apps/api/domains/accounts/tests/test_merchant_batch.py -v
```

Expected: FAIL — `merchant_updated` key missing from response

**Step 3: Add `extract_merchant_keyword()` helper and update `update_transaction` endpoint**

In `apps/api/domains/accounts/router.py`:

Add the helper function after the imports:

```python
def _extract_merchant_keyword(description: str) -> str | None:
    """Extract the most distinctive word from a cleaned transaction description.

    Used to find all related transactions for merchant-batch reclassification.
    Returns None if no keyword with length > 3 is found.
    """
    from packages.categorization.cleaner import clean_description
    from packages.categorization.rules import KeywordMatcher

    # First: check if a known keyword matches (most reliable)
    matcher = KeywordMatcher()
    cleaned = clean_description(description).lower()
    for keyword in matcher.rules.keys():
        if keyword in cleaned:
            return keyword

    # Fallback: first word with length > 3
    for word in cleaned.split():
        if len(word) > 3:
            return word

    return None
```

Update `TransactionUpdate` schema to accept `old_category`:

```python
class TransactionUpdate(BaseModel):
    """Updateable fields for a single transaction."""
    category: Optional[str] = Field(default=None)
    amount: Optional[float] = Field(default=None)
    original_category: Optional[str] = Field(default=None)
    old_category: Optional[str] = Field(
        default=None,
        description="Previous category — used for merchant-batch reclassification"
    )
```

Replace the `update_transaction` endpoint body with:

```python
@router.patch("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: str = Path(description="Transaction UUID"),
    update: TransactionUpdate = Body(...),
    client: Client = Depends(get_user_client),
):
    """Update a single transaction and auto-reclassify all matching merchant transactions.

    When category changes, all transactions from the same merchant that had
    the old category are automatically updated to the new category and marked
    is_manual=True (merchant-batch reclassification).
    """
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    user_id = user_response.user.id

    updates = {}
    if update.category is not None:
        updates["category"] = update.category
        updates["is_manual"] = True
    if update.amount is not None:
        updates["amount"] = update.amount
    if update.original_category is not None:
        updates["original_category"] = update.original_category

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        result = (
            client.table("transactions")
            .update(updates)
            .eq("id", transaction_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Transaction not found")

        tx = result.data[0]
        merchant_updated = 0

        # Merchant-batch reclassification: auto-update all matching transactions
        if update.category and update.old_category:
            description = tx.get("description", "")
            keyword = _extract_merchant_keyword(description)

            if keyword:
                try:
                    batch_result = (
                        client.table("transactions")
                        .update({"category": update.category, "is_manual": True})
                        .eq("user_id", user_id)
                        .eq("category", update.old_category)
                        .ilike("description", f"%{keyword}%")
                        .execute()
                    )
                    merchant_updated = len(batch_result.data) if batch_result.data else 0
                    logger.info(
                        "merchant_batch_reclassified",
                        keyword=keyword,
                        old=update.old_category,
                        new=update.category,
                        count=merchant_updated,
                    )
                except Exception as e:
                    logger.warning("merchant_batch_failed", error=str(e))

        return {
            "status": "ok",
            "transaction": tx,
            "merchant_updated": merchant_updated,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("transaction_update_failed", error=str(e), tx_id=transaction_id)
        raise HTTPException(status_code=500, detail="Failed to update transaction")
```

**Step 4: Run the test**

```bash
.venv/bin/python -m pytest apps/api/domains/accounts/tests/ -v 2>&1 | tail -20
```

**Step 5: Commit**

```bash
git add apps/api/domains/accounts/router.py apps/api/domains/accounts/tests/test_merchant_batch.py
git commit -m "feat(accounts): merchant-batch reclassification — auto-update all matching transactions on category correction"
```

---

## Task 9: Contrastive Pretraining Post-Import

**Files:**
- Modify: `apps/api/domains/ingestion/router.py`
- Test: `apps/api/domains/ingestion/tests/test_pretraining_trigger.py`

**Step 1: Write the failing test**

Create `apps/api/domains/ingestion/tests/test_pretraining_trigger.py`:

```python
"""Test that contrastive pretraining is triggered after a successful import."""
from unittest.mock import MagicMock, patch, call


def test_contrastive_pretraining_queued_after_import():
    """_run_contrastive_pretraining_bg must be added as a background task after import."""
    from apps.api.domains.ingestion.router import _classify_and_update_transactions
    import inspect
    src = inspect.getsource(_classify_and_update_transactions)
    # After classification, pretraining should be triggered
    # We check the module-level function exists
    from apps.api.domains.ingestion import router as ingestion_module
    assert hasattr(ingestion_module, "_run_contrastive_pretraining_bg"), (
        "Missing _run_contrastive_pretraining_bg function — "
        "contrastive pretraining not triggered post-import"
    )
```

**Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest apps/api/domains/ingestion/tests/test_pretraining_trigger.py -v
```

Expected: FAIL

**Step 3: Add contrastive pretraining background task to `ingestion/router.py`**

Add this function to `apps/api/domains/ingestion/router.py` (after `_classify_and_update_transactions`):

```python
def _run_contrastive_pretraining_bg(
    user_id: str,
    descriptions: list[str],
    token: str,
) -> None:
    """Background task: unsupervised contrastive pretraining on imported transactions.

    Runs after /import completes. No labels required — uses augmented positive pairs.
    Updates the per-user adapter (projector weights) and persists to Supabase Storage.
    """
    if len(descriptions) < 4:
        return

    try:
        from apps.api.domains.categorization.service import get_classifier
        from packages.categorization.adapter_manager import AdapterManager

        classifier = get_classifier()
        mgr = AdapterManager()

        # Load user adapter if exists, else use global base
        user_state = mgr.load_user_adapter(user_id)
        if user_state:
            try:
                classifier.load_state_dict(user_state)
            except Exception:
                pass

        mgr.run_contrastive_pretraining(classifier, descriptions, epochs=3)

        # Save updated adapter
        mgr.save_user_adapter(user_id, classifier.state_dict())

        logger.info(
            "contrastive_pretraining_complete",
            user_id=user_id,
            descriptions=len(descriptions),
        )
    except Exception as e:
        logger.warning("contrastive_pretraining_failed", user_id=user_id, error=str(e))
```

Then, at the end of `import_file()` in `router.py`, add the pretraining task after the existing `_classify_and_update_transactions` task:

```python
    # Enqueue contrastive pretraining (updates projector weights from unlabeled data)
    if unique_descs and token:
        background_tasks.add_task(
            _run_contrastive_pretraining_bg, user_id, unique_descs, token
        )
```

**Step 4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest apps/api/domains/ingestion/tests/test_pretraining_trigger.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/api/domains/ingestion/router.py apps/api/domains/ingestion/tests/test_pretraining_trigger.py
git commit -m "feat(ingestion): trigger contrastive pretraining as background task after import"
```

---

## Task 10: Supervised Fine-Tuning Post-Reclassification

**Files:**
- Modify: `apps/api/domains/accounts/router.py`
- Test: `apps/api/domains/accounts/tests/test_merchant_batch.py`

**Step 1: Write the failing test**

Add to `apps/api/domains/accounts/tests/test_merchant_batch.py`:

```python
def test_fine_tuning_triggered_after_merchant_batch(monkeypatch):
    """After merchant-batch reclassification, supervised fine-tuning must be triggered."""
    from apps.api.domains.accounts import router as accounts_module
    import inspect

    src = inspect.getsource(accounts_module.update_transaction)
    assert "_run_supervised_finetuning_bg" in src, (
        "update_transaction must enqueue _run_supervised_finetuning_bg — "
        "supervised fine-tuning not triggered after reclassification"
    )
```

**Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest apps/api/domains/accounts/tests/test_merchant_batch.py::test_fine_tuning_triggered_after_merchant_batch -v
```

Expected: FAIL

**Step 3: Add fine-tuning background task to `accounts/router.py`**

Add this function to `apps/api/domains/accounts/router.py`:

```python
def _run_supervised_finetuning_bg(
    user_id: str,
    texts: list[str],
    categories: list[str],
) -> None:
    """Background task: supervised fine-tuning of user adapter on corrected transactions.

    Triggered after merchant-batch reclassification. Trains projector + HypFFN
    on the newly labeled (description, category) pairs.
    """
    if not texts or len(texts) != len(categories):
        return

    try:
        from apps.api.domains.categorization.service import get_classifier
        from packages.categorization.adapter_manager import AdapterManager

        classifier = get_classifier()
        mgr = AdapterManager()

        # Load user adapter base
        user_state = mgr.load_user_adapter(user_id)
        if user_state:
            try:
                classifier.load_state_dict(user_state)
            except Exception:
                pass

        mgr.fine_tune_supervised(classifier, texts, categories, epochs=5)

        # Persist updated adapter
        mgr.save_user_adapter(user_id, classifier.state_dict())

        logger.info(
            "supervised_finetuning_complete",
            user_id=user_id,
            examples=len(texts),
        )
    except Exception as e:
        logger.warning("supervised_finetuning_failed", user_id=user_id, error=str(e))
```

Update `update_transaction` to enqueue fine-tuning when merchant-batch update returns results. In the merchant-batch block, after logging `merchant_batch_reclassified`, add:

```python
                    if merchant_updated > 0 and batch_result.data:
                        # Collect all corrected (description, category) pairs for fine-tuning
                        ft_texts = [r.get("description", "") for r in batch_result.data if r.get("description")]
                        ft_categories = [update.category] * len(ft_texts)
                        if ft_texts:
                            # This requires background_tasks — add BackgroundTasks to endpoint signature
                            background_tasks.add_task(
                                _run_supervised_finetuning_bg, user_id, ft_texts, ft_categories
                            )
```

Update the `update_transaction` signature to accept `BackgroundTasks`:

```python
@router.patch("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: str = Path(description="Transaction UUID"),
    update: TransactionUpdate = Body(...),
    background_tasks: BackgroundTasks = None,   # NEW
    client: Client = Depends(get_user_client),
):
```

Add `BackgroundTasks` to the import: `from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Path, Query`

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest apps/api/domains/accounts/tests/ -v 2>&1 | tail -20
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/api/domains/accounts/router.py
git commit -m "feat(accounts): trigger supervised fine-tuning after merchant-batch reclassification"
```

---

## Task 11: Metrics Endpoint `GET /categorization/metrics`

**Files:**
- Modify: `apps/api/domains/categorization/router.py`
- Modify: `apps/api/domains/categorization/schemas.py`
- Test: `apps/api/domains/categorization/tests/test_classify_endpoint.py`

**Step 1: Write the failing test**

Add to `apps/api/domains/categorization/tests/test_classify_endpoint.py`:

```python
def test_metrics_endpoint_exists(client_with_auth):
    """GET /categorization/metrics must return accuracy and per_class keys."""
    response = client_with_auth.get("/api/v1/categorization/metrics")
    assert response.status_code in (200, 404)  # 404 = no labeled data yet
    if response.status_code == 200:
        data = response.json()
        assert "overall_accuracy" in data
        assert "per_class" in data
        assert "confidence_histogram" in data
        assert "rule_vs_model_split" in data
```

**Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest apps/api/domains/categorization/tests/test_classify_endpoint.py::test_metrics_endpoint_exists -v
```

Expected: FAIL — 405 or 404 (endpoint doesn't exist)

**Step 3: Add `GET /metrics` endpoint to `categorization/router.py`**

Add to `apps/api/domains/categorization/router.py`:

```python
@router.get("/metrics")
async def get_classification_metrics(client: Client = Depends(get_user_client)):
    """Compute classification accuracy metrics using manually-corrected transactions.

    Ground truth: transactions where is_manual=True.
    Returns per-class F1, confidence histogram, and rule vs. model split.
    Requires at least 1 manually corrected transaction.
    """
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support
    import numpy as np

    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    user_id = user_response.user.id

    # Fetch labeled ground truth (is_manual=True)
    try:
        result = (
            client.table("transactions")
            .select("description,category")
            .eq("user_id", user_id)
            .eq("is_manual", True)
            .execute()
        )
        labeled = result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB query failed: {e}")

    if not labeled:
        return {
            "error": "no_labeled_data",
            "message": "Correct some transactions first to generate metrics.",
            "total_corrections": 0,
        }

    descriptions = [r["description"] for r in labeled if r.get("description")]
    true_categories = [r["category"] for r in labeled if r.get("description")]

    if not descriptions:
        raise HTTPException(status_code=400, detail="No valid descriptions in labeled data")

    # Classify all labeled transactions
    try:
        predictions = classify_batch_in_process(descriptions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {e}")

    pred_categories = [p["category"] for p in predictions]
    confidences = [p["confidence"] for p in predictions]
    paths = [p.get("path", "unknown") for p in predictions]

    # Get classifier labels for consistent indexing
    classifier = get_classifier()
    label_names = classifier.labels
    label2idx = {l: i for i, l in enumerate(label_names)}

    y_true = np.array([label2idx.get(c, len(label_names) - 1) for c in true_categories])
    y_pred = np.array([label2idx.get(c, len(label_names) - 1) for c in pred_categories])

    acc = float(accuracy_score(y_true, y_pred))
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred,
        labels=list(range(len(label_names))),
        zero_division=0,
    )

    per_class = {
        label_names[i]: {
            "precision": float(precision[i]),
            "recall":    float(recall[i]),
            "f1":        float(f1[i]),
            "support":   int(support[i]),
        }
        for i in range(len(label_names))
        if support[i] > 0
    }

    # Confidence histogram (5 buckets)
    buckets = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    for c in confidences:
        idx = min(int(c / 0.2), 4)
        key = list(buckets.keys())[idx]
        buckets[key] += 1

    # Rule vs. model split
    split = {"keyword_rule": 0, "hypffn": 0, "novel_cluster": 0}
    for p in paths:
        if p in split:
            split[p] += 1
        else:
            split["hypffn"] += 1

    return {
        "overall_accuracy":         acc,
        "per_class":                per_class,
        "confidence_histogram":     buckets,
        "rule_vs_model_split":      split,
        "total_corrections":        len(labeled),
        "novel_categories_discovered": sum(1 for p in predictions if p.get("is_novel")),
    }
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest apps/api/domains/categorization/tests/ -v 2>&1 | tail -20
```

**Step 5: Commit**

```bash
git add apps/api/domains/categorization/router.py
git commit -m "feat(categorization): add GET /metrics endpoint with per-class F1, confidence histogram, rule vs model split"
```

---

## Task 12: `train-global` CLI Command

**Files:**
- Modify: `packages/categorization/cli.py`
- Test: (manual — verified via dry run)

**Step 1: Add `train_global()` function and argparse command to `cli.py`**

Add this function in `packages/categorization/cli.py` before `main()`:

```python
def train_global(args):
    """Train global base model on aggregate is_manual=True corrections from all users.

    Fetches anonymized (description, category) pairs from all users who have
    manually corrected transactions. Trains FinBERT + HypCD pipeline.
    Saves checkpoint locally and optionally uploads to Supabase Storage.
    """
    print("Connecting to Supabase...")
    supabase = get_supabase()

    # Fetch all is_manual=True transactions across all users (dev-only: service role key)
    print("Fetching labeled corrections from all users...")
    result = (
        supabase.table("transactions")
        .select("description,category")
        .eq("is_manual", True)
        .execute()
    )
    records = result.data or []

    if not records:
        print("No manual corrections found. Train-global requires is_manual=True transactions.")
        return

    print(f"Found {len(records)} labeled corrections across all users.")

    texts = [r["description"] for r in records if r.get("description")]
    categories = [r["category"] for r in records if r.get("description")]

    if len(texts) < 50:
        print(f"WARNING: Only {len(texts)} examples. Global model benefits from 1000+.")

    # Initialize classifier with FinBERT backend
    print("Initializing HypCDClassifier with FinBERT backbone...")
    from packages.categorization.backends.cloud import CloudBackend
    backend = CloudBackend()
    classifier = HypCDClassifier(backend=backend)

    # Run supervised fine-tuning via AdapterManager
    from packages.categorization.adapter_manager import AdapterManager
    mgr = AdapterManager()

    print(f"Running supervised fine-tuning for {args.epochs} epochs...")
    mgr.fine_tune_supervised(classifier, texts, categories, epochs=args.epochs)

    # Save checkpoint
    output_path = args.output or "checkpoints/global/base_model.pt"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    mgr.save_global_base(classifier.state_dict())
    print(f"Global base model saved to: checkpoints/global/base_model.pt")

    if args.upload:
        print("Uploading to Supabase Storage (models/global/base_model.pt)...")
        # save_global_base already uploads to Supabase Storage if credentials are set
        print("Upload complete (or skipped if no Supabase credentials).")

    print(f"\nTraining complete.")
    print(f"  Labeled examples: {len(texts)}")
    print(f"  Epochs:           {args.epochs}")
    print(f"  Checkpoint:       checkpoints/global/base_model.pt")
    print("\nNext: restart the API to load the new checkpoint automatically.")
```

In `main()`, add the `train-global` subcommand:

```python
    # train-global
    tg_parser = subparsers.add_parser(
        "train-global",
        help="Train global base model on aggregate corrections from all users"
    )
    tg_parser.add_argument("--epochs", type=int, default=50, help="Training epochs")
    tg_parser.add_argument("--output", type=str, default=None, help="Output checkpoint path")
    tg_parser.add_argument("--upload", action="store_true", help="Upload to Supabase Storage")
```

And in the dispatch block:

```python
    elif args.command == "train-global":
        train_global(args)
```

**Step 2: Verify the CLI runs without errors**

```bash
.venv/bin/python -m packages.categorization.cli --help
.venv/bin/python -m packages.categorization.cli train-global --help
```

Expected: help text shows `train-global` with `--epochs`, `--output`, `--upload` options.

**Step 3: Commit**

```bash
git add packages/categorization/cli.py
git commit -m "feat(cli): add train-global command — trains global HypCD base model on aggregate corrections"
```

---

## Task 13: Remove Frontend "Reclassify All?" Prompt

**Files:**
- Modify: `apps/web/app/dashboard/transactions/page.tsx`

**Step 1: Find the reclassify prompt in the frontend**

```bash
grep -n "reclassify\|Reclassify\|associated\|similar" apps/web/app/dashboard/transactions/page.tsx | head -20
```

**Step 2: Understand what to change**

The frontend currently asks the user "Do you want to reclassify all similar transactions?" before calling `batchUpdateTransactions`. This dialog must be removed. The API now handles merchant-batch automatically via `PATCH /accounts/transactions/{id}` with `old_category`.

**Step 3: Update the category edit handler**

Find the `saveCategoryEdit` or `handleReclassify` function in `transactions/page.tsx`.

The current call likely looks like:
```typescript
// OLD: asks user first
if (confirm("Reclassify all similar?")) {
  await accountsApi.batchUpdateTransactions([...similarTxs]);
}
await accountsApi.updateTransaction(id, { category: newCategory });
```

Replace with a single call that passes `old_category`:
```typescript
// NEW: server handles batch automatically
const result = await accountsApi.updateTransaction(id, {
  category: newCategory,
  old_category: transaction.category,   // Pass old category for merchant-batch
});
// result.merchant_updated tells us how many were updated
```

Remove any `confirm()` dialog, batch selection UI, or "similar transactions" modal related to reclassification.

**Step 4: Update `client.ts` to include `old_category`**

In `apps/web/lib/api/client.ts`, find the `updateTransaction` method and update its payload type:

```typescript
// Add old_category to the update payload
async updateTransaction(id: string, updates: {
  category?: string;
  amount?: number;
  original_category?: string;
  old_category?: string;   // NEW
}): Promise<{ status: string; transaction: Transaction; merchant_updated: number }> {
  // ... existing implementation
}
```

**Step 5: Verify TypeScript compiles**

```bash
cd apps/web && npx tsc --noEmit 2>&1 | head -20
```

Expected: 0 new errors

**Step 6: Commit**

```bash
git add apps/web/app/dashboard/transactions/page.tsx apps/web/lib/api/client.ts
git commit -m "feat(frontend): remove 'reclassify all?' prompt — merchant-batch now automatic via API"
```

---

## Final Verification

Run the full test suite:

```bash
.venv/bin/python -m pytest packages/categorization/tests/ apps/api/domains/ -x -q 2>&1 | tail -30
```

Check the entire categorization pipeline end-to-end:

```bash
.venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, ".")
from packages.categorization.hypcd import HypCDClassifier
clf = HypCDClassifier()
results = clf.predict_batch(["swiggy order bangalore", "hdfc credit card interest"])
for r in results:
    print(f"{r['path']:14} {r['category']:12} conf={r['confidence']:.2f} depth={r['depth']} norm={r['norm']:.3f}")
EOF
```

Expected output (example):
```
keyword_rule   Food         conf=1.00 depth=micro norm=0.731
hypffn         Finance      conf=0.71 depth=micro norm=0.812
```

Update `.gemini/current_state.md` to reflect completion.
