#!/usr/bin/env python3
import sys, os, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from app.services.parser import LogParser
from app.services.detector import AnomalyDetector
from app.services.correlator import EventCorrelator
from app.services.evaluator import ModelEvaluator
from app.core.database import init_db

def tail_cmd(args):
    init_db()
    if not os.path.exists(args.file):
        sys.exit(f"File not found: {args.file}")
    print(f"[*] Streaming {args.file} (threshold: {args.anomaly_threshold})")
    with open(args.file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            lvl, msg, ts = LogParser.extract_level_and_clean(line.strip())
            tpl_id, _, _ = LogParser.extract_template(msg)
            v = AnomalyDetector.evaluate(args.service, lvl, msg, tpl_id, ts or "2026-10-07T12:00:00")
            if v.anomaly_score >= args.anomaly_threshold:
                print(f"[!] ANOMALY [{v.severity.upper()}] ({v.anomaly_score:.2f}): {msg[:100]}")

def analyze_cmd(args):
    init_db()
    if not os.path.exists(args.file):
        sys.exit(f"File not found: {args.file}")
    with open(args.file, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    anomalies = []
    for i, line in enumerate(lines):
        lvl, msg, ts = LogParser.extract_level_and_clean(line)
        tpl_id, _, _ = LogParser.extract_template(msg)
        v = AnomalyDetector.evaluate(args.service, lvl, msg, tpl_id, ts or f"2026-10-07T12:00:{i%60:02d}")
        if v.is_anomaly:
            anomalies.append({"id": f"log_{i}", "timestamp": ts or "2026-10-07T12:00:00", "service": args.service, "level": lvl, "message": msg, "anomaly_score": v.anomaly_score})
    print(f"[+] Anomalies: {len(anomalies)} / {len(lines)}")
    if args.correlate and anomalies:
        g = EventCorrelator.build_correlation_graph(anomalies)
        print(f"[+] Correlated DAG: {len(g.nodes)} nodes, {len(g.edges)} cascade edges. Root: {g.root_cause_candidate}")

def bench_cmd(_):
    init_db()
    r = ModelEvaluator.run_benchmark()
    print(f"Dataset: {r.dataset_name} | F1: {r.f1_score:.4f} (Baseline: {r.baseline_f1:.4f}, +{r.f1_improvement_pct:.1f}%) | Latency: {r.latency_ms_per_item:.2f}ms")

def main():
    p = argparse.ArgumentParser(description="Log Anomaly Detector CLI")
    sub = p.add_subparsers(dest="command", required=True)
    t = sub.add_parser("tail")
    t.add_argument("-f", "--file", required=True)
    t.add_argument("--service", default="api-gateway")
    t.add_argument("--anomaly-threshold", type=float, default=0.60)
    t.set_defaults(func=tail_cmd)
    a = sub.add_parser("analyze")
    a.add_argument("--file", required=True)
    a.add_argument("--service", default="api-gateway")
    a.add_argument("--correlate", action="store_true")
    a.set_defaults(func=analyze_cmd)
    b = sub.add_parser("benchmark")
    b.set_defaults(func=bench_cmd)
    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
