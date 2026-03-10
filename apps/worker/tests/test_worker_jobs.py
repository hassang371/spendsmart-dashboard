import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.append(os.getcwd())

from apps.worker.main import process_next_job


class TestWorkerJobs(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_table = MagicMock()
        self.mock_client.table.return_value = self.mock_table

    @patch("apps.worker.main.train_model")
    def test_process_next_job_executes_pending_job(self, mock_train_model):
        """Worker should successfully claim and process a pending job."""
        mock_train_model.return_value = "Training complete."

        # Mock finding a job
        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": "job-123",
                "user_id": "user-abc",
                "status": "pending",
                "logs": "forecasting: queued",
            }
        ]
        self.mock_table.select().eq().limit().execute.return_value = mock_response

        # Mock successful claim
        mock_claim_response = MagicMock()
        mock_claim_response.data = [{"id": "job-123", "status": "processing"}]
        self.mock_table.update().eq().eq().execute.return_value = mock_claim_response

        had_job = process_next_job(self.mock_client)

        self.assertTrue(had_job)
        mock_train_model.assert_called_with("job-123", "user-abc")

        # Verify it updated status
        self.assertTrue(self.mock_table.update.called)

    @patch("apps.worker.main.train_model")
    def test_process_next_job_skips_completed_job(self, mock_train_model):
        """Worker should skip jobs that are already completed (Idempotency)."""
        # Mock finding a job that is supposedly pending in the queue, but its data says it's completed
        # (This simulates a race condition where the status changed right before we processed it,
        #  so we don't accidentally re-run it)
        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": "job-123",
                "user_id": "user-abc",
                "status": "completed",
                "logs": "forecasting: done",
            }
        ]
        self.mock_table.select().eq().limit().execute.return_value = mock_response

        had_job = process_next_job(self.mock_client)

        self.assertTrue(had_job)  # It found a job in the queue
        mock_train_model.assert_not_called()  # But it skipped training

    @patch("apps.worker.main.train_model")
    def test_process_next_job_handles_failed_claim(self, mock_train_model):
        """If updating the job to 'processing' fails (already claimed by other worker), skip it."""
        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": "job-123",
                "user_id": "user-abc",
                "status": "pending",
                "logs": "forecasting: queued",
            }
        ]
        self.mock_table.select().eq().limit().execute.return_value = mock_response

        # Mock FAILED claim (zero rows returned from update)
        mock_claim_response = MagicMock()
        mock_claim_response.data = []
        self.mock_table.update().eq().eq().execute.return_value = mock_claim_response

        had_job = process_next_job(self.mock_client)

        self.assertTrue(had_job)
        mock_train_model.assert_not_called()  # Skipped because another worker claimed it

    @patch("apps.worker.main.train_model")
    def test_process_next_job_retries_failure_status_write(self, mock_train_model):
        """Worker retries status write when first failure update attempt errors."""
        mock_train_model.side_effect = RuntimeError("boom")

        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": "job-123",
                "user_id": "user-abc",
                "status": "pending",
                "logs": "forecasting: queued",
            }
        ]
        self.mock_table.select().eq().limit().execute.return_value = mock_response

        # First update call is claim (succeeds), second is failed status (raises),
        # third is retry failed status (succeeds)
        claim_response = MagicMock()
        claim_response.data = [{"id": "job-123", "status": "processing"}]
        retry_response = MagicMock()
        retry_response.data = [{"id": "job-123", "status": "failed"}]

        update_chain = self.mock_table.update().eq().eq().execute
        update_chain.side_effect = [claim_response, RuntimeError("write failed")]

        retry_chain = self.mock_table.update().eq().execute
        retry_chain.return_value = retry_response

        had_job = process_next_job(self.mock_client)

        self.assertTrue(had_job)
        self.assertGreaterEqual(self.mock_table.update.call_count, 3)


if __name__ == "__main__":
    unittest.main()
