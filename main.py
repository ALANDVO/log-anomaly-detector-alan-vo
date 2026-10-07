#!/usr/bin/env python3
# log-anomaly-detector — AI-powered log analysis that uses LLMs to detect anomalies, correlate events across services, and generate incident summaries from raw application and system logs.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_client import LLM
def tail(args):
    """Stream logs and detect anomalies in real-time."""
    llm = LLM()
    print(f"Tailing {args.file}... (threshold: {args.anomaly_threshold})")
    print(f"{'-'*60}")
    patterns = []
    with open(args.file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            verdict = llm.classify(
                text=f"Log line: {line}\nRecent context: {json.dumps(patterns[-5:], indent=0)}",
                categories=["normal", "warning", "anomaly", "critical"],
                instructions="Classify this log line. Consider: error codes, unusual timestamps, rate patterns, unexpected sequences. Be conservative — flag only genuine anomalies."
            )
            if verdict["category"] in ("anomaly", "critical"):
                ts = line[:20] if len(line) > 20 else ""
                print(f"\n{'!':*60}")
                print(f"ANOMALY [{verdict['category'].upper()}] conf={verdict['confidence']}")
                print(f"  {line[:120]}")
                print(f"  Why: {verdict['reasoning'][:150]}")
                print(f"{'!'*60}")
            patterns.append(line[:200])
            if len(patterns) > 100:
                patterns.pop(0)

def analyze(args):
    """Analyze a log file for anomalies and correlations."""
    llm = LLM()
    logs = load_logs(args.file)
    print(f"Loaded {len(logs)} log entries")
    # Chunk and analyze
    anomalies = []
    chunk_size = 20
    for i in range(0, len(logs), chunk_size):
        chunk = logs[i:i+chunk_size]
        verdict = llm.classify(
            text=f"Log sequence:\n{json.dumps(chunk, indent=2)}",
            categories=["normal", "degraded", "anomaly", "incident"],
            instructions="Analyze this sequence of log entries. Look for: error bursts, timeout cascades, resource exhaustion patterns, unusual request patterns, security events."
        )
        if verdict["category"] != "normal":
            anomalies.append({"range": f"{i}-{i+len(chunk)}", "assessment": verdict, "logs": chunk})
    # Correlate
    if args.correlate and len(anomalies) > 1:
        timeline = llm.generate(
            f"Here are correlated anomalies from the same log file:\n{json.dumps(anomalies, indent=2)}\n\nReconstruct the incident timeline. What happened, in what order, and what's the likely root cause?",
            system="You are an SRE reconstructing an incident timeline. Be precise with timestamps and causal links."
        )
        print(f"\n{'='*60}\nINCIDENT TIMELINE\n{'='*60}\n{timeline}")
    print(f"\nAnomalies detected: {len(anomalies)}")

def incident(args):
    """Generate an incident report for a specific time window."""
    llm = LLM()
    print(f"Generating incident report for {args.time} (window: {args.window})")
    # Load logs around the time
    logs = load_logs("incident_logs.json")
    summary = llm.generate(
        f"Incident window: {args.time} (+/- {args.window})\n\nLogs:\n{json.dumps(logs[:100], indent=2)}\n\nGenerate: 1) Impact Assessment 2) Timeline 3) Root Cause Hypothesis 4) Remediation Steps 5) Communication Draft (for stakeholders)",
        system="You are an incident commander. Write a post-incident review that's actionable and honest."
    )
    print(summary)

def load_logs(path):
    try:
        with open(path) as f:
            content = f.read().strip()
        # Try JSON lines
        try:
            return [json.loads(line) for line in content.split("\n") if line.strip()]
        except json.JSONDecodeError:
            return [line for line in content.split("\n") if line.strip()]
    except FileNotFoundError:
        # Generate sample logs for demo
        return generate_sample_logs()

def generate_sample_logs():
    import random
    logs = []
    services = ["api-gateway", "auth-service", "payment-service", "db-proxy", "cache-layer"]
    for i in range(50):
        svc = random.choice(services)
        level = random.choices(["INFO", "WARN", "ERROR", "CRITICAL"], weights=[70, 15, 10, 5])[0]
        msg = random.choice([
            "Request completed", "Connection pool exhausted", "Timeout after 30s",
            "Authentication failed for user", "Cache miss", "Slow query: 2.3s",
            "Memory usage at 92%", "Circuit breaker OPEN", "Retry attempt 3/5"
        ])
        logs.append({"ts": f"2026-04-09T14:{i//60:02d}:{i%60:02d}", "service": svc, "level": level, "msg": msg})
    return logs

if __name__ == '__main__':
    main()
