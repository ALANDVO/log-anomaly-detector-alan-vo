import pytest
from app.services.correlator import EventCorrelator

def test_build_correlation_graph():
    logs = [
        {
            "id": "log-1",
            "service": "db-proxy",
            "timestamp": "2026-10-07T14:00:00",
            "level": "CRITICAL",
            "message": "Connection pool exhausted",
            "anomaly_score": 0.85
        },
        {
            "id": "log-2",
            "service": "auth-service",
            "timestamp": "2026-10-07T14:00:05",
            "level": "ERROR",
            "message": "Database query timeout after 30s",
            "anomaly_score": 0.75
        },
        {
            "id": "log-3",
            "service": "api-gateway",
            "timestamp": "2026-10-07T14:00:12",
            "level": "CRITICAL",
            "message": "Circuit breaker OPEN for auth-service",
            "anomaly_score": 0.90
        }
    ]

    graph = EventCorrelator.build_correlation_graph(logs)
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2
    assert graph.root_cause_candidate == "log-1"
    # Verify edge between db-proxy and downstream auth-service
    assert graph.edges[0].source == "log-1"
    assert graph.edges[0].target == "log-2"
    assert graph.edges[0].relationship == "downstream_dependency_cascade"
    assert graph.edges[0].delay_seconds == 5.0

def test_build_correlation_graph_empty():
    graph = EventCorrelator.build_correlation_graph([])
    assert graph.nodes == []
    assert graph.edges == []
    assert graph.root_cause_candidate is None

def test_root_cause_follows_dependency_when_symptom_arrives_first():
    logs = [
        {
            "id": "symptom",
            "service": "api-gateway",
            "timestamp": "2026-10-07T16:00:00+00:00",
            "level": "CRITICAL",
            "message": "Circuit breaker OPEN for auth-service",
            "anomaly_score": 0.95,
        },
        {
            "id": "hop",
            "service": "auth-service",
            "timestamp": "2026-10-07T16:00:04+00:00",
            "level": "ERROR",
            "message": "Database query timeout",
            "anomaly_score": 0.70,
        },
        {
            "id": "origin",
            "service": "db-proxy",
            "timestamp": "2026-10-07T11:01:04-05:00",
            "level": "CRITICAL",
            "message": "Connection pool exhausted",
            "anomaly_score": 0.88,
        },
    ]
    graph = EventCorrelator.build_correlation_graph(logs)
    assert [node.id for node in graph.nodes] == ["symptom", "hop", "origin"]
    assert graph.root_cause_candidate == "origin"
    assert graph.edges[0].source == "symptom"
    assert graph.edges[0].delay_seconds == 4.0
    assert graph.edges[1].delay_seconds == 60.0
    assert graph.edges[1].relationship == "correlated_temporal_cluster"

def test_root_cause_tie_breaks_to_earliest_when_topology_does_not_distinguish():
    logs = [
        {
            "id": "later",
            "service": "billing-service",
            "timestamp": "2026-10-07T14:00:05Z",
            "level": "ERROR",
            "message": "later unrelated failure",
            "anomaly_score": 0.99,
        },
        {
            "id": "earlier",
            "service": "search-service",
            "timestamp": "2026-10-07T14:00:01Z",
            "level": "ERROR",
            "message": "earlier unrelated failure",
            "anomaly_score": 0.40,
        },
    ]
    graph = EventCorrelator.build_correlation_graph(logs)
    assert graph.root_cause_candidate == "earlier"
    assert graph.edges[0].delay_seconds == 4.0

def test_incident_records_upstream_root_and_chronological_window():
    from app.core.database import init_db, transaction

    init_db()
    now = "2026-10-07T18:10:00"
    rows = [
        ("log_rc_symptom", "2026-10-07T18:00:00", "api-gateway", "CRITICAL", "Circuit breaker OPEN", 0.95),
        ("log_rc_origin", "2026-10-07T18:00:08", "db-proxy", "CRITICAL", "Connection pool exhausted", 0.90),
    ]
    with transaction() as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO logs (id, timestamp, service, level, message, template_id, parameters,
               anomaly_score, is_anomaly, severity, anomaly_reasons, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, NULL, '[]', ?, 1, 'critical', '[]', '{}', ?)""",
            [(rid, ts, svc, lvl, msg, score, now) for rid, ts, svc, lvl, msg, score in rows],
        )
    incident_id = EventCorrelator._create_incident_from_cluster([
        {"id": "log_rc_symptom", "timestamp": "2026-10-07T18:00:00", "service": "api-gateway", "message": "Circuit breaker OPEN", "anomaly_score": 0.95},
        {"id": "log_rc_origin", "timestamp": "2026-10-07T18:00:08", "service": "db-proxy", "message": "Connection pool exhausted", "anomaly_score": 0.90},
    ])
    assert incident_id
    with transaction() as conn:
        stored = conn.execute(
            "SELECT service, start_time, end_time, root_cause_hypothesis, blast_radius FROM incidents WHERE id = ?",
            (incident_id,),
        ).fetchone()
    assert stored["service"] == "db-proxy"
    assert stored["start_time"] == "2026-10-07T18:00:00"
    assert stored["end_time"] == "2026-10-07T18:00:08"
    assert stored["root_cause_hypothesis"].startswith("Root cause candidate is db-proxy")
    assert stored["blast_radius"].startswith('["db-proxy"')
