from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from app.core.security import require_role
from app.models.schemas import AuditLogResponse
from app.services.audit import AuditService

router = APIRouter(prefix="/api/audit", tags=["Audit Trails"])

@router.get("", response_model=List[AuditLogResponse])
async def list_audit_trail(
    user: dict = Depends(require_role("admin")),
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Retrieves paginated audit log trails. Restricted to administrators."""
    return AuditService.list_logs(limit=limit, offset=offset, entity_type=entity_type, action=action)
