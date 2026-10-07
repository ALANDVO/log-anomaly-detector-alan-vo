import time, uuid, json
from datetime import datetime, timezone
from typing import List, Dict, Any
from app.models.schemas import BenchmarkResultResponse
from app.services.parser import LogParser
from app.services.detector import AnomalyDetector
from app.core.database import transaction

BENCHMARK_DATASET: List[Dict[str, Any]] = [
    {"id": "ds-01", "service": "api-gateway", "level": "INFO", "message": "GET /api/v1/products 200 OK - duration 24ms", "is_ground_truth_anomaly": False, "category": "normal_http"},
    {"id": "ds-02", "service": "api-gateway", "level": "INFO", "message": "GET /health 200 OK - duration 2ms", "is_ground_truth_anomaly": False, "category": "health_check"},
    {"id": "ds-03", "service": "auth-service", "level": "INFO", "message": "User usr_9281 logged in successfully via OIDC token", "is_ground_truth_anomaly": False, "category": "auth_success"},
    {"id": "ds-04", "service": "payment-service", "level": "INFO", "message": "Payment intent pi_8382 processed status: succeeded", "is_ground_truth_anomaly": False, "category": "payment_normal"},
    {"id": "ds-05", "service": "cache-layer", "level": "INFO", "message": "Cache hit for key usr_session_291 in 0.4ms", "is_ground_truth_anomaly": False, "category": "cache_hit"},
    {"id": "ds-06", "service": "db-proxy", "level": "INFO", "message": "Executing SELECT * FROM orders WHERE user_id = 9281 (1.8ms)", "is_ground_truth_anomaly": False, "category": "db_normal"},
    {"id": "ds-07", "service": "order-service", "level": "INFO", "message": "Order ord_7719 created for amount 124.50 USD", "is_ground_truth_anomaly": False, "category": "order_created"},
    {"id": "ds-08", "service": "auth-service", "level": "INFO", "message": "Refreshing token for client cli_front_01", "is_ground_truth_anomaly": False, "category": "token_refresh"},
    {"id": "ds-09", "service": "db-proxy", "level": "INFO", "message": "Connection 14 acquired from pool [pool_size=50]", "is_ground_truth_anomaly": False, "category": "db_pool_ok"},
    {"id": "ds-10", "service": "cache-layer", "level": "INFO", "message": "Key user_prefs_11 evicted under LRU policy", "is_ground_truth_anomaly": False, "category": "cache_lru"},
    {"id": "ds-11", "service": "api-gateway", "level": "ERROR", "message": "HTTP 404 Not Found for resource /static/missing-icon.png requested by bot crawler", "is_ground_truth_anomaly": False, "category": "benign_404_error"},
    {"id": "ds-12", "service": "auth-service", "level": "ERROR", "message": "Single invalid password attempt for existing user bob (attempt 1/5)", "is_ground_truth_anomaly": False, "category": "benign_user_typo"},
    {"id": "ds-13", "service": "api-gateway", "level": "WARN", "message": "Client cancelled request before response completed: ECONNRESET from mobile client", "is_ground_truth_anomaly": False, "category": "benign_client_disconnect"},
    {"id": "ds-14", "service": "db-proxy", "level": "WARN", "message": "Query took 120ms to execute on unindexed reporting field", "is_ground_truth_anomaly": False, "category": "mild_latency_warning"},
    {"id": "ds-15", "service": "db-proxy", "level": "CRITICAL", "message": "Connection pool exhausted: 50/50 active connections held, 120 queued queries", "is_ground_truth_anomaly": True, "category": "resource_exhaustion"},
    {"id": "ds-16", "service": "db-proxy", "level": "CRITICAL", "message": "Transaction deadlock detected on table 'orders_lock', killing victim process 8271", "is_ground_truth_anomaly": True, "category": "db_deadlock"},
    {"id": "ds-17", "service": "auth-service", "level": "ERROR", "message": "Auth failure rate exceeded threshold: 85 failed attempts for user admin in 60s", "is_ground_truth_anomaly": True, "category": "brute_force"},
    {"id": "ds-18", "service": "api-gateway", "level": "ERROR", "message": "Circuit breaker OPEN for auth-service after 5 consecutive 503 errors", "is_ground_truth_anomaly": True, "category": "circuit_breaker"},
    {"id": "ds-19", "service": "payment-service", "level": "CRITICAL", "message": "Downstream payment gateway unreachable: Timeout after 30000ms", "is_ground_truth_anomaly": True, "category": "gateway_timeout"},
    {"id": "ds-20", "service": "auth-service", "level": "ERROR", "message": "Unhandled exception: NullPointerException at org.security.TokenValidator.verifySignature", "is_ground_truth_anomaly": True, "category": "unhandled_crash"},
    {"id": "ds-21", "service": "order-service", "level": "CRITICAL", "message": "Cascade failure: failed to persist ledger transaction due to broken db-proxy pipe", "is_ground_truth_anomaly": True, "category": "cascade_failure"},
    {"id": "ds-22", "service": "auth-service", "level": "CRITICAL", "message": "Segmentation fault (core dumped) in native crypto extension libsecp256k1.so", "is_ground_truth_anomaly": True, "category": "native_segfault"},
    {"id": "ds-23", "service": "cache-layer", "level": "INFO", "message": "System memory alert: Out of memory threshold reached, oomkiller invoked for worker 9", "is_ground_truth_anomaly": True, "category": "silent_oom"},
    {"id": "ds-24", "service": "api-gateway", "level": "WARN", "message": "Cascade failure warning: 503 Service Unavailable spike detected on upstream microservices", "is_ground_truth_anomaly": True, "category": "silent_cascade_warning"},
    {"id": "ds-25", "service": "db-proxy", "level": "INFO", "message": "Internal worker panic: fatal deadlock encountered while acquiring table mutex", "is_ground_truth_anomaly": True, "category": "silent_panic"}
]

class ModelEvaluator:
    @classmethod
    def run_benchmark(cls) -> BenchmarkResultResponse:
        start_time = time.perf_counter()
        tp = fp = tn = fn = 0
        base_tp = base_fp = base_tn = base_fn = 0
        failures = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for item in BENCHMARK_DATASET:
            gt = item["is_ground_truth_anomaly"]
            base_pred = item["level"].upper() in ("ERROR", "CRITICAL")
            if base_pred and gt: base_tp += 1
            elif base_pred and not gt: base_fp += 1
            elif not base_pred and not gt: base_tn += 1
            else: base_fn += 1

            tpl_id, _, _ = LogParser.extract_template(item["message"])
            verdict = AnomalyDetector.evaluate(item["service"], item["level"], item["message"], tpl_id, now_iso)
            pred = verdict.is_anomaly

            if pred and gt: tp += 1
            elif pred and not gt:
                fp += 1
                failures.append({"id": item["id"], "error_type": "False Positive", "message": item["message"], "verdict_score": verdict.anomaly_score, "reasons": verdict.reasons, "explanation": "Benign operational error flagged due to token entropy or rare template."})
            elif not pred and not gt: tn += 1
            else:
                fn += 1
                failures.append({"id": item["id"], "error_type": "False Negative", "message": item["message"], "verdict_score": verdict.anomaly_score, "reasons": verdict.reasons, "explanation": "Subtle anomaly scored below detection threshold."})

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        n = len(BENCHMARK_DATASET)
        latency = round(elapsed_ms / max(1, n), 4)

        precision = round(tp / (tp + fp) if (tp + fp) > 0 else 0.0, 4)
        recall = round(tp / (tp + fn) if (tp + fn) > 0 else 0.0, 4)
        f1 = round(2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0, 4)
        acc = round((tp + tn) / n if n > 0 else 0.0, 4)

        b_prec = round(base_tp / (base_tp + base_fp) if (base_tp + base_fp) > 0 else 0.0, 4)
        b_rec = round(base_tp / (base_tp + base_fn) if (base_tp + base_fn) > 0 else 0.0, 4)
        b_f1 = round(2 * (b_prec * b_rec) / (b_prec + b_rec) if (b_prec + b_rec) > 0 else 0.0, 4)
        f1_imp = round(((f1 - b_f1) / max(0.01, b_f1)) * 100.0, 2)
        run_id = f"eval_{uuid.uuid4().hex[:8]}"

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO evaluation_runs (id, timestamp, dataset_name, sample_count, precision_score,
                   recall_score, f1_score, baseline_precision, baseline_recall, baseline_f1, latency_ms, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, now_iso, "CloudMicroservice-Benchmark-v1", n, precision, recall, f1, b_prec, b_rec, b_f1, round(elapsed_ms, 2), json.dumps({"tp": tp, "fp": fp, "tn": tn, "fn": fn}))
            )

        limitations = [
            "Cold start template rarity penalty on newly deployed microservices.",
            "Short log token sequences (< 4 tokens) carry low entropy.",
            "Assumes monotonic timestamp ordering across distributed log forwarders."
        ]

        return BenchmarkResultResponse(
            run_id=run_id, timestamp=now_iso, dataset_name="CloudMicroservice-Benchmark-v1", sample_count=n,
            true_positives=tp, false_positives=fp, true_negatives=tn, false_negatives=fn,
            precision=precision, recall=recall, f1_score=f1, accuracy=acc, latency_ms_per_item=latency,
            baseline_precision=b_prec, baseline_recall=b_rec, baseline_f1=b_f1, f1_improvement_pct=f1_imp,
            failure_cases=failures, limitations=limitations
        )
