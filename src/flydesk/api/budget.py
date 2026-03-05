"""Budget status API endpoint."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Request

from flydesk.rbac.guards import AdminDashboard

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/budget",
    tags=["admin"],
    dependencies=[AdminDashboard],
)


@router.get("/status")
async def budget_status(request: Request) -> dict:
    config = getattr(request.app.state, "config", None)
    settings_repo = getattr(request.app.state, "settings_repo", None)
    if config is None or settings_repo is None:
        return {"daily_limit": 0.0, "spent_today": 0.0, "percentage": 0.0, "status": "unavailable"}

    today = date.today().isoformat()
    spent_today = float(await settings_repo.get_app_setting(f"daily_spend_{today}") or "0")
    daily_limit = config.daily_budget_limit

    if daily_limit > 0:
        percentage = spent_today / daily_limit
        if percentage >= config.budget_alert_critical:
            status = "critical"
        elif percentage >= config.budget_alert_warning:
            status = "warning"
        else:
            status = "ok"
    else:
        percentage = 0.0
        status = "unlimited"

    return {
        "daily_limit": daily_limit,
        "spent_today": spent_today,
        "percentage": round(percentage, 4),
        "status": status,
    }
