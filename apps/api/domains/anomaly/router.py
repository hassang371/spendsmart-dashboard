"""Anomaly router — anomaly detection alerts (stub)."""

from fastapi import APIRouter, Depends

from apps.api.core.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/anomaly", tags=["anomaly"])


@router.get("/alerts")
async def get_alerts(current_user: CurrentUser = Depends(get_current_user)):
    """Get anomaly alerts for the authenticated user (stub — returns empty list).

    BUG-032 fix: Removed user_id path parameter to eliminate IDOR risk.
    User identity is now derived from the verified auth token only.
    """
    return {"alerts": [], "user_id": current_user.id}
