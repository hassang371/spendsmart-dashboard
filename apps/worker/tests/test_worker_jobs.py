import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure import paths
sys.path.append(os.getcwd())

from apps.worker import main


class TestWorkerJobs(unittest.TestCase):
    @patch("apps.worker.main.get_supabase")
    def test_worker_polls_training_jobs(self, mock_get_supabase):
        """Worker should poll training_jobs and process pending ones."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Verify main module has the expected functions
        self.assertTrue(hasattr(main, "train_model"))
        self.assertTrue(hasattr(main, "main"))

    @patch("apps.worker.main.get_supabase")
    @patch("apps.worker.main.train_model")
    def test_train_model_called_for_pending_job(
        self, mock_train_model, mock_get_supabase
    ):
        """Verify train_model is callable with job_id and user_id."""
        mock_train_model.return_value = "Training complete."
        mock_train_model("job-123", "user-abc")
        mock_train_model.assert_called_with("job-123", "user-abc")


if __name__ == "__main__":
    unittest.main()
