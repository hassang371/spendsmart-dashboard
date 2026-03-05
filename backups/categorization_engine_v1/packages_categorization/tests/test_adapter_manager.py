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
    """Returns None when no global checkpoint exists locally and Supabase is not configured."""
    from packages.categorization.adapter_manager import AdapterManager
    mgr = AdapterManager(supabase_url="", supabase_key="", local_dir=str(tmp_path))
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
