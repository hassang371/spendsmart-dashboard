"""Tests for model_registry — save_version must write user_model_metadata atomically.

Bug 1: save_version() uploaded to Storage but never populated
user_model_metadata, so load_latest() never found any adapter.
"""

from unittest.mock import MagicMock

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
    assert rpc_name == "upsert_model_metadata", f"Expected RPC 'upsert_model_metadata', got '{rpc_name}'"

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
