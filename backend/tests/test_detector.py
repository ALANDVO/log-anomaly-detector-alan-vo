import pytest
from app.services.detector import AnomalyDetector
from app.core.database import init_db

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_detector_normal_log_nominal_score():
    verdict = AnomalyDetector.evaluate(
        service="api-gateway",
        level="INFO",
        message="GET /api/v1/products 200 OK - duration 20ms",
        template_id="tpl_common_http",
        timestamp_iso="2026-10-07T12:00:00"
    )
    assert not verdict.is_anomaly
    assert verdict.anomaly_score < 0.50
    assert verdict.severity == "low"

def test_detector_critical_deadlock_high_score():
    verdict = AnomalyDetector.evaluate(
        service="db-proxy",
        level="CRITICAL",
        message="Transaction deadlock detected on table 'orders', killing victim thread 401",
        template_id="tpl_deadlock_rare",
        timestamp_iso="2026-10-07T12:00:00"
    )
    assert verdict.is_anomaly
    assert verdict.anomaly_score >= 0.70
    assert verdict.severity in ("high", "critical")
    assert any("deadlock" in r.lower() or "critical" in r.lower() for r in verdict.reasons)

def test_token_entropy_calculation():
    # Repetitive tokens -> low entropy
    low_tokens = ["error", "error", "error", "error"]
    low_ent = AnomalyDetector.calculate_token_entropy(low_tokens)
    assert low_ent == 0.0

    # Diverse tokens -> high entropy
    high_tokens = [f"tok_{i}" for i in range(16)]
    high_ent = AnomalyDetector.calculate_token_entropy(high_tokens)
    assert high_ent == 4.0

def test_detector_threshold_fallback_to_defaults():
    """Test that detector uses default thresholds when DB is empty."""
    from app.core.database import transaction
    
    # Clear threshold_config table
    with transaction() as conn:
        conn.execute("DELETE FROM threshold_config")
    
    # Invalidate cache so it fetches fresh from (empty) DB
    AnomalyDetector.invalidate_threshold_cache()
    
    # Fetch thresholds - should get defaults
    thresholds = AnomalyDetector._get_thresholds()
    
    # Verify defaults are present
    assert thresholds["anomaly_threshold"] == 0.50
    assert thresholds["severity_critical"] == 0.80
    assert thresholds["severity_high"] == 0.65
    assert thresholds["severity_medium"] == 0.40
    assert "anomaly_threshold" in thresholds
    assert "severity_critical" in thresholds

