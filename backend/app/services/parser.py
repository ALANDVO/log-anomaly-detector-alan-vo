import re, hashlib
from datetime import datetime, timezone
from typing import Tuple, List, Dict, Optional, Any
from app.core.database import transaction

REGEX_IP = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b')
REGEX_UUID = re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b')
REGEX_HEX = re.compile(r'\b0x[0-9a-fA-F]+\b')
REGEX_URL = re.compile(r'https?://[^\s/$.?#].[^\s]*')
REGEX_PATH = re.compile(r'(?:/[a-zA-Z0-9_\-\.]+){2,}')
REGEX_NUM = re.compile(r'\b\d+(?:\.\d+)?(?:ms|s|MB|GB|KB|kb|mb|%)?\b')
REGEX_QUOTED = re.compile(r'"[^"]*"|\'[^\']*\'')
REGEX_TS = re.compile(r'^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?')
_LV = r'DEBUG|INFO|WARN(?:ING)?|ERR(?:OR)?|CRIT(?:ICAL)?|FATAL'
REGEX_LEVEL = re.compile(rf'^\[({_LV})\]|^(?:[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+\s+\[?)?({_LV})\b', re.IGNORECASE)

class LogParser:
    @staticmethod
    def extract_level_and_clean(raw: str, default_level: str = "INFO") -> Tuple[str, str, Optional[str]]:
        ts_m = REGEX_TS.search(raw)
        ts, cleaned = (ts_m.group(0).replace(" ", "T"), raw[ts_m.end():].strip()) if ts_m else (None, raw)
        lvl_m = REGEX_LEVEL.match(cleaned)
        if lvl_m:
            l = (lvl_m.group(1) or lvl_m.group(2)).upper()
            level = "CRITICAL" if ("CRIT" in l or "FATAL" in l) else ("ERROR" if "ERR" in l else ("WARN" if "WARN" in l else ("DEBUG" if "DEBUG" in l else "INFO")))
        else:
            level = default_level.upper()
        return level, cleaned, ts

    @classmethod
    def extract_template(cls, message: str) -> Tuple[str, str, List[str]]:
        params = []
        def mask(m): params.append(m.group(0)); return "<*>"
        masked = REGEX_URL.sub(mask, message)
        masked = REGEX_UUID.sub(mask, masked)
        masked = REGEX_IP.sub(mask, masked)
        masked = REGEX_PATH.sub(mask, masked)
        masked = REGEX_HEX.sub(mask, masked)
        masked = REGEX_QUOTED.sub(mask, masked)
        masked = REGEX_NUM.sub(mask, masked)
        pattern = " ".join(masked.strip().split()) or "<empty_log>"
        tpl_id = "tpl_" + hashlib.sha256(pattern.encode("utf-8")).hexdigest()[:12]
        return tpl_id, pattern, params

    @classmethod
    def record_template(cls, template_id: str, pattern: str, sample_message: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, occurrence_count FROM templates WHERE id = ?", (template_id,))
            row = cursor.fetchone()
            if row:
                count = row["occurrence_count"] + 1
                cursor.execute("UPDATE templates SET occurrence_count = ?, last_seen = ? WHERE id = ?", (count, now, template_id))
            else:
                count = 1
                cursor.execute("INSERT INTO templates (id, pattern, sample_message, occurrence_count, first_seen, last_seen) VALUES (?, ?, ?, ?, ?, ?)",
                               (template_id, pattern, sample_message, 1, now, now))
        return {"id": template_id, "pattern": pattern, "sample_message": sample_message, "occurrence_count": count, "first_seen": now, "last_seen": now}
