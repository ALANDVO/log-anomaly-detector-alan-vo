import uuid, json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.core.database import transaction
from app.models.schemas import CorrelationGraph, CascadeNode, CascadeEdge

SERVICE_DEPENDENCIES = {
    "db-proxy": ["auth-service", "payment-service", "order-service"],
    "cache-layer": ["api-gateway", "auth-service"],
    "auth-service": ["api-gateway"],
    "payment-service": ["api-gateway", "order-service"]
}

class EventCorrelator:
    @staticmethod
    def _event_time(log: Dict[str, Any]) -> float:
        try:
            dt = datetime.fromisoformat(str(log.get("timestamp") or "").replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            return float("inf")

    @classmethod
    def _downstream(cls, service: str) -> set:
        seen, stack = set(), list(SERVICE_DEPENDENCIES.get(service, []))
        while stack:
            nxt = stack.pop()
            if nxt not in seen:
                seen.add(nxt)
                stack.extend(SERVICE_DEPENDENCIES.get(nxt, []))
        return seen

    @classmethod
    def select_root_event(cls, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        present = {l.get("service") for l in logs}
        return max(logs, key=lambda log: (
            len(cls._downstream(str(log.get("service") or "")) & present),
            -cls._event_time(log), float(log.get("anomaly_score") or 0.0),
        ))

    @classmethod
    def correlate_recent_anomalies(cls, window_minutes: int = 15) -> List[str]:
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT l.* FROM logs l LEFT JOIN incident_logs il ON l.id = il.log_id
                   WHERE l.is_anomaly = 1 AND il.incident_id IS NULL"""
            )
            rows = [dict(r) for r in cursor.fetchall()]
        if not rows: return []
        rows.sort(key=cls._event_time)
        floor = cls._event_time(rows[-1]) - max(1, int(window_minutes)) * 60
        rows = [r for r in rows if floor <= cls._event_time(r) < float("inf")]
        if not rows: return []
        clusters: List[List[Dict[str, Any]]] = []
        curr_cluster: List[Dict[str, Any]] = [rows[0]]
        for i in range(1, len(rows)):
            if cls._event_time(rows[i]) - cls._event_time(rows[i - 1]) <= 300:
                curr_cluster.append(rows[i])
            else:
                clusters.append(curr_cluster)
                curr_cluster = [rows[i]]
        clusters.append(curr_cluster)

        incident_ids: List[str] = []
        for cluster in clusters:
            inc_id = cls._create_incident_from_cluster(cluster)
            if inc_id: incident_ids.append(inc_id)
        return incident_ids

    @classmethod
    def _create_incident_from_cluster(cls, cluster: List[Dict[str, Any]]) -> Optional[str]:
        if not cluster: return None
        cluster.sort(key=cls._event_time)
        root = cls.select_root_event(cluster)
        primary_svc = root["service"]
        services = list(dict.fromkeys([primary_svc] + [l["service"] for l in cluster]))
        max_score = max(l["anomaly_score"] for l in cluster)
        start_ts, end_ts = cluster[0]["timestamp"], cluster[-1]["timestamp"]

        if len(services) > 2 and max_score >= 0.8: severity = "P1"
        elif len(services) > 1 or max_score >= 0.75: severity = "P2"
        elif max_score >= 0.6: severity = "P3"
        else: severity = "P4"

        incident_id = f"inc_{uuid.uuid4().hex[:10]}"
        title = f"Correlated {severity} Alert: {primary_svc} Cascade ({len(cluster)} events across {len(services)} services)"
        summary = f"Cascade from {start_ts} to {end_ts} across {', '.join(services)} (peak {max_score:.2f}). Root-cause candidate: {primary_svc}."
        hyp = f"Root cause candidate is {primary_svc}: '{root['message'][:100]}'."
        now_iso = datetime.now(timezone.utc).isoformat()

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO incidents (id, title, status, severity, service, start_time, end_time,
                   log_count, summary, root_cause_hypothesis, postmortem_notes, blast_radius, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (incident_id, title, "open", severity, primary_svc, start_ts, end_ts,
                 len(cluster), summary, hyp, "", json.dumps(services), now_iso, now_iso)
            )
            cursor.executemany("INSERT OR IGNORE INTO incident_logs (incident_id, log_id) VALUES (?, ?)", [(incident_id, l["id"]) for l in cluster])
        return incident_id

    @classmethod
    def build_correlation_graph(cls, logs: List[Dict[str, Any]]) -> CorrelationGraph:
        if not logs: return CorrelationGraph(nodes=[], edges=[], root_cause_candidate=None)
        sorted_logs = sorted(logs, key=cls._event_time)
        nodes = [
            CascadeNode(id=l["id"], service=l["service"], timestamp=l["timestamp"], level=l["level"], message=l["message"][:120], anomaly_score=float(l.get("anomaly_score", 0.0)))
            for l in sorted_logs
        ]
        edges = []
        for i in range(len(sorted_logs) - 1):
            src, tgt = sorted_logs[i], sorted_logs[i + 1]
            t0, t1 = cls._event_time(src), cls._event_time(tgt)
            delay = 0.0 if t0 == float("inf") or t1 == float("inf") else max(0.0, round(t1 - t0, 2))

            if tgt["service"] in SERVICE_DEPENDENCIES.get(src["service"], []): rel = "downstream_dependency_cascade"
            elif src["service"] == tgt["service"]: rel = "same_service_consecutive_error"
            else: rel = "correlated_temporal_cluster"

            edges.append(CascadeEdge(source=src["id"], target=tgt["id"], delay_seconds=delay, relationship=rel))

        return CorrelationGraph(nodes=nodes, edges=edges, root_cause_candidate=cls.select_root_event(sorted_logs)["id"])
