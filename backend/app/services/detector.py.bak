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
    _threshold_cache: Optional[Dict[str, float]] = None

    @classmethod
    def _get_thresholds(cls) -> Dict[str, float]:
        """Fetch current threshold configuration from database."""
        if cls._threshold_cache is not None:
            return cls._threshold_cache
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT config_key, config_value FROM threshold_config")
            rows = cursor.fetchall()
        cls._threshold_cache = {row["config_key"]: row["config_value"] for row in rows}
        # Fallback defaults if DB is empty
        defaults = {
            "anomaly_threshold": 0.50,
            "severity_critical": 0.80,
            "severity_high": 0.65,
            "severity_medium": 0.40,
            "level_critical_weight": 0.40,
            "level_error_weight": 0.25,
            "level_warn_weight": 0.10,
            "rarity_first_occurrence": 0.35,
            "rarity_under_5": 0.20,
            "burst_high_density": 0.35,
            "burst_elevated": 0.20,
            "entropy_high_threshold": 4.2,
            "entropy_high_bonus": 0.15,
            "entropy_low_threshold": 1.0,
            "entropy_low_bonus": 0.10,
        }
        for k, v in defaults.items():
            cls._threshold_cache.setdefault(k, v)
        return cls._threshold_cache

    @classmethod
    def invalidate_threshold_cache(cls) -> None:
        cls._threshold_cache = None

    @staticmethod
    def calculate_token_entropy(tokens: List[str]) -> float:
        if not tokens: return 0.0
        n, counts = len(tokens), {}
        for t in tokens: counts[t] = counts.get(t, 0) + 1
        return -sum((c / n) * math.log2(c / n) for c in counts.values())

    @classmethod
    def evaluate_template_rarity(cls, template_id: str) -> Tuple[float, Optional[str]]:
        thresholds = cls._get_thresholds()
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT occurrence_count FROM templates WHERE id = ?", (template_id,))
            row = cursor.fetchone()
            if not row or row["occurrence_count"] <= 1:
                return thresholds["rarity_first_occurrence"], "First occurrence of template pattern"
            count = row["occurrence_count"]
            return (thresholds["rarity_under_5"], f"Rare template pattern ({count}x)") if count < 5 else (0.0, None)

    @classmethod
    def evaluate_burst_rate(cls, service: str, timestamp_iso: str) -> Tuple[float, Optional[str]]:
        thresholds = cls._get_thresholds()
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
            if ratio > 0.4: return thresholds["burst_high_density"], f"High error density in window ({errors}/{total})"
            elif ratio > 0.2: return thresholds["burst_elevated"], f"Elevated error burst in window ({errors}/{total})"
        return 0.0, None

    @classmethod
    def evaluate(cls, service: str, level: str, message: str, template_id: str, timestamp_iso: str) -> AnomalyVerdict:
        thresholds = cls._get_thresholds()
        reasons, raw_score = [], 0.0
        lvl = level.upper()
        if lvl == "CRITICAL":
            raw_score += thresholds["level_critical_weight"]; reasons.append("Critical log severity")
        elif lvl == "ERROR":
            raw_score += thresholds["level_error_weight"]; reasons.append("Error log level")
        elif lvl == "WARN":
            raw_score += thresholds["level_warn_weight"]

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
        if len(tokens) > 15 and entropy > thresholds["entropy_high_threshold"]:
            raw_score += thresholds["entropy_high_bonus"]; reasons.append(f"High token entropy ({entropy:.2f})")
        elif len(tokens) > 5 and entropy < thresholds["entropy_low_threshold"]:
            raw_score += thresholds["entropy_low_bonus"]; reasons.append(f"Low token entropy ({entropy:.2f})")

        burst_score, burst_reason = cls.evaluate_burst_rate(service, timestamp_iso)
        raw_score += burst_score
        if burst_reason: reasons.append(burst_reason)

        final = min(1.0, round(raw_score, 3))
        is_anom = final >= thresholds["anomaly_threshold"]
        sev = (
            "critical" if final >= thresholds["severity_critical"]
            else ("high" if final >= thresholds["severity_high"]
            else ("medium" if final >= thresholds["severity_medium"] else "low"))
        )
        if not is_anom and not reasons: reasons.append("Nominal operational baseline")

        return AnomalyVerdict(is_anomaly=is_anom, anomaly_score=final, severity=sev, reasons=reasons, template_id=template_id)