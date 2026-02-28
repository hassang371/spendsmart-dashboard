"""Anomaly router — anomaly detection alerts (stub)."""

from fastapi import APIRouter

router = APIRouter(prefix="/anomaly", tags=["anomaly"])


@router.get("/alerts/{user_id}")
async def get_alerts(user_id: str):
    """Get anomaly alerts for a user (stub — returns empty list)."""
    return {"alerts": [], "user_id": user_id}
