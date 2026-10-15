import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from app.core.database import transaction
from app.core.security import get_current_user, require_role, verify_csrf
from app.models.schemas import (
    ServiceDependencyResponse, ServiceDependencyCreate, ServiceDependencyUpdate
)
from app.services.audit import AuditService

router = APIRouter(prefix="/api/dependencies", tags=["Service Dependencies"])


def _row_to_response(row: dict) -> ServiceDependencyResponse:
    return ServiceDependencyResponse(
        id=row["id"],
        upstream=row["upstream"],
        downstream=row["downstream"],
        relationship=row["relationship"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("", response_model=List[ServiceDependencyResponse])
async def list_dependencies(
    user: dict = Depends(get_current_user),
    upstream: Optional[str] = Query(None),
    downstream: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List service dependencies with optional filtering."""
    query, params = "SELECT * FROM service_dependencies WHERE 1=1", []
    if upstream:
        query += " AND upstream = ?"
        params.append(upstream)
    if downstream:
        query += " AND downstream = ?"
        params.append(downstream)
    query += " ORDER BY upstream, downstream LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    return [_row_to_response(dict(r)) for r in rows]


@router.post("", response_model=ServiceDependencyResponse, status_code=status.HTTP_201_CREATED)
async def create_dependency(
    payload: ServiceDependencyCreate,
    request: Request,
    user: dict = Depends(require_role("analyst")),
    _csrf: None = Depends(verify_csrf),
):
    """Create a new service dependency."""
    now_iso = datetime.now(timezone.utc).isoformat()
    dep_id = f"dep_{uuid.uuid4().hex[:10]}"

    with transaction() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO service_dependencies (id, upstream, downstream, relationship, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (dep_id, payload.upstream, payload.downstream, payload.relationship, now_iso, now_iso)
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Dependency from '{payload.upstream}' to '{payload.downstream}' already exists."
            )

    AuditService.record(
        user_id=user["id"],
        username=user["username"],
        action="create_dependency",
        entity_type="service_dependency",
        entity_id=dep_id,
        ip_address=request.client.host if request.client else "127.0.0.1",
        details=f"{payload.upstream} -> {payload.downstream} ({payload.relationship})"
    )

    return ServiceDependencyResponse(
        id=dep_id,
        upstream=payload.upstream,
        downstream=payload.downstream,
        relationship=payload.relationship,
        created_at=now_iso,
        updated_at=now_iso,
    )


@router.patch("/{dep_id}", response_model=ServiceDependencyResponse)
async def update_dependency(
    dep_id: str,
    payload: ServiceDependencyUpdate,
    request: Request,
    user: dict = Depends(require_role("analyst")),
    _csrf: None = Depends(verify_csrf),
):
    """Update an existing service dependency."""
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM service_dependencies WHERE id = ?", (dep_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")

        upstream = payload.upstream if payload.upstream is not None else row["upstream"]
        downstream = payload.downstream if payload.downstream is not None else row["downstream"]
        relationship = payload.relationship if payload.relationship is not None else row["relationship"]

        # Check for duplicate if upstream/downstream changed
        if upstream != row["upstream"] or downstream != row["downstream"]:
            cursor.execute(
                "SELECT id FROM service_dependencies WHERE upstream = ? AND downstream = ? AND id != ?",
                (upstream, downstream, dep_id)
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Dependency from '{upstream}' to '{downstream}' already exists."
                )

        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """UPDATE service_dependencies SET upstream = ?, downstream = ?, relationship = ?, updated_at = ?
               WHERE id = ?""",
            (upstream, downstream, relationship, now_iso, dep_id)
        )

    AuditService.record(
        user_id=user["id"],
        username=user["username"],
        action="update_dependency",
        entity_type="service_dependency",
        entity_id=dep_id,
        ip_address=request.client.host if request.client else "127.0.0.1",
        details=f"{upstream} -> {downstream} ({relationship})"
    )

    return ServiceDependencyResponse(
        id=dep_id,
        upstream=upstream,
        downstream=downstream,
        relationship=relationship,
        created_at=row["created_at"],
        updated_at=now_iso,
    )


@router.delete("/{dep_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dependency(
    dep_id: str,
    request: Request,
    user: dict = Depends(require_role("analyst")),
    _csrf: None = Depends(verify_csrf),
):
    """Delete a service dependency."""
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT upstream, downstream FROM service_dependencies WHERE id = ?", (dep_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")

        cursor.execute("DELETE FROM service_dependencies WHERE id = ?", (dep_id,))

    AuditService.record(
        user_id=user["id"],
        username=user["username"],
        action="delete_dependency",
        entity_type="service_dependency",
        entity_id=dep_id,
        ip_address=request.client.host if request.client else "127.0.0.1",
        details=f"{row['upstream']} -> {row['downstream']} removed"
    )

    return None