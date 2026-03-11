"""Tests for cleanup automation tasks (M6 toil reduction).

Tests:
- cleanup_stale_training_jobs: marks stuck jobs as failed
- cleanup_old_checkpoints: deletes old .pt files, keeps newest
"""

import os
import time
from unittest.mock import MagicMock, patch

from apps.api.tasks.cleanup_tasks import (
    cleanup_old_checkpoints,
    cleanup_stale_training_jobs,
)


class TestCleanupStaleTrainingJobs:
    """Stale jobs stuck in 'processing' > 1 hour should be auto-failed."""

    @patch("apps.api.core.auth.get_service_client")
    def test_marks_stale_jobs_as_failed(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Simulate 2 stale jobs found
        mock_result = MagicMock()
        mock_result.data = [{"id": "job-1"}, {"id": "job-2"}]
        mock_client.table.return_value.update.return_value.eq.return_value.lt.return_value.execute.return_value = (
            mock_result
        )

        result = cleanup_stale_training_jobs()

        assert result["cleaned_up"] == 2
        mock_client.table.assert_called_with("training_jobs")

    @patch("apps.api.core.auth.get_service_client")
    def test_returns_zero_when_no_stale_jobs(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.update.return_value.eq.return_value.lt.return_value.execute.return_value = (
            mock_result
        )

        result = cleanup_stale_training_jobs()

        assert result["cleaned_up"] == 0

    @patch("apps.api.core.auth.get_service_client")
    def test_handles_service_client_error(self, mock_get_client):
        mock_get_client.side_effect = Exception("Supabase unavailable")

        result = cleanup_stale_training_jobs()

        assert result["cleaned_up"] == 0
        assert "error" in result


class TestCleanupOldCheckpoints:
    """Old checkpoint files should be deleted, keeping the newest per directory."""

    def test_deletes_old_checkpoint_files(self, tmp_path):
        """Files older than max_age_days (except newest) should be deleted."""
        # Create checkpoint files with different ages
        old_file = tmp_path / "old_model.pt"
        old_file.write_bytes(b"old model data")
        old_mtime = time.time() - (60 * 86400)  # 60 days old
        os.utime(old_file, (old_mtime, old_mtime))

        new_file = tmp_path / "new_model.pt"
        new_file.write_bytes(b"new model data")
        # new_file keeps current mtime (just created)

        result = cleanup_old_checkpoints(checkpoint_dir=str(tmp_path), max_age_days=30)

        assert result["deleted_count"] == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_keeps_newest_file_even_if_old(self, tmp_path):
        """Always keep the newest file in each directory, even if over max age."""
        only_file = tmp_path / "only_model.pt"
        only_file.write_bytes(b"data")
        old_mtime = time.time() - (60 * 86400)
        os.utime(only_file, (old_mtime, old_mtime))

        result = cleanup_old_checkpoints(checkpoint_dir=str(tmp_path), max_age_days=30)

        assert result["deleted_count"] == 0
        assert only_file.exists()

    def test_returns_zero_for_missing_directory(self):
        result = cleanup_old_checkpoints(checkpoint_dir="/nonexistent/path", max_age_days=30)

        assert result["deleted_count"] == 0
        assert result["deleted_bytes"] == 0

    def test_ignores_non_checkpoint_files(self, tmp_path):
        """Only .pt and .pth files should be considered."""
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("not a checkpoint")
        old_mtime = time.time() - (60 * 86400)
        os.utime(txt_file, (old_mtime, old_mtime))

        result = cleanup_old_checkpoints(checkpoint_dir=str(tmp_path), max_age_days=30)

        assert result["deleted_count"] == 0
        assert txt_file.exists()
