"""Regression: training_jobs status constraint must allow 'queued'.

Bug 5: the CHECK constraint excluded 'queued', blocking every
POST /training/train and POST /training/upload at the DB insert step.
"""

from pathlib import Path


def test_status_constraint_migration_adds_queued():
    """Migration 20260316000001 must exist and add 'queued' to the allowed set."""
    migration = Path("supabase/migrations/20260316000001_fix_training_jobs_status_constraint.sql")
    assert migration.exists(), (
        "Migration 20260316000001_fix_training_jobs_status_constraint.sql " "must exist to fix Bug 5."
    )
    content = migration.read_text()
    assert "'queued'" in content, "Migration must include 'queued' in the status constraint."


def test_training_router_uses_queued_status_string():
    """The training router must insert status='queued', not an invalid value."""
    import inspect

    from apps.api.domains.training import router as training_router

    source = inspect.getsource(training_router)
    assert (
        '"queued"' in source or "'queued'" in source
    ), "training/router.py must use 'queued' as the insert status string."
