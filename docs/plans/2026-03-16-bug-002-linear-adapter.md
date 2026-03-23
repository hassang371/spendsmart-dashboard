# BUG-002: Linear Adapter Broken Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all five root causes that prevent per-user Linear Adapters from being trained, stored, and applied during classification.

**Architecture:** Five sequential fixes: (1) DB migration adds `"queued"` to `training_jobs` status constraint; (2) an atomic `upsert_model_metadata` RPC replaces read-modify-write and is called by `save_version()`; (3) the accounts background task replaces the dead-code `AdapterManager` path with the `model_registry` path that `load_latest()` can find; (4) the feedback endpoint propagates corrections to `transactions` so the training pipeline can consume them; (5) `adapter_manager.py` is deleted.

**Tech Stack:** Python 3.11, FastAPI, Supabase (postgrest-py client), PyTorch (state_dict serialisation), pytest, Supabase migrations (SQL)

---

## Chunk 1: Database fixes + atomic metadata write

### Task 1: DB migration — add `"queued"` to `training_jobs` status constraint (Bug 5)

**Files:**
- Create: `supabase/migrations/20260316000001_fix_training_jobs_status_constraint.sql`
- Modify: `architecture/schema.sql` lines 157-159
- Create: `apps/api/tests/test_training_jobs_constraint.py`

- [ ] **Step 1: Write the failing test**

  The test asserts that the migration file exists and contains `'queued'`. It fails before
  the migration file is created (Step 3) and passes after.

  File: `apps/api/tests/test_training_jobs_constraint.py`

  ```python
  """Regression: training_jobs status constraint must allow 'queued'.

  Bug 5: the CHECK constraint excluded 'queued', blocking every
  POST /training/train and POST /training/upload at the DB insert step.
  """
  from pathlib import Path


  def test_status_constraint_migration_adds_queued():
      """Migration 20260316000001 must exist and add 'queued' to the allowed set."""
      migration = Path(
          "supabase/migrations/20260316000001_fix_training_jobs_status_constraint.sql"
      )
      assert migration.exists(), (
          "Migration 20260316000001_fix_training_jobs_status_constraint.sql "
          "must exist to fix Bug 5."
      )
      content = migration.read_text()
      assert "'queued'" in content, (
          "Migration must include 'queued' in the status constraint."
      )


  def test_training_router_uses_queued_status_string():
      """The training router must insert status='queued', not an invalid value."""
      import inspect
      from apps.api.domains.training import router as training_router

      source = inspect.getsource(training_router)
      assert '"queued"' in source or "'queued'" in source, (
          "training/router.py must use 'queued' as the insert status string."
      )
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  cd "/Users/mohammedhassanmohiddin/Documents/Antigravity/SCALE APP"
  .venv/bin/python -m pytest apps/api/tests/test_training_jobs_constraint.py -v
  ```

  Expected: FAIL — `test_status_constraint_migration_adds_queued` fails because the
  migration file does not exist yet.

- [ ] **Step 3: Write the migration**

  File: `supabase/migrations/20260316000001_fix_training_jobs_status_constraint.sql`

  ```sql
  -- Migration: Fix training_jobs status CHECK constraint
  -- Bug 5: 'queued' was missing from the allowed set, causing every
  -- POST /training/train and POST /training/upload to fail.

  ALTER TABLE public.training_jobs
      DROP CONSTRAINT IF EXISTS training_jobs_status_check;

  ALTER TABLE public.training_jobs
      ADD CONSTRAINT training_jobs_status_check
      CHECK (status = ANY (ARRAY[
          'pending'::text, 'queued'::text, 'running'::text,
          'processing'::text, 'completed'::text, 'failed'::text
      ]));
  ```

- [ ] **Step 4: Sync `architecture/schema.sql`**

  In `architecture/schema.sql`, find lines 158-159 (the existing constraint):

  ```sql
  CONSTRAINT training_jobs_status_check
      CHECK (status = ANY (ARRAY['pending'::text, 'running'::text, 'processing'::text, 'completed'::text, 'failed'::text]))
  ```

  Replace with:

  ```sql
  CONSTRAINT training_jobs_status_check
      CHECK (status = ANY (ARRAY['pending'::text, 'queued'::text, 'running'::text, 'processing'::text, 'completed'::text, 'failed'::text]))
  ```

- [ ] **Step 5: Apply migration locally**

  ```bash
  cd "/Users/mohammedhassanmohiddin/Documents/Antigravity/SCALE APP"
  npx supabase db push
  ```

  Expected: migration applied with no errors.

- [ ] **Step 6: Run tests to verify they pass**

  ```bash
  .venv/bin/python -m pytest apps/api/tests/test_training_jobs_constraint.py -v
  ```

  Expected: both tests PASS.

- [ ] **Step 7: Commit**

  ```bash
  git add supabase/migrations/20260316000001_fix_training_jobs_status_constraint.sql \
          architecture/schema.sql \
          apps/api/tests/test_training_jobs_constraint.py
  git commit -m "fix(db): add 'queued' to training_jobs status constraint

  Bug 5: CHECK constraint excluded 'queued', blocking every training
  job insert. Adds migration + syncs architecture/schema.sql.

  Refs: docs/bugs/BUG-002-linear-adapter-broken-pipeline.md"
  ```

---

### Task 2: Add `upsert_model_metadata` RPC for atomic metadata write (Bug 1)

`save_version()` needs to atomically update `user_model_metadata` (url + timestamp + increment
correction_count) after every Storage upload. A plain read-modify-write has a race condition
if two training runs complete simultaneously for the same user. A Postgres RPC handles this
with a single `INSERT … ON CONFLICT DO UPDATE` that increments atomically.

**Files:**
- Create: `supabase/migrations/20260316000002_upsert_model_metadata_rpc.sql`
- Modify: `packages/categorization/model_registry.py`
- Modify: `supabase/migrations/20260301000000_user_model_metadata.sql` (fix comment, line 6)
- Create: `packages/categorization/tests/test_model_registry.py`

- [ ] **Step 1: Write the failing tests**

  File: `packages/categorization/tests/test_model_registry.py`

  ```python
  """Tests for model_registry — save_version must write user_model_metadata atomically.

  Bug 1: save_version() uploaded to Storage but never populated
  user_model_metadata, so load_latest() never found any adapter.
  """
  from unittest.mock import MagicMock, call
  import pytest


  def _make_client():
      """Minimal Supabase client mock where storage upload and rpc succeed."""
      client = MagicMock()
      client.storage.from_.return_value.upload.return_value = None
      client.rpc.return_value.execute.return_value = MagicMock(data=None)
      return client


  def test_save_version_calls_upsert_model_metadata_rpc():
      """save_version() must call the upsert_model_metadata RPC after upload."""
      import torch
      from packages.categorization.model_registry import save_version

      client = _make_client()
      state_dict = {"weight": torch.zeros(2, 2)}

      version = save_version(client, "user-abc", state_dict, metrics={"samples": 3})

      client.rpc.assert_called_once()
      rpc_name = client.rpc.call_args.args[0]
      assert rpc_name == "upsert_model_metadata", (
          f"Expected RPC 'upsert_model_metadata', got '{rpc_name}'"
      )

      rpc_params = client.rpc.call_args.args[1]
      assert rpc_params["p_user_id"] == "user-abc"
      assert "user-abc/v_" in rpc_params["p_adapter_url"]
      assert rpc_params["p_adapter_url"].endswith("/adapter.pt")


  def test_save_version_passes_correction_count_delta_to_rpc():
      """correction_count_delta is forwarded to the RPC for atomic increment."""
      import torch
      from packages.categorization.model_registry import save_version

      client = _make_client()
      state_dict = {"weight": torch.zeros(2, 2)}

      save_version(client, "user-abc", state_dict, correction_count_delta=7)

      rpc_params = client.rpc.call_args.args[1]
      assert rpc_params["p_count_delta"] == 7


  def test_save_version_metadata_failure_is_nonfatal():
      """If the RPC raises, save_version still returns a valid ModelVersion."""
      import torch
      from packages.categorization.model_registry import save_version

      client = _make_client()
      # RPC raises — simulates DB connectivity issue
      client.rpc.return_value.execute.side_effect = Exception("connection refused")

      state_dict = {"weight": torch.zeros(2, 2)}
      version = save_version(client, "user-abc", state_dict)

      # Must still return a ModelVersion (not raise)
      assert version is not None
      assert version.user_id == "user-abc"
      assert version.storage_path.startswith("user-abc/v_")
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  cd "/Users/mohammedhassanmohiddin/Documents/Antigravity/SCALE APP"
  .venv/bin/python -m pytest packages/categorization/tests/test_model_registry.py -v
  ```

  Expected: FAIL — `save_version` does not call any RPC yet.

- [ ] **Step 3: Write the RPC migration**

  File: `supabase/migrations/20260316000002_upsert_model_metadata_rpc.sql`

  ```sql
  -- Migration: Atomic upsert_model_metadata RPC
  -- Bug 1: save_version() never populated user_model_metadata.
  -- This RPC atomically sets adapter_url + adapter_updated_at and
  -- increments correction_count in a single statement, eliminating
  -- the read-modify-write race condition.

  CREATE OR REPLACE FUNCTION public.upsert_model_metadata(
      p_user_id        UUID,
      p_adapter_url    TEXT,
      p_count_delta    INT DEFAULT 0
  )
  RETURNS void
  LANGUAGE sql
  SECURITY DEFINER
  AS $$
      INSERT INTO public.user_model_metadata
          (user_id, adapter_url, adapter_updated_at, correction_count)
      VALUES
          (p_user_id, p_adapter_url, NOW(), p_count_delta)
      ON CONFLICT (user_id)
      DO UPDATE SET
          adapter_url        = EXCLUDED.adapter_url,
          adapter_updated_at = EXCLUDED.adapter_updated_at,
          correction_count   = public.user_model_metadata.correction_count
                               + EXCLUDED.correction_count;
  $$;

  -- Grant execute to service_role (used by background tasks)
  GRANT EXECUTE ON FUNCTION public.upsert_model_metadata TO service_role;
  ```

- [ ] **Step 4: Apply the migration**

  ```bash
  npx supabase db push
  ```

  Expected: applied with no errors.

- [ ] **Step 5: Update `save_version()` to call the RPC**

  Replace the full body of `save_version` in
  `packages/categorization/model_registry.py`:

  ```python
  def save_version(
      client: Client,
      user_id: str,
      adapter_state_dict: Dict[str, Any],
      metrics: Optional[Dict[str, Any]] = None,
      correction_count_delta: int = 0,
  ) -> ModelVersion:
      """Save a new model version to Supabase Storage and atomically update
      user_model_metadata via the upsert_model_metadata RPC.
      """
      import torch

      version_id = f"v_{int(datetime.now().timestamp())}"
      storage_path = f"{user_id}/{version_id}/adapter.pt"

      buffer = io.BytesIO()
      torch.save(adapter_state_dict, buffer)
      buffer.seek(0)

      try:
          client.storage.from_("models").upload(
              storage_path,
              buffer.read(),
              file_options={"content-type": "application/octet-stream"},
          )
          logger.info("model_saved", user_id=user_id, version_id=version_id)
      except Exception as e:
          logger.error("model_save_failed", error=str(e))
          raise

      # Atomically update user_model_metadata (url + timestamp + count increment).
      # Non-fatal: if the RPC fails, the adapter is still saved to Storage.
      try:
          client.rpc(
              "upsert_model_metadata",
              {
                  "p_user_id": user_id,
                  "p_adapter_url": storage_path,
                  "p_count_delta": correction_count_delta,
              },
          ).execute()
          logger.info(
              "user_model_metadata_updated",
              user_id=user_id,
              storage_path=storage_path,
              count_delta=correction_count_delta,
          )
      except Exception as e:
          logger.error(
              "user_model_metadata_rpc_failed",
              user_id=user_id,
              storage_path=storage_path,
              error=str(e),
          )

      return ModelVersion(
          version_id=version_id,
          user_id=user_id,
          created_at=datetime.utcnow().isoformat(),
          metrics=metrics or {},
          storage_path=storage_path,
      )
  ```

- [ ] **Step 6: Fix wrong storage path comment in migration**

  In `supabase/migrations/20260301000000_user_model_metadata.sql`, change line 6:

  ```sql
  adapter_url      TEXT,           -- Supabase Storage path: users/{user_id}/adapter.pt
  ```

  To:

  ```sql
  adapter_url      TEXT,           -- Supabase Storage path: {user_id}/v_{timestamp}/adapter.pt
  ```

- [ ] **Step 7: Run tests**

  ```bash
  .venv/bin/python -m pytest packages/categorization/tests/test_model_registry.py -v
  ```

  Expected: all 3 tests PASS.

- [ ] **Step 8: Run full categorization test suite**

  ```bash
  .venv/bin/python -m pytest packages/categorization/tests/ -v
  ```

  Expected: all pass.

- [ ] **Step 9: Commit**

  ```bash
  git add supabase/migrations/20260316000002_upsert_model_metadata_rpc.sql \
          supabase/migrations/20260301000000_user_model_metadata.sql \
          packages/categorization/model_registry.py \
          packages/categorization/tests/test_model_registry.py
  git commit -m "fix(categorization): save_version atomically writes user_model_metadata via RPC

  Bug 1: save_version() never populated user_model_metadata, so classify
  calls always fell back to the base model. Adds upsert_model_metadata
  RPC (atomic INSERT ON CONFLICT) and calls it after every Storage upload.
  Also fixes wrong storage path comment in migration 20260301.

  Refs: docs/bugs/BUG-002-linear-adapter-broken-pipeline.md"
  ```

---

## Chunk 2: Fix background task + training_tasks + feedback endpoint

### Task 3: Replace `AdapterManager` in background task + fix Celery task (Bugs 2 + 3)

`_run_supervised_finetuning_bg` saves to `users/{user_id}/adapter.pt` via `AdapterManager`.
`load_latest()` scans `{user_id}/v_*` — it never finds anything saved by the background task.
Replace with the `get_classifier()` singleton + `model_registry.save_version()`.

Also update `training_tasks.py` (Celery path) to pass `correction_count_delta` to `save_version()`.

**Files:**
- Modify: `apps/api/domains/accounts/router.py` lines 39-71 (rewrite `_run_supervised_finetuning_bg`)
- Modify: `apps/api/tasks/training_tasks.py` lines 80-89 (add `correction_count_delta`)
- Create: `apps/api/tests/test_finetuning_bg.py`

- [ ] **Step 1: Write the failing tests**

  File: `apps/api/tests/test_finetuning_bg.py`

  ```python
  """Regression: background finetuning must use model_registry, not AdapterManager.

  Bug 2+3: _run_supervised_finetuning_bg used AdapterManager which saved to
  users/{user_id}/adapter.pt — a path load_latest() never scans.
  After fix, it must call save_version() which saves to {user_id}/v_*.
  """
  from unittest.mock import MagicMock, patch
  import inspect


  def test_background_task_does_not_use_adapter_manager():
      """Source of _run_supervised_finetuning_bg must not import AdapterManager."""
      from apps.api.domains.accounts.router import _run_supervised_finetuning_bg

      source = inspect.getsource(_run_supervised_finetuning_bg)
      assert "AdapterManager" not in source, (
          "_run_supervised_finetuning_bg still uses AdapterManager — "
          "must use model_registry.save_version() instead."
      )
      assert "save_version" in source, (
          "_run_supervised_finetuning_bg must call save_version()."
      )


  def test_background_task_calls_save_version_with_correct_args():
      """save_version is called with user_id and correction_count_delta=len(texts)."""
      # These patches work because Step 3 changes the function to use module-level imports
      with (
          patch("apps.api.domains.accounts.router.get_classifier") as mock_gc,
          patch("apps.api.domains.accounts.router.save_version") as mock_sv,
          patch("apps.api.domains.accounts.router.get_service_client") as mock_client,
      ):
          mock_adapter = MagicMock()
          mock_adapter.state_dict.return_value = {"w": "data"}
          mock_gc.return_value.train_adapter.return_value = mock_adapter
          mock_sv.return_value = MagicMock(storage_path="user-xyz/v_1/adapter.pt")

          from apps.api.domains.accounts.router import _run_supervised_finetuning_bg
          _run_supervised_finetuning_bg(
              user_id="user-xyz",
              texts=["lunch", "swiggy"],
              categories=["Food", "Food"],
          )

      mock_sv.assert_called_once()
      kwargs = mock_sv.call_args.kwargs
      assert kwargs["user_id"] == "user-xyz"
      assert kwargs["correction_count_delta"] == 2  # len(texts)


  def test_training_tasks_passes_correction_count_delta():
      """train_adapter_task must pass correction_count_delta=len(texts) to save_version."""
      import inspect
      from apps.api.tasks import training_tasks

      source = inspect.getsource(training_tasks.train_adapter_task)
      assert "correction_count_delta" in source, (
          "train_adapter_task must pass correction_count_delta to save_version()."
      )
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  .venv/bin/python -m pytest apps/api/tests/test_finetuning_bg.py -v
  ```

  Expected: FAIL — source contains `AdapterManager`, `save_version` not called.

- [ ] **Step 3: Rewrite `_run_supervised_finetuning_bg` with module-level imports**

  In `apps/api/domains/accounts/router.py`, add these imports at the **top of the file**
  (after existing imports):

  ```python
  from apps.api.core.auth import get_service_client
  from apps.api.domains.categorization.service import get_classifier
  from packages.categorization.model_registry import save_version
  ```

  Then replace the function body at lines 39-71:

  ```python
  def _run_supervised_finetuning_bg(
      user_id: str,
      texts: list[str],
      categories: list[str],
  ) -> None:
      """Background task: supervised fine-tuning of user's Linear Adapter.

      Uses the classifier singleton (no re-instantiation of MiniLM) and saves
      via model_registry.save_version() to the versioned path that load_latest()
      can find. Writes user_model_metadata atomically via the RPC.
      """
      if not texts or len(texts) != len(categories):
          return

      try:
          classifier = get_classifier()
          adapter = classifier.train_adapter(
              texts=texts,
              categories=categories,
              epochs=5,
          )

          client = get_service_client()
          save_version(
              client=client,
              user_id=user_id,
              adapter_state_dict=adapter.state_dict(),
              metrics={"samples": len(texts), "source": "bg_finetuning"},
              correction_count_delta=len(texts),
          )

          logger.info(
              "supervised_finetuning_complete",
              user_id=user_id,
              examples=len(texts),
          )
      except Exception as e:
          logger.warning("supervised_finetuning_failed", user_id=user_id, error=str(e))
  ```

- [ ] **Step 4: Update `training_tasks.py` to pass `correction_count_delta`**

  In `apps/api/tasks/training_tasks.py`, update the `save_version()` call (lines 80-89):

  ```python
  version_record = save_version(
      client=client,
      user_id=user_id,
      adapter_state_dict=adapter.state_dict(),
      metrics={
          "epochs": epochs,
          "learning_rate": learning_rate,
          "samples": len(texts),
      },
      correction_count_delta=len(texts),
  )
  ```

- [ ] **Step 5: Run tests**

  ```bash
  .venv/bin/python -m pytest apps/api/tests/test_finetuning_bg.py -v
  ```

  Expected: all 3 tests PASS.

- [ ] **Step 6: Run broader suite**

  ```bash
  .venv/bin/python -m pytest apps/api/tests/ packages/categorization/tests/ -v --tb=short
  ```

  Expected: all pass.

- [ ] **Step 7: Commit**

  ```bash
  git add apps/api/domains/accounts/router.py \
          apps/api/tasks/training_tasks.py \
          apps/api/tests/test_finetuning_bg.py
  git commit -m "fix(accounts): replace AdapterManager with model_registry in bg task

  Bugs 2+3: _run_supervised_finetuning_bg saved adapters to the wrong
  Storage path (users/{user_id}/adapter.pt) which load_latest() never
  scans. Now uses get_classifier() singleton + save_version() which saves
  to {user_id}/v_{ts}/adapter.pt. Also passes correction_count_delta
  from train_adapter_task (Celery path).

  Refs: docs/bugs/BUG-002-linear-adapter-broken-pipeline.md"
  ```

---

### Task 4: Fix feedback endpoint to propagate `is_manual=True` to transactions (Bug 4)

`POST /categorization/feedback` writes to `training_corrections` but never sets
`is_manual=True` on the matching transactions. `POST /training/train` reads
`transactions WHERE is_manual=True` — so feedback corrections are silently ignored.

**Files:**
- Modify: `apps/api/domains/categorization/router.py` lines 137-143
- Create: `apps/api/tests/test_feedback_updates_transactions.py`

- [ ] **Step 1: Write the failing test**

  File: `apps/api/tests/test_feedback_updates_transactions.py`

  ```python
  """Regression: POST /categorization/feedback must set is_manual=True on transactions.

  Bug 4: feedback endpoint only wrote to training_corrections. The training
  pipeline reads transactions WHERE is_manual=True — corrections were ignored.
  """
  from unittest.mock import MagicMock, patch
  import inspect


  def test_feedback_handler_updates_transactions():
      """submit_feedback must update the transactions table after storing corrections."""
      import inspect
      from apps.api.domains.categorization.router import submit_feedback

      source = inspect.getsource(submit_feedback)
      assert '"transactions"' in source or "'transactions'" in source, (
          "submit_feedback must update the 'transactions' table to set is_manual=True."
      )
      assert "is_manual" in source, (
          "submit_feedback must set is_manual=True on matching transactions."
      )


  def test_feedback_calls_transactions_update_for_each_correction():
      """One transactions.update() call is made per correction description."""
      import asyncio
      from apps.api.domains.categorization.router import submit_feedback
      from apps.api.domains.categorization.schemas import FeedbackRequest

      client_mock = MagicMock()
      # training_corrections insert
      client_mock.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
      # transactions update chain: .update().eq().eq().execute()
      update_chain = MagicMock()
      client_mock.table.return_value.update.return_value = update_chain
      update_chain.eq.return_value = update_chain
      update_chain.execute.return_value = MagicMock(data=[])

      req = FeedbackRequest(corrections={"Swiggy order": "Food", "Uber ride": "Transport"})
      # Call the handler directly — user_id and client injected as kwargs (bypasses Depends)
      asyncio.run(submit_feedback(req, user_id="uid-1", client=client_mock))

      # One update call per correction
      update_calls = [
          c for c in client_mock.table.call_args_list
          if c.args and c.args[0] == "transactions"
      ]
      assert len(update_calls) >= 2, (
          f"Expected 2 transaction update calls, got {len(update_calls)}"
      )
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  .venv/bin/python -m pytest apps/api/tests/test_feedback_updates_transactions.py -v
  ```

  Expected: FAIL — source does not contain `transactions` or `is_manual` yet.

- [ ] **Step 3: Implement the fix in `submit_feedback`**

  In `apps/api/domains/categorization/router.py`, after the `training_corrections` insert
  (after line 138):

  ```python
  try:
      client.table("training_corrections").insert(rows_to_insert).execute()
  except Exception:
      raise HTTPException(status_code=500, detail="Failed to store feedback")

  # Propagate corrections to transactions so POST /training/train can consume them.
  # training/router.py reads transactions WHERE is_manual=True.
  for row in rows_to_insert:
      try:
          client.table("transactions").update(
              {"is_manual": True, "category": row["corrected_category"]}
          ).eq("user_id", user_id).eq("description", row["description"]).execute()
      except Exception as e:
          # Non-fatal: correction stored; transaction update failure logged only.
          logger.warning(
              "feedback_transaction_update_failed",
              description=row["description"],
              error=str(e),
          )
  ```

- [ ] **Step 4: Run tests**

  ```bash
  .venv/bin/python -m pytest apps/api/tests/test_feedback_updates_transactions.py -v
  ```

  Expected: both tests PASS.

- [ ] **Step 5: Run full API test suite**

  ```bash
  .venv/bin/python -m pytest apps/api/tests/ -v --tb=short
  ```

  Expected: all pass.

- [ ] **Step 6: Commit**

  ```bash
  git add apps/api/domains/categorization/router.py \
          apps/api/tests/test_feedback_updates_transactions.py
  git commit -m "fix(categorization): feedback endpoint sets is_manual=True on transactions

  Bug 4: training_corrections was write-only — POST /training/train reads
  transactions WHERE is_manual=True, never training_corrections. Now
  feedback endpoint also updates matching transaction rows so corrections
  reach the training pipeline.

  Refs: docs/bugs/BUG-002-linear-adapter-broken-pipeline.md"
  ```

---

## Chunk 3: Cleanup + verification

### Task 5: Delete `adapter_manager.py` (Fix 5)

`AdapterManager` has zero callers after Task 3. Delete it to eliminate the wrong
Storage path from the codebase entirely.

**Files:**
- Delete: `packages/categorization/adapter_manager.py`

- [ ] **Step 1: Confirm no remaining imports**

  ```bash
  grep -r "adapter_manager\|AdapterManager" \
    apps/ packages/ \
    --include="*.py" \
    --exclude-dir=.venv
  ```

  Expected: no output. If any matches appear, update those files before proceeding.

- [ ] **Step 2: Delete the file**

  ```bash
  git rm "packages/categorization/adapter_manager.py"
  ```

- [ ] **Step 3: Run full test suite**

  ```bash
  .venv/bin/python -m pytest apps/ packages/ -v --tb=short
  ```

  Expected: all pass, no `ImportError` for `adapter_manager`.

- [ ] **Step 4: Commit**

  ```bash
  git commit -m "refactor(categorization): delete dead-code AdapterManager

  Bug 3: AdapterManager had no callers after fixing _run_supervised_finetuning_bg.
  Removes the wrong Storage path (users/{user_id}/adapter.pt) from the codebase.

  Refs: docs/bugs/BUG-002-linear-adapter-broken-pipeline.md"
  ```

---

### Task 6: Update BUG-002 status + HLD sync

- [ ] **Step 1: Update BUG-002 status to `Fix Applied`**

  In `docs/bugs/BUG-002-linear-adapter-broken-pipeline.md`, change:

  ```
  > **Status:** Root Cause Found
  ```

  To:

  ```
  > **Status:** Fix Applied
  ```

  Append to Changelog:

  ```
  | 2026-03-16 | Fix Applied — Bug 5: migration 20260316000001; Bug 1: migration 20260316000002 + save_version RPC call; Bugs 2+3: bg task rewrite + correction_count_delta in Celery task; Bug 4: feedback→transactions propagation; cleanup: AdapterManager deleted |
  ```

- [ ] **Step 2: Update `docs/design/system-architecture.md` ML pipeline section**

  Find any reference to `AdapterManager` or `users/{user_id}/adapter.pt` in the ML pipeline
  section and replace with: "Per-user adapters saved via `model_registry.save_version()`
  to `{user_id}/v_{timestamp}/adapter.pt`. `user_model_metadata` updated atomically via
  `upsert_model_metadata` RPC after each save."

  Add a Changelog entry to `system-architecture.md`:

  ```
  | 2026-03-16 | BUG-002 fix: AdapterManager removed; single save path is model_registry.save_version(). upsert_model_metadata RPC ensures atomic metadata write. |
  ```

- [ ] **Step 3: Run `make check` (full DoD check)**

  ```bash
  cd "/Users/mohammedhassanmohiddin/Documents/Antigravity/SCALE APP"
  make check
  ```

  Expected: lint + tsc + pytest all pass.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/bugs/BUG-002-linear-adapter-broken-pipeline.md \
          docs/design/system-architecture.md
  git commit -m "docs: mark BUG-002 Fix Applied, sync system-architecture HLD

  Refs: docs/bugs/BUG-002-linear-adapter-broken-pipeline.md"
  ```

---

## Execution order summary

```
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6
  DB      RPC +    bg task  feedback  delete   status
  fix    save_v   rewrite  endpoint  AdpMgr   update
```

Tasks 1-4 are sequential (each builds on the previous). Task 5 depends on Task 3 being
committed first (removes the only remaining caller of AdapterManager). Task 6 closes the loop.
