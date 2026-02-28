from datetime import datetime, timedelta
import structlog
from celery import shared_task
from apps.api.core.config import settings
from supabase import create_client, Client

logger = structlog.get_logger(__name__)

def get_service_client() -> Client:
    """Provides a Supabase client using the service role key to bypass RLS."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

@shared_task(name="cleanup_stale_jobs")
def cleanup_stale_jobs() -> str:
    """
    Toil Reduction Task:
    Garbage collects ML training jobs that are stuck in 'processing' status
    for more than 2 hours. This prevents the queue from being permanently
    blocked by zombie workers.
    """
    logger.info("Starting stale training jobs cleanup")
    
    try:
        supabase = get_service_client()
        
        # Calculate exactly 2 hours ago
        threshold_time = datetime.utcnow() - timedelta(hours=2)
        threshold_iso = threshold_time.isoformat()
        
        # Find and update stuck jobs
        response = (
            supabase.table("classification_jobs")
            .update({
                "status": "failed",
                "error_message": "Job timed out (cleaned up by maintenance task)"
            })
            .eq("status", "processing")
            .lt("updated_at", threshold_iso)
            .execute()
        )
        
        affected_count = len(response.data) if response.data else 0
        logger.info(f"Cleanup complete. Found {affected_count} stuck jobs.")
        
        return f"Cleaned up {affected_count} stale training jobs"
        
    except Exception as e:
        logger.error(f"Failed to cleanup stale jobs: {e}")
        return f"Error cleaning up stale jobs: {e}"
