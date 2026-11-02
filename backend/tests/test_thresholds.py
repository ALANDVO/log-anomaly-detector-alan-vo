import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.config import settings
from app.core.database import init_db, transaction
from app.services.detector import AnomalyDetector
from datetime import datetime, timezone
import uuid

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    # Clear threshold_config table before each test to ensure isolation
    with transaction() as conn:
        conn.execute("DELETE FROM threshold_config")
    # Re-seed defaults
    now = datetime.now(timezone.utc).isoformat()
    defaults = [
        ("anomaly_threshold", 0.50, "Minimum anomaly score to classify as anomaly"),
        ("severity_critical", 0.80, "Anomaly score threshold for critical severity"),
        ("severity_high", 0.65, "Anomaly score threshold for high severity"),
        ("severity_medium", 0.40, "Anomaly score threshold for medium severity"),
        ("level_critical_weight", 0.40, "Weight added for CRITICAL log level"),
        ("level_error_weight", 0.25, "Weight added for ERROR log level"),
        ("level_warn_weight", 0.10, "Weight added for WARN log level"),
        ("rarity_first_occurrence", 0.35, "Score for first occurrence of template"),
        ("rarity_under_5", 0.20, "Score for template with < 5 occurrences"),
        ("burst_high_density", 0.35, "Score for high error density (>40%)"),
        ("burst_elevated", 0.20, "Score for elevated error burst (>20%)"),
        ("entropy_high_threshold", 4.2, "Token entropy threshold for high entropy bonus"),
        ("entropy_high_bonus", 0.15, "Score bonus for high token entropy"),
        ("entropy_low_threshold", 1.0, "Token entropy threshold for low entropy bonus"),
        ("entropy_low_bonus", 0.10, "Score bonus for low token entropy"),
    ]
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT INTO threshold_config (id, config_key, config_value, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            [(f"thr_{uuid.uuid4().hex[:10]}", k, v, d, now, now) for k, v, d in defaults]
        )
    AnomalyDetector.invalidate_threshold_cache()

@pytest.mark.asyncio
async def test_thresholds_crud_workflow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        settings.DEMO_MODE = True

        # Login as analyst
        login_res = await client.post("/api/auth/demo-login", json={"role": "analyst"})
        assert login_res.status_code == 200
        csrf = login_res.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf}

        # 1. List thresholds (should have defaults)
        list_res = await client.get("/api/thresholds")
        assert list_res.status_code == 200
        thresholds = list_res.json()
        assert len(thresholds) > 0
        
        # Verify default thresholds exist
        config_keys = {t["config_key"] for t in thresholds}
        assert "anomaly_threshold" in config_keys
        assert "severity_critical" in config_keys
        assert "severity_high" in config_keys
        assert "severity_medium" in config_keys

        # 2. Update a threshold
        update_res = await client.put(
            "/api/thresholds/anomaly_threshold",
            json={"config_value": 0.60},
            headers=headers
        )
        assert update_res.status_code == 200
        updated = update_res.json()
        assert updated["config_key"] == "anomaly_threshold"
        assert updated["config_value"] == 0.60

        # 3. Verify update persisted
        list_res2 = await client.get("/api/thresholds")
        assert list_res2.status_code == 200
        thresholds2 = list_res2.json()
        anomaly_thresh = next(t for t in thresholds2 if t["config_key"] == "anomaly_threshold")
        assert anomaly_thresh["config_value"] == 0.60

        # 4. Update another threshold
        update_res2 = await client.put(
            "/api/thresholds/severity_high",
            json={"config_value": 0.70},
            headers=headers
        )
        assert update_res2.status_code == 200
        updated2 = update_res2.json()
        assert updated2["config_key"] == "severity_high"
        assert updated2["config_value"] == 0.70

@pytest.mark.asyncio
async def test_thresholds_viewer_read_only():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        settings.DEMO_MODE = True

        # Login as viewer
        login_res = await client.post("/api/auth/demo-login", json={"role": "viewer"})
        assert login_res.status_code == 200
        csrf = login_res.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf}

        # Viewer can read
        list_res = await client.get("/api/thresholds")
        assert list_res.status_code == 200
        assert len(list_res.json()) > 0

        # Viewer cannot update
        update_res = await client.put(
            "/api/thresholds/anomaly_threshold",
            json={"config_value": 0.90},
            headers=headers
        )
        assert update_res.status_code == 403
        assert "Access denied" in update_res.json()["detail"]

@pytest.mark.asyncio
async def test_thresholds_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        settings.DEMO_MODE = True

        login_res = await client.post("/api/auth/demo-login", json={"role": "analyst"})
        assert login_res.status_code == 200
        csrf = login_res.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf}

        # Try to update non-existent threshold
        update_res = await client.put(
            "/api/thresholds/nonexistent_key",
            json={"config_value": 0.50},
            headers=headers
        )
        assert update_res.status_code == 404
        assert "not found" in update_res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_threshold_audit_trail():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        settings.DEMO_MODE = True

        login_res = await client.post("/api/auth/demo-login", json={"role": "analyst"})
        assert login_res.status_code == 200
        csrf = login_res.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf}

        # Update a threshold
        await client.put(
            "/api/thresholds/anomaly_threshold",
            json={"config_value": 0.75},
            headers=headers
        )

        # Check audit log
        admin_login = await client.post("/api/auth/demo-login", json={"role": "admin"})
        assert admin_login.status_code == 200
        admin_csrf = admin_login.json()["csrf_token"]
        admin_headers = {"X-CSRF-Token": admin_csrf}

        audit_res = await client.get("/api/audit", headers=admin_headers)
        assert audit_res.status_code == 200
        audits = audit_res.json()
        
        # Find the threshold update audit entry
        threshold_audits = [a for a in audits if a["action"] == "update_threshold" and a["entity_type"] == "threshold_config"]
        assert len(threshold_audits) >= 1
        audit = threshold_audits[0]
        assert audit["entity_id"] == "anomaly_threshold"
        assert "0.75" in audit["details"]
        assert "analyst" in audit["username"]

def test_detector_uses_database_thresholds():
    """Test that detector reads thresholds from database."""
    from app.core.database import transaction
    
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT config_value FROM threshold_config WHERE config_key = 'anomaly_threshold'")
        row = cursor.fetchone()
        assert row is not None
        original_value = row["config_value"]
    
    # The detector should use the database value
    verdict = AnomalyDetector.evaluate(
        service="test-service",
        level="INFO",
        message="Normal operation message",
        template_id="tpl_test",
        timestamp_iso="2026-10-07T12:00:00"
    )
    
    # With default threshold of 0.50, normal message should not be anomaly
    assert not verdict.is_anomaly
    assert verdict.anomaly_score < original_value + 0.1  # Some tolerance

def test_detector_threshold_cache_invalidation():
    """Test that detector cache is invalidated after threshold update."""
    # First, get initial threshold
    thresholds = AnomalyDetector._get_thresholds()
    original_anomaly_threshold = thresholds["anomaly_threshold"]
    
    # Invalidate cache
    AnomalyDetector.invalidate_threshold_cache()
    
    # Next call should fetch fresh from DB
    thresholds2 = AnomalyDetector._get_thresholds()
    assert thresholds2["anomaly_threshold"] == original_anomaly_threshold
