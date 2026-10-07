import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.config import settings

@pytest.mark.asyncio
async def test_complete_incident_lifecycle_workflow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        settings.DEMO_MODE = True

        # 1. Login as Analyst
        login_res = await client.post("/api/auth/demo-login", json={"role": "analyst"})
        assert login_res.status_code == 200
        csrf = login_res.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf}

        # 2. Ingest batch of cascading logs
        ingest_payload = {
            "trigger_correlation": True,
            "logs": [
                {
                    "timestamp": "2026-10-07T15:00:00",
                    "service": "db-proxy",
                    "level": "CRITICAL",
                    "message": "Connection pool exhausted: 50/50 active connections held, 120 queued queries"
                },
                {
                    "timestamp": "2026-10-07T15:00:04",
                    "service": "auth-service",
                    "level": "ERROR",
                    "message": "Database query timeout after 30000ms while authenticating token sess_881"
                },
                {
                    "timestamp": "2026-10-07T15:00:10",
                    "service": "api-gateway",
                    "level": "CRITICAL",
                    "message": "Circuit breaker OPEN for auth-service after 5 consecutive 503 errors"
                }
            ]
        }
        ingest_res = await client.post("/api/logs/ingest", json=ingest_payload, headers=headers)
        assert ingest_res.status_code == 200
        data = ingest_res.json()
        assert data["total_ingested"] == 3
        assert data["anomalies_detected"] >= 2
        assert data["incidents_created"] >= 1

        # 3. List incidents
        inc_list_res = await client.get("/api/incidents")
        assert inc_list_res.status_code == 200
        incidents = inc_list_res.json()
        assert len(incidents) >= 1
        incident_id = incidents[0]["id"]

        # 4. Fetch incident detail and verify DAG graph
        detail_res = await client.get(f"/api/incidents/{incident_id}")
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["id"] == incident_id
        assert len(detail["correlated_logs"]) >= 2
        assert len(detail["graph"]["nodes"]) >= 2

        # 5. Patch incident status to 'investigating'
        patch_res = await client.patch(
            f"/api/incidents/{incident_id}",
            json={"status": "investigating", "postmortem_notes": "Identified connection pool leak."},
            headers=headers
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == "investigating"
        assert patch_res.json()["postmortem_notes"] == "Identified connection pool leak."

        # 6. Export postmortem as markdown
        export_md = await client.get(f"/api/incidents/{incident_id}/export?format=markdown")
        assert export_md.status_code == 200
        assert "# Postmortem Report" in export_md.text
        assert "Identified connection pool leak" in export_md.text

        # 7. Check health and metadata endpoints
        health_res = await client.get("/api/health")
        assert health_res.status_code == 200
        assert health_res.json()["status"] == "healthy"

        meta_res = await client.get("/api/meta")
        assert meta_res.status_code == 200
        assert meta_res.json()["name"] == "log-anomaly-detector-alan-vo"

@pytest.mark.asyncio
async def test_admin_audit_trail_access():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        settings.DEMO_MODE = True

        # Analyst cannot access admin audit trail
        await client.post("/api/auth/demo-login", json={"role": "analyst"})
        analyst_audit = await client.get("/api/audit")
        assert analyst_audit.status_code == 403

        # Admin CAN access audit trail
        await client.post("/api/auth/demo-login", json={"role": "admin"})
        admin_audit = await client.get("/api/audit")
        assert admin_audit.status_code == 200
        audit_records = admin_audit.json()
        assert isinstance(audit_records, list)
        assert len(audit_records) > 0
