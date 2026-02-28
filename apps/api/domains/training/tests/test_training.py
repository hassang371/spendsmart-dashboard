"""Tests for training domain — BUG-01 verification."""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestUpdateJobStatus:
    """BUG-01 fix: Celery task should update DB with job status."""

    @patch("apps.api.core.auth.get_service_client")
    def test_update_job_status_completed(self, mock_get_client):
        """_update_job_status should write 'completed' to training_jobs."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        from apps.api.tasks.training_tasks import _update_job_status

        _update_job_status(
            job_id="test-job-123",
            status="completed",
            metrics={"accuracy": 0.95},
            checkpoint_path="/app/checkpoints/user1/final_model.pt",
        )

        # Verify the update was called on training_jobs table
        mock_client.table.assert_called_with("training_jobs")
        update_call = mock_client.table.return_value.update
        update_call.assert_called_once()

        # Check the update data
        update_data = update_call.call_args[0][0]
        assert update_data["status"] == "completed"
        assert update_data["metrics"] == {"accuracy": 0.95}
        assert update_data["checkpoint_path"] == "/app/checkpoints/user1/final_model.pt"

    @patch("apps.api.core.auth.get_service_client")
    def test_update_job_status_failed(self, mock_get_client):
        """_update_job_status should write 'failed' and error message."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        from apps.api.tasks.training_tasks import _update_job_status

        _update_job_status(
            job_id="test-job-456",
            status="failed",
            error="Out of memory",
        )

        update_call = mock_client.table.return_value.update
        update_data = update_call.call_args[0][0]
        assert update_data["status"] == "failed"
        assert update_data["logs"] == "Out of memory"

    @patch("apps.api.core.auth.get_service_client")
    def test_update_job_status_handles_client_failure(self, mock_get_client):
        """If service client fails, should not raise (just log)."""
        mock_get_client.side_effect = RuntimeError("No service key")

        from apps.api.tasks.training_tasks import _update_job_status

        # Should not raise
        _update_job_status(job_id="test-job-789", status="completed")
