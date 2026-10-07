import uuid
from datetime import datetime, timezone
from typing import Optional, List
from app.core.database import transaction
from app.models.schemas import AuditLogResponse

class AuditService:
    @staticmethod
    def record(user_id: str, username: str, action: str, entity_type: str, entity_id: str, ip_address: str = "127.0.0.1", details: Optional[str] = None) -> str:
        audit_id = f"aud_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO audit_logs (id, timestamp, user_id, username, action, entity_type, entity_id, details, ip_address)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (audit_id, now_iso, user_id, username, action, entity_type, entity_id, details, ip_address)
            )
        return audit_id

    @staticmethod
    def list_logs(limit: int = 50, offset: int = 0, entity_type: Optional[str] = None, action: Optional[str] = None) -> List[AuditLogResponse]:
        query, params = "SELECT * FROM audit_logs WHERE 1=1", []
        if entity_type: query += " AND entity_type = ?"; params.append(entity_type)
        if action: query += " AND action = ?"; params.append(action)
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [
            AuditLogResponse(
                id=r["id"], timestamp=r["timestamp"], user_id=r["user_id"], username=r["username"],
                action=r["action"], entity_type=r["entity_type"], entity_id=r["entity_id"],
                details=r["details"], ip_address=r["ip_address"]
            ) for r in rows
        ]
