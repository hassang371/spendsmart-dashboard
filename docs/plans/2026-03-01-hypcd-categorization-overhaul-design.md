# HypCD Categorization Engine Overhaul — Design Doc
**Date:** 2026-03-01
**Status:** Approved

---

## Goal

Bring the `packages/categorization` engine into full compliance with the HypCD research doc (all pipeline stages wired end-to-end), implement a global base model + per-user adapter system, fix all broken/disconnected components, and remove dead code.

---

## 1. Dead Code Removal

| File | Action | Reason |
|---|---|---|
| `backends/mobile.py` | Delete | Deferred to mobile phase |
| `discovery.py` | Delete | Duplicate of `clustering.py` |
| `hyperbolic_nn.py` | Delete | Superseded by inline classes in `hypcd.py` |
| `trainer.py` | Delete | Superseded by `training.py` |
| `losses.py` | Delete | Only used by deleted `trainer.py` |
| `distillation/` | Delete | Not connected to anything |
| `integration_example.py` | Delete | Reference file only |

`cli.py` updated to use `training.py:HypCDTrainer` and remove references to deleted files.

---

## 2. Complete Research Doc Pipeline (All Steps, In Order)

Every call to `HypCDClassifier.predict_batch()` executes this exact sequence:

```
§3.3.1  Step 1:  clean_description()         — regex: strip UPI IDs, dates, ref numbers
§3.3.1  Step 2:  KeywordMatcher.predict()    — fast path, confidence=1.0 on match
                  ↓ (miss only)
§3.4    Step 3:  FinBERT [CLS] embedding     — replaces bert-base-uncased → (768-dim)
§3.5.1  Step 4a: HyperbolicProjector MLP     — 768 → 256 → 128 (Euclidean)
§3.5.2  Step 4b: Feature Clipping            — clip norm < 0.98 (stability)
§3.5.3  Step 4c: expmap0                     — Euclidean → Poincaré ball (128-dim)
§3.6.1  Step 5:  HypFFN forward              — Möbius HypLinear layers → (11-dim logits)
§3.6.2  Step 6:  Softmax in tangent space    — logmap0 → softmax → probabilities
§3.7.1  Step 7:  Confidence threshold check  — if conf >= 0.5 → known category
§3.7.2  Step 8:  GCD routing (conf < 0.5)   — HyperbolicKMeans → novel cluster label
§3.8    Step 9:  Hierarchy norm extraction   — norm = depth, added to output dict
        Step 10: Salary guardrail            — prevent merchant mislabeled as Salary
```

**Output dict** (extended):
```python
{
  "category":    "Food",
  "confidence":  0.91,
  "embedding":   tensor([...]),   # 128-dim hyperbolic vector
  "is_novel":    False,
  "depth":       "micro",         # NEW: "macro" (near center) or "micro" (near boundary)
  "norm":        0.73,            # NEW: hyperbolic norm = hierarchy depth
  "path":        "keyword_rule"   # NEW: "keyword_rule" | "hypffn" | "novel_cluster"
}
```

---

## 3. Backbone: FinBERT

Replace `bert-base-uncased` with `ProsusAI/finbert` in `backends/cloud.py`.
Same 768-dim output, same architecture — drop-in replacement.
Financial domain pretraining improves embedding quality for transaction text.

---

## 4. Checkpoint Loading at Startup

`HypCDClassifier.__init__()` gains checkpoint loading:

```
Priority order:
1. Env var HYPCD_CHECKPOINT_PATH (explicit override)
2. Supabase Storage: models/global/base_model.pt (production)
3. checkpoints/global/base_model.pt (local dev)
4. Random init (first run, no checkpoint exists)
```

Loaded at API startup via the existing `get_classifier()` singleton. No per-request overhead.

---

## 5. Global Base Model + Per-User Adapter System

### 5.1 Architecture

```
FinBERT backbone (440MB, frozen, shared in memory, loaded once at startup)
    ↓
Global HypCD weights (HyperbolicProjector + HypFFN)
    ↓
Per-user adapter override (~0.4MB, loaded per-session, cached in-memory)
```

The per-user adapter IS the projector + classifier state_dict.
It is initialized from global base weights and fine-tuned on the user's corrections.

### 5.2 Storage

```
Supabase Storage bucket: "models"
  models/global/base_model.pt           ← global model (dev team trains)
  models/users/{user_id}/adapter.pt     ← per-user adapter
```

Local dev fallback:
```
checkpoints/global/base_model.pt
checkpoints/users/{user_id}/adapter.pt
```

### 5.3 New Database Table

```sql
CREATE TABLE user_model_metadata (
  user_id        UUID PRIMARY KEY REFERENCES auth.users(id),
  adapter_url    TEXT,           -- Supabase Storage path
  correction_count INT DEFAULT 0,
  adapter_updated_at TIMESTAMPTZ,
  created_at     TIMESTAMPTZ DEFAULT now()
);
```

### 5.4 Global Model Training (CLI)

```bash
python -m packages.categorization.cli train-global \
  --epochs 50 \
  --output checkpoints/global/base_model.pt \
  --upload  # optional: push to Supabase Storage after training
```

Fetches all `is_manual=True` corrections from all users (anonymized descriptions + categories).
Runs full supervised training pipeline (`training_pipeline.py`).
Saves checkpoint locally; `--upload` flag pushes to Supabase Storage.

---

## 6. Merchant-Batch Reclassification (New Behavior)

When user corrects transaction T (e.g., Swiggy: Transport → Food):

```
1. Extract merchant keyword from cleaned description
   clean_description(T.description) → "SWIGGY ORDER" → keyword: "swiggy"

2. Batch update in Supabase:
   UPDATE transactions
   SET category = 'Food', is_manual = True
   WHERE user_id = {user_id}
     AND category = 'Transport'
     AND description ILIKE '%swiggy%'

3. Load user's adapter from Supabase Storage
   (or init from global base if first-time user)

4. Fine-tune adapter on all newly labeled examples
   (swiggy descriptions, "Food") pairs

5. Save updated adapter to Supabase Storage
   models/users/{user_id}/adapter.pt

6. Update user_model_metadata: correction_count++, adapter_updated_at=now()

7. Return { updated_count: N, new_category: "Food" } to API caller
```

**Frontend change:** Remove the "Reclassify all associated transactions?" prompt.
Auto-reclassify is the default behaviour.

---

## 7. Training System

### 7.1 Contrastive Pretraining (Unsupervised — triggered at import time)

- No labels required — uses augmented positive pairs
- Updates HyperbolicProjector weights only
- Runs as a background task after `POST /ingest/import` completes
- Implements dynamic λ schedule: ramps from 0.0 → 0.5 over first 20% of epochs (angle loss first, then distance loss enforcement)
- Uses `training.py:HypCDTrainer.hybrid_loss()` with InfoNCE-style negatives

### 7.2 Supervised Fine-Tuning (Labeled — triggered after merchant-batch reclassification)

- Uses `is_manual=True` transactions as ground truth
- Updates both HyperbolicProjector and HypFFN
- Runs immediately after merchant-batch reclassification (batch is already large enough)
- Uses `training_pipeline.py:HierarchicalLoss` (cross-entropy + hierarchy penalty)

### 7.3 Dynamic λ Schedule (fixes static lambda issue)

```python
def get_lambda(epoch: int, total_epochs: int) -> float:
    warmup = int(0.2 * total_epochs)
    if epoch < warmup:
        return 0.0 + 0.5 * (epoch / warmup)  # Ramp 0→0.5
    return 0.5  # Hold at 0.5
```

---

## 8. Evaluation Metrics

### 8.1 New API Endpoint

`GET /categorization/metrics` (authenticated, per-user)

Response:
```json
{
  "overall_accuracy": 0.87,
  "per_class": {
    "Food": {"precision": 0.94, "recall": 0.91, "f1": 0.92, "support": 145}
  },
  "confidence_histogram": {"0.0-0.2": 12, "0.2-0.4": 8, "0.4-0.6": 23, "0.6-0.8": 89, "0.8-1.0": 141},
  "rule_vs_model_split": {"keyword_rule": 312, "hypffn": 188, "novel_cluster": 5},
  "novel_categories_discovered": 3,
  "adapter_version": "2026-03-01T14:23:00",
  "total_corrections": 47
}
```

Ground truth: user's `is_manual=True` transactions.

### 8.2 Training Metrics (per epoch)

Tracked in `training_pipeline.py`:
- Training loss (hybrid: distance + angle)
- Validation loss
- Per-class F1, precision, recall on validation split
- Top-K accuracy (K=2,3)
- Confidence calibration score

Saved to `checkpoints/metrics_history.json`.

---

## 9. On Collecting User Weights for Global Training

**Do not collect user adapter weights.** Averaging per-user adapter weights (federated learning) introduces noise from heterogeneous spending patterns and degrades global accuracy.

**Correct approach:** Collect anonymized labeled corrections (description + category) from users who opt in. Use this as training data for the global base model. Clean labeled data trains a better global model than averaged weights.

The global model benefits from *data diversity*, not *weight averaging*.

---

## 10. Files Affected

### Deleted
- `packages/categorization/backends/mobile.py`
- `packages/categorization/discovery.py`
- `packages/categorization/hyperbolic_nn.py`
- `packages/categorization/trainer.py`
- `packages/categorization/losses.py`
- `packages/categorization/distillation/` (directory)
- `packages/categorization/integration_example.py`

### Modified
- `packages/categorization/backends/cloud.py` — FinBERT, checkpoint loading
- `packages/categorization/hypcd.py` — full pipeline steps 7-9, checkpoint loading, adapter support
- `packages/categorization/training.py` — dynamic λ schedule
- `packages/categorization/training_pipeline.py` — per-class F1, top-K, calibration metrics
- `packages/categorization/cli.py` — remove dead imports, add train-global command
- `apps/api/domains/accounts/router.py` — merchant-batch reclassification, remove "reclassify all?" prompt
- `apps/api/domains/ingestion/router.py` — trigger contrastive pretraining post-import
- `apps/api/domains/categorization/` — new metrics endpoint

### New Files
- `packages/categorization/adapter_manager.py` — load/save/fine-tune per-user adapters
- `apps/api/domains/categorization/router.py` — `GET /categorization/metrics`
- `supabase/migrations/YYYYMMDD_user_model_metadata.sql` — new table

---

## Verification Checklist

- [ ] All 10 pipeline steps execute on every `predict_batch()` call
- [ ] FinBERT loads successfully, embeddings are 768-dim
- [ ] Checkpoint loads from Supabase Storage on cold start
- [ ] Merchant-batch reclassification auto-updates all matching transactions
- [ ] Per-user adapter saved/loaded from Supabase Storage
- [ ] Contrastive pretraining triggers after import
- [ ] Supervised fine-tuning triggers after reclassification
- [ ] Dynamic λ schedule ramps correctly
- [ ] `GET /categorization/metrics` returns valid F1 scores
- [ ] `train-global` CLI command runs end-to-end
- [ ] All deleted files are removed
- [ ] No broken imports remain
- [ ] All existing tests still pass
