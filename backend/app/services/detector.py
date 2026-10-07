import math, re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from app.core.database import transaction
from app.models.schemas import AnomalyVerdict

SUSPICIOUS_KEYWORDS = {
    "deadlock": 0.40, "out of memory": 0.45, "oomkiller": 0.50,
    "connection pool exhausted": 0.40, "circuit breaker open": 0.45,
    "fatal": 0.35, "panic": 0.45, "segmentation fault": 0.50,
    "unhandled exception": 0.35, "timeout": 0.20, "refused": 0.25,
    "503 service unavailable": 0.30, "500 internal server error": 0.25,
    "cascade failure": 0.45, "corrupted": 0.40
}

class AnomalyDetector:
    @staticmethod
    def calculate_token_entropy(tokens: List[str]) -> float:
        if not tokens: return 0.0
        n, counts = len(tokens), {}
        for t in tokens: counts[t] = counts.get(t, 0) + 1
        return -sum((c / n) * math.log2(c / n) for c in counts.values())

    @classmethod
    def evaluate_template_rarity(cls, template_id: str) -> Tuple[float, Optional[str]]:
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT occurrence_count FROM templates WHERE id = ?", (template_id,))
            row = cursor.fetchone()
            if not row or row["occurrence_count"] <= 1:
                return 0.35, "First occurrence of template pattern"
            count = row["occurrence_count"]
            return (0.20, f"Rare template pattern ({count}x)") if count < 5 else (0.0, None)

    @classmethod
    def evaluate_burst_rate(cls, service: str, timestamp_iso: str) -> Tuple[float, Optional[str]]:
        try: target_dt = datetime.fromisoformat(timestamp_iso)
        except Exception: target_dt = datetime.now(timezone.utc)
        w_start, target_str = (target_dt - timedelta(minutes=10)).isoformat(), target_dt.isoformat()

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT COUNT(*) as t, SUM(CASE WHEN level IN ('ERROR', 'CRITICAL') THEN 1 ELSE 0 END) as e
                   FROM logs WHERE service = ? AND timestamp >= ? AND timestamp <= ?""",
                (service, w_start, target_str)
            )
            row = cursor.fetchone()
            total, errors = row["t"] if row and row["t"] else 0, row["e"] if row and row["e"] else 0

        if total > 0 and errors > 3:
            ratio = errors / total
            if ratio > 0.4: return 0.35, f"High error density in window ({errors}/{total})"
            elif ratio > 0.2: return 0.20, f"Elevated error burst in window ({errors}/{total})"
        return 0.0, None

    @classmethod
    def evaluate(cls, service: str, level: str, message: str, template_id: str, timestamp_iso: str) -> AnomalyVerdict:
        reasons, raw_score = [], 0.0
        lvl = level.upper()
        if lvl == "CRITICAL": raw_score += 0.40; reasons.append("Critical log severity")
        elif lvl == "ERROR": raw_score += 0.25; reasons.append("Error log level")
        elif lvl == "WARN": raw_score += 0.10

        rarity_score, rarity_reason = cls.evaluate_template_rarity(template_id)
        raw_score += rarity_score
        if rarity_reason: reasons.append(rarity_reason)

        lower = message.lower()
        matched = [kw for kw in SUSPICIOUS_KEYWORDS if kw in lower]
        if matched:
            raw_score += sum(SUSPICIOUS_KEYWORDS[kw] for kw in matched[:2])
            reasons.append(f"High-risk keywords: {', '.join(matched[:2])}")

        tokens = re.findall(r'\b\w+\b', message)
        entropy = cls.calculate_token_entropy(tokens)
        if len(tokens) > 15 and entropy > 4.2:
            raw_score += 0.15; reasons.append(f"High token entropy ({entropy:.2f})")
        elif len(tokens) > 5 and entropy < 1.0:
            raw_score += 0.10; reasons.append(f"Low token entropy ({entropy:.2f})")

        burst_score, burst_reason = cls.evaluate_burst_rate(service, timestamp_iso)
        raw_score += burst_score
        if burst_reason: reasons.append(burst_reason)

        final = min(1.0, round(raw_score, 3))
        is_anom = final >= 0.50
        sev = "critical" if final >= 0.80 else ("high" if final >= 0.65 else ("medium" if final >= 0.40 else "low"))
        if not is_anom and not reasons: reasons.append("Nominal operational baseline")

        return AnomalyVerdict(is_anomaly=is_anom, anomaly_score=final, severity=sev, reasons=reasons, template_id=template_id)
