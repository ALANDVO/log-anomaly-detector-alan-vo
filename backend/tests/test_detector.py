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
