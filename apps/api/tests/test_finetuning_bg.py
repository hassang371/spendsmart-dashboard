"""Regression: background finetuning must use model_registry, not AdapterManager.

Bug 2+3: _run_supervised_finetuning_bg used AdapterManager which saved to
users/{user_id}/adapter.pt — a path load_latest() never scans.
After fix, it must call save_version() which saves to {user_id}/v_*.
"""

import inspect
from unittest.mock import MagicMock, patch


def test_background_task_does_not_use_adapter_manager():
    """Source of _run_supervised_finetuning_bg must not import AdapterManager."""
    from apps.api.domains.accounts.router import _run_supervised_finetuning_bg

    source = inspect.getsource(_run_supervised_finetuning_bg)
    assert "AdapterManager" not in source, (
        "_run_supervised_finetuning_bg still uses AdapterManager — " "must use model_registry.save_version() instead."
    )
    assert "save_version" in source, "_run_supervised_finetuning_bg must call save_version()."


def test_background_task_calls_save_version_with_correct_args():
    """save_version is called with user_id and correction_count_delta=len(texts)."""
    # These patches work because the function uses module-level imports
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
    assert "correction_count_delta" in source, "train_adapter_task must pass correction_count_delta to save_version()."
