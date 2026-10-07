import uuid, json, random, secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status, Request

from app.core.database import transaction
from app.core.security import get_current_user, require_role, verify_csrf
from app.models.schemas import (
    LogIngestRequest, LogIngestResponse, LogEntryResponse, LogStatsResponse, LogTemplateResponse, LogEntryCreate
)
from app.services.parser import LogParser
from app.services.detector import AnomalyDetector
from app.services.correlator import EventCorrelator
from app.services.audit import AuditService

router = APIRouter(prefix="/api/logs", tags=["Logs"])

@router.post("/ingest", response_model=LogIngestResponse)
async def ingest_logs(
    payload: LogIngestRequest,
    request: Request,
    user: dict = Depends(require_role("analyst")),
    _csrf: None = Depends(verify_csrf)
):
    if not payload.logs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No log entries provided.")

    now_iso = datetime.now(timezone.utc).isoformat()
    processed: List[LogEntryResponse] = []
    anomalies_count = 0

    with transaction() as conn:
        cursor = conn.cursor()
        for entry in payload.logs:
            log_id = f"log_{uuid.uuid4().hex[:12]}"
            lvl, clean_msg, ext_ts = LogParser.extract_level_and_clean(entry.message, entry.level)
            final_ts = ext_ts or entry.timestamp or now_iso
            tpl_id, pattern, params = LogParser.extract_template(clean_msg)

            LogParser.record_template(tpl_id, pattern, clean_msg)
            verdict = AnomalyDetector.evaluate(entry.service, lvl, clean_msg, tpl_id, final_ts)
            if verdict.is_anomaly: anomalies_count += 1

            cursor.execute(
                """INSERT INTO logs (id, timestamp, service, level, message, template_id, parameters,
                   anomaly_score, is_anomaly, severity, anomaly_reasons, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (log_id, final_ts, entry.service, lvl, clean_msg, tpl_id, json.dumps(params),
                 verdict.anomaly_score, 1 if verdict.is_anomaly else 0, verdict.severity,
                 json.dumps(verdict.reasons), json.dumps(entry.metadata or {}), now_iso)
            )
            processed.append(LogEntryResponse(
                id=log_id, timestamp=final_ts, service=entry.service, level=lvl, message=clean_msg,
                template_id=tpl_id, parameters=params, anomaly_score=verdict.anomaly_score,
                is_anomaly=verdict.is_anomaly, severity=verdict.severity, anomaly_reasons=verdict.reasons,
                metadata=entry.metadata, created_at=now_iso
            ))

    incidents_created = 0
    if payload.trigger_correlation and anomalies_count > 0:
        incidents_created = len(EventCorrelator.correlate_recent_anomalies(window_minutes=20))

    AuditService.record(
        user["id"], user["username"], "ingest_logs", "logs_batch", f"batch_{len(payload.logs)}",
        request.client.host if request.client else "127.0.0.1",
        f"Ingested {len(payload.logs)} logs ({anomalies_count} anomalies)"
    )

    return LogIngestResponse(
        total_ingested=len(processed), anomalies_detected=anomalies_count,
        incidents_created=incidents_created, items=processed
    )

@router.get("", response_model=Dict[str, Any])
async def list_logs(
    user: dict = Depends(get_current_user),
    service: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    is_anomaly: Optional[bool] = Query(None),
    severity: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    q, p = "SELECT * FROM logs WHERE 1=1", []
    qc, pc = "SELECT COUNT(*) as cnt FROM logs WHERE 1=1", []

    if service:
        q += " AND service = ?"; qc += " AND service = ?"; p.append(service); pc.append(service)
    if level:
        q += " AND level = ?"; qc += " AND level = ?"; p.append(level.upper()); pc.append(level.upper())
    if is_anomaly is not None:
        val = 1 if is_anomaly else 0
        q += " AND is_anomaly = ?"; qc += " AND is_anomaly = ?"; p.append(val); pc.append(val)
    if severity:
        q += " AND severity = ?"; qc += " AND severity = ?"; p.append(severity); pc.append(severity)
    if search:
        q += " AND message LIKE ?"; qc += " AND message LIKE ?"; p.append(f"%{search}%"); pc.append(f"%{search}%")

    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(qc, pc)
        total = cursor.fetchone()["cnt"]
        cursor.execute(q + " ORDER BY timestamp DESC LIMIT ? OFFSET ?", p + [limit, offset])
        rows = cursor.fetchall()

    return {
        "total": total, "limit": limit, "offset": offset,
        "items": [
            LogEntryResponse(
                id=r["id"], timestamp=r["timestamp"], service=r["service"], level=r["level"], message=r["message"],
                template_id=r["template_id"], parameters=json.loads(r["parameters"]) if r["parameters"] else None,
                anomaly_score=r["anomaly_score"], is_anomaly=bool(r["is_anomaly"]), severity=r["severity"],
                anomaly_reasons=json.loads(r["anomaly_reasons"]) if r["anomaly_reasons"] else None,
                metadata=json.loads(r["metadata"]) if r["metadata"] else None, created_at=r["created_at"]
            ) for r in rows
        ]
    }

@router.get("/templates", response_model=List[LogTemplateResponse])
async def list_templates(user: dict = Depends(get_current_user)):
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM templates ORDER BY occurrence_count DESC LIMIT 100")
        rows = cursor.fetchall()
    return [
        LogTemplateResponse(
            id=r["id"], pattern=r["pattern"], sample_message=r["sample_message"],
            occurrence_count=r["occurrence_count"], first_seen=r["first_seen"], last_seen=r["last_seen"]
        ) for r in rows
    ]

@router.get("/stats", response_model=LogStatsResponse)
async def get_log_stats(user: dict = Depends(get_current_user)):
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total, SUM(is_anomaly) as anomalies FROM logs")
        row = cursor.fetchone()
        total, anomalies = row["total"] or 0, row["anomalies"] or 0

        cursor.execute("SELECT service, COUNT(*) as cnt FROM logs GROUP BY service")
        svcs = {r["service"]: r["cnt"] for r in cursor.fetchall()}

        cursor.execute("SELECT severity, COUNT(*) as cnt FROM logs WHERE is_anomaly = 1 GROUP BY severity")
        sevs = {r["severity"]: r["cnt"] for r in cursor.fetchall()}

        cursor.execute("SELECT COUNT(*) as cnt FROM incidents WHERE status != 'resolved'")
        active = cursor.fetchone()["cnt"] or 0

        cursor.execute("SELECT strftime('%Y-%m-%dT%H:00:00', timestamp) as b, COUNT(*) as t, SUM(is_anomaly) as a FROM logs GROUP BY b ORDER BY b DESC LIMIT 7")
        trend = [{"bucket": r["b"] or "recent", "total": r["t"], "anomalies": r["a"] or 0} for r in cursor.fetchall()]

    rate = round(anomalies / total, 4) if total > 0 else 0.0
    return LogStatsResponse(
        total_logs=total, total_anomalies=anomalies, anomaly_rate=rate,
        service_breakdown=svcs, severity_breakdown=sevs, active_incidents=active, recent_trend=trend
    )

@router.post("/seed-sample-data")
async def seed_sample_data(
    request: Request,
    user: dict = Depends(require_role("analyst")),
    _csrf: None = Depends(verify_csrf)
):
    services = ["api-gateway", "auth-service", "payment-service", "db-proxy", "cache-layer"]
    base_time = datetime.now(timezone.utc) - timedelta(minutes=25)
    samples = []
    for i in range(20):
        samples.append(LogEntryCreate(
            timestamp=(base_time + timedelta(seconds=i * 20)).isoformat(),
            service=random.choice(services), level="INFO",
            message=f"Request req_{secrets.token_hex(4)} completed status 200 in {random.randint(10, 50)}ms"
        ))
    t_inc = base_time + timedelta(minutes=15)
    samples.extend([
        LogEntryCreate(timestamp=(t_inc + timedelta(seconds=1)).isoformat(), service="db-proxy", level="CRITICAL", message="Connection pool exhausted: 50/50 active connections held, 120 queued queries"),
        LogEntryCreate(timestamp=(t_inc + timedelta(seconds=3)).isoformat(), service="db-proxy", level="CRITICAL", message="Transaction deadlock detected on table 'accounts', killing victim thread 401"),
        LogEntryCreate(timestamp=(t_inc + timedelta(seconds=8)).isoformat(), service="auth-service", level="ERROR", message="Database query timeout after 30000ms while authenticating token sess_881"),
        LogEntryCreate(timestamp=(t_inc + timedelta(seconds=15)).isoformat(), service="api-gateway", level="CRITICAL", message="Circuit breaker OPEN for auth-service after 5 consecutive 503 errors")
    ])
    return await ingest_logs(LogIngestRequest(logs=samples, trigger_correlation=True), request, user, _csrf)
