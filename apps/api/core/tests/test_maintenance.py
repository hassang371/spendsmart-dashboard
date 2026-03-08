import pytest
from unittest.mock import patch, MagicMock
from apps.api.core.tasks.maintenance_tasks import cleanup_stale_jobs

@pytest.fixture
def mock_supabase():
    with patch("apps.api.core.tasks.maintenance_tasks.get_service_client") as mock:
        yield mock

class TestCleanupStaleJobs:
    """Test the maintenance task for cleaning up stale training jobs."""
    
    def test_cleanup_stale_jobs_success(self, mock_supabase):
        """Test it updates jobs older than 2 hours correctly."""
        # Setup mock client
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        
        # Mock the chained select/update/execute calls
        mock_query = MagicMock()
        mock_client.table.return_value = mock_query
        mock_query.update.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.lt.return_value = mock_query
        
        # Simulate returning 2 rows affected
        mock_response = MagicMock()
        mock_response.data = [{"id": "1"}, {"id": "2"}]
        mock_query.execute.return_value = mock_response

        # Call the task function
        result = cleanup_stale_jobs()

        # Assert correct result string returned
        assert "Cleaned up 2 stale training jobs" in result

        # BUG-017 fix: Verify now correctly targets training_jobs, not dropped classification_jobs
        mock_client.table.assert_called_with("training_jobs")
        # BUG-017 fix: Verify correct field name ('logs') and added updated_at timestamp
        update_call = mock_query.update.call_args[0][0]
        assert update_call["status"] == "failed"
        assert "logs" in update_call
        assert "updated_at" in update_call
        assert "Job timed out" in update_call["logs"]

    def test_cleanup_stale_jobs_no_rows(self, mock_supabase):
        """Test behavior when no stale jobs exist."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        
        mock_query = MagicMock()
        mock_client.table.return_value = mock_query
        mock_query.update.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.lt.return_value = mock_query
        
        mock_response = MagicMock()
        mock_response.data = []
        mock_query.execute.return_value = mock_response

        result = cleanup_stale_jobs()
        assert "Cleaned up 0 stale training jobs" in result

    def test_cleanup_stale_jobs_exception(self, mock_supabase):
        """Test behavior when Supabase throws an exception."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        
        mock_query = MagicMock()
        mock_client.table.return_value = mock_query
        mock_query.update.return_value = mock_query
        
        # Raise generic exception when eq is called
        mock_query.eq.side_effect = Exception("Database connection failed")

        result = cleanup_stale_jobs()
        assert "Error cleaning up stale jobs: Database connection failed" in result
