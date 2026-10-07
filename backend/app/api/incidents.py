import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Literal
from fastapi import APIRouter, Depends, Query, HTTPException, status, Request
from fastapi.responses import PlainTextResponse

from app.core.database import transaction
from app.core.security import get_current_user, require_role, verify_csrf
from app.models.schemas import (
    IncidentResponse, IncidentDetailResponse, IncidentUpdateRequest,
    LLMAdvisoryRequest, LLMAdvisoryResponse, LogEntryResponse
)
from app.services.correlator import EventCorrelator
from app.services.llm_advisor import LLMAdvisor
from app.services.audit import AuditService

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])

@router.get("", response_model=List[IncidentResponse])
async def list_incidents(
    user: dict = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    q, p = "SELECT * FROM incidents WHERE 1=1", []
    if status_filter: q += " AND status = ?"; p.append(status_filter)
    if severity: q += " AND severity = ?"; p.append(severity)
    q += " ORDER BY created_at DESC LIMIT ? OFFSET ?"; p.extend([limit, offset])

    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(q, p)
        rows = cursor.fetchall()

    return [
        IncidentResponse(
            id=r["id"], title=r["title"], status=r["status"], severity=r["severity"], service=r["service"],
            start_time=r["start_time"], end_time=r["end_time"], log_count=r["log_count"], summary=r["summary"],
            root_cause_hypothesis=r["root_cause_hypothesis"], postmortem_notes=r["postmortem_notes"],
            blast_radius=json.loads(r["blast_radius"]) if r["blast_radius"] else None,
            advisory_provider=r["advisory_provider"], advisory_model=r["advisory_model"],
            created_at=r["created_at"], updated_at=r["updated_at"]
        ) for r in rows
    ]

@router.get("/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident_detail(incident_id: str, user: dict = Depends(get_current_user)):
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

        cursor.execute(
            """SELECT l.* FROM logs l JOIN incident_logs il ON l.id = il.log_id
               WHERE il.incident_id = ? ORDER BY l.timestamp ASC""",
            (incident_id,)
        )
        log_rows = [dict(r) for r in cursor.fetchall()]

    logs = [
        LogEntryResponse(
            id=r["id"], timestamp=r["timestamp"], service=r["service"], level=r["level"], message=r["message"],
            template_id=r["template_id"], parameters=json.loads(r["parameters"]) if r["parameters"] else None,
            anomaly_score=r["anomaly_score"], is_anomaly=bool(r["is_anomaly"]), severity=r["severity"],
            anomaly_reasons=json.loads(r["anomaly_reasons"]) if r["anomaly_reasons"] else None,
            metadata=json.loads(r["metadata"]) if r["metadata"] else None, created_at=r["created_at"]
        ) for r in log_rows
    ]

    return IncidentDetailResponse(
        id=inc["id"], title=inc["title"], status=inc["status"], severity=inc["severity"], service=inc["service"],
        start_time=inc["start_time"], end_time=inc["end_time"], log_count=inc["log_count"], summary=inc["summary"],
        root_cause_hypothesis=inc["root_cause_hypothesis"], postmortem_notes=inc["postmortem_notes"],
        blast_radius=json.loads(inc["blast_radius"]) if inc["blast_radius"] else None,
        advisory_provider=inc["advisory_provider"], advisory_model=inc["advisory_model"],
        created_at=inc["created_at"], updated_at=inc["updated_at"],
        correlated_logs=logs, graph=EventCorrelator.build_correlation_graph(log_rows)
    )

@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: str,
    payload: IncidentUpdateRequest,
    request: Request,
    user: dict = Depends(require_role("analyst")),
    _csrf: None = Depends(verify_csrf)
):
    now_iso = datetime.now(timezone.utc).isoformat()
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

        new_status = payload.status or inc["status"]
        new_notes = payload.postmortem_notes if payload.postmortem_notes is not None else inc["postmortem_notes"]

        cursor.execute(
            "UPDATE incidents SET status = ?, postmortem_notes = ?, updated_at = ? WHERE id = ?",
            (new_status, new_notes, now_iso, incident_id)
        )
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        updated = cursor.fetchone()

    AuditService.record(
        user["id"], user["username"], "update_incident", "incident", incident_id,
        request.client.host if request.client else "127.0.0.1", f"Status set to {new_status}"
    )

    return IncidentResponse(
        id=updated["id"], title=updated["title"], status=updated["status"], severity=updated["severity"],
        service=updated["service"], start_time=updated["start_time"], end_time=updated["end_time"],
        log_count=updated["log_count"], summary=updated["summary"], root_cause_hypothesis=updated["root_cause_hypothesis"],
        postmortem_notes=updated["postmortem_notes"], blast_radius=json.loads(updated["blast_radius"]) if updated["blast_radius"] else None,
        advisory_provider=updated["advisory_provider"], advisory_model=updated["advisory_model"],
        created_at=updated["created_at"], updated_at=updated["updated_at"]
    )

@router.post("/{incident_id}/advisory", response_model=LLMAdvisoryResponse)
async def generate_advisory(
    incident_id: str,
    payload: LLMAdvisoryRequest,
    request: Request,
    user: dict = Depends(require_role("analyst")),
    _csrf: None = Depends(verify_csrf)
):
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        inc = cursor.fetchone()
        if not inc: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")
        cursor.execute(
            """SELECT l.* FROM logs l JOIN incident_logs il ON l.id = il.log_id
               WHERE il.incident_id = ? ORDER BY l.timestamp ASC""",
            (incident_id,)
        )
        logs = [dict(r) for r in cursor.fetchall()]

    res = await LLMAdvisor.generate_incident_advisory(dict(inc), logs, payload.operator_guidance)
    if res.advisory_status == "success":
        now_iso = datetime.now(timezone.utc).isoformat()
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE incidents SET root_cause_hypothesis = ?, advisory_provider = ?, advisory_model = ?, updated_at = ? WHERE id = ?",
                (res.root_cause_hypothesis, res.provider, res.model, now_iso, incident_id)
            )

    AuditService.record(
        user["id"], user["username"], "generate_llm_advisory", "incident", incident_id,
        request.client.host if request.client else "127.0.0.1", f"Provider {res.provider} status {res.advisory_status}"
    )
    return res

@router.get("/{incident_id}/export")
async def export_postmortem(
    incident_id: str,
    export_format: Literal["json", "markdown"] = Query("markdown", alias="format"),
    user: dict = Depends(get_current_user)
):
    detail = await get_incident_detail(incident_id=incident_id, user=user)
    if export_format == "json": return detail.model_dump()

    md = f"""# Postmortem Report: {detail.title}
- **Incident ID:** `{detail.id}` | **Severity:** `{detail.severity}` | **Status:** `{detail.status.upper()}`
- **Primary Service:** `{detail.service}` | **Events:** {detail.log_count}

## 1. Executive Summary
{detail.summary}

## 2. Root Cause Hypothesis
{detail.root_cause_hypothesis or "Under deterministic baseline investigation."}

## 3. Postmortem Notes & Operator Remediation
{detail.postmortem_notes or "No notes recorded."}

## 4. Correlated Event Cascade Timeline
| Timestamp | Service | Level | Score | Log Message |
|---|---|---|---|---|
"""
    for l in detail.correlated_logs:
        md += f"| {l.timestamp} | {l.service} | {l.level} | {l.anomaly_score:.2f} | {l.message[:80]} |\n"
    return PlainTextResponse(content=md, media_type="text/markdown")
