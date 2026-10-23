import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.core.database import transaction
from app.core.security import get_current_user, require_role, verify_csrf
from app.models.schemas import ThresholdConfigResponse, ThresholdConfigUpdate
from app.services.audit import AuditService
from app.services.detector import AnomalyDetector

router = APIRouter(prefix="/api/thresholds", tags=["Threshold Configuration"])


def _row_to_response(row: dict) -> ThresholdConfigResponse:
    return ThresholdConfigResponse(
        id=row["id"],
        config_key=row["config_key"],
        config_value=row["config_value"],
        description=row["description"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("", response_model=List[ThresholdConfigResponse])
async def list_thresholds(
    user: dict = Depends(get_current_user),
):
    """List all threshold configuration values."""
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM threshold_config ORDER BY config_key")
        rows = cursor.fetchall()
    return [_row_to_response(dict(r)) for r in rows]


@router.put("/{config_key}", response_model=ThresholdConfigResponse)
async def update_threshold(
    config_key: str,
    payload: ThresholdConfigUpdate,
    user: dict = Depends(require_role("analyst", "admin")),
    request: Request = None,
    _csrf: None = Depends(verify_csrf),
):
    """Update a threshold configuration value."""
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM threshold_config WHERE config_key = ?", (config_key,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Threshold configuration not found")

        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "UPDATE threshold_config SET config_value = ?, updated_at = ? WHERE config_key = ?",
            (payload.config_value, now, config_key)
        )

        cursor.execute("SELECT * FROM threshold_config WHERE config_key = ?", (config_key,))
        updated = cursor.fetchone()

        # Invalidate detector cache
        AnomalyDetector.invalidate_threshold_cache()

        # Audit trail
        ip = request.client.host if request and request.client else "unknown"
        AuditService.log(
            conn,
            user_id=user["id"],
            username=user["username"],
            action="update_threshold",
            entity_type="threshold_config",
            entity_id=config_key,
            details=f"Updated {config_key} from {row['config_value']} to {payload.config_value}",
            ip_address=ip,
        )

    return _row_to_response(dict(updated))