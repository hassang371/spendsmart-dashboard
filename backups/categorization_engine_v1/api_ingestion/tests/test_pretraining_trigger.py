"""Test that contrastive pretraining is triggered after a successful import."""


def test_contrastive_pretraining_queued_after_import():
    """_run_contrastive_pretraining_bg must exist in the ingestion router module."""
    from apps.api.domains.ingestion import router as ingestion_module

    assert hasattr(ingestion_module, "_run_contrastive_pretraining_bg"), (
        "Missing _run_contrastive_pretraining_bg function — "
        "contrastive pretraining not triggered post-import"
    )
