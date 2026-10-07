import sqlite3, threading
from pathlib import Path
from typing import Generator, Optional
from contextlib import contextmanager
from app.core.config import settings

_thread_local = threading.local()

def get_db_path() -> str:
    raw = settings.DATABASE_URL
    p_str = raw[len("sqlite:///"):] if raw.startswith("sqlite:///") else (raw[len("sqlite://"):] if raw.startswith("sqlite://") else raw)
    p = Path(p_str).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path(), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

@contextmanager
def transaction(existing_conn: Optional[sqlite3.Connection] = None) -> Generator[sqlite3.Connection, None, None]:
    if existing_conn is not None: yield existing_conn; return
    current = getattr(_thread_local, "conn", None)
    if current is not None: yield current; return

    conn = get_connection()
    _thread_local.conn = conn
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        _thread_local.conn = None
        conn.close()

def init_db() -> None:
    with transaction() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('viewer', 'analyst', 'admin')), created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, username TEXT NOT NULL,
            email TEXT NOT NULL, role TEXT NOT NULL, csrf_token TEXT NOT NULL,
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS templates (
            id TEXT PRIMARY KEY, pattern TEXT NOT NULL, sample_message TEXT NOT NULL,
            occurrence_count INTEGER DEFAULT 1, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS logs (
            id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, service TEXT NOT NULL,
            level TEXT NOT NULL, message TEXT NOT NULL, template_id TEXT, parameters TEXT,
            anomaly_score REAL NOT NULL DEFAULT 0.0, is_anomaly INTEGER NOT NULL DEFAULT 0,
            severity TEXT NOT NULL DEFAULT 'low', anomaly_reasons TEXT, metadata TEXT, created_at TEXT NOT NULL,
            FOREIGN KEY (template_id) REFERENCES templates(id)
        );
        CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
        CREATE INDEX IF NOT EXISTS idx_logs_service ON logs(service);
        CREATE INDEX IF NOT EXISTS idx_logs_is_anomaly ON logs(is_anomaly);

        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('open', 'acknowledged', 'investigating', 'resolved')),
            severity TEXT NOT NULL CHECK(severity IN ('P1', 'P2', 'P3', 'P4')), service TEXT NOT NULL,
            start_time TEXT NOT NULL, end_time TEXT NOT NULL, log_count INTEGER NOT NULL DEFAULT 0,
            summary TEXT NOT NULL, root_cause_hypothesis TEXT, postmortem_notes TEXT, blast_radius TEXT,
            advisory_provider TEXT, advisory_model TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS incident_logs (
            incident_id TEXT NOT NULL, log_id TEXT NOT NULL, PRIMARY KEY (incident_id, log_id),
            FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
            FOREIGN KEY (log_id) REFERENCES logs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, user_id TEXT NOT NULL, username TEXT NOT NULL,
            action TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, details TEXT, ip_address TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evaluation_runs (
            id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, dataset_name TEXT NOT NULL, sample_count INTEGER NOT NULL,
            precision_score REAL NOT NULL, recall_score REAL NOT NULL, f1_score REAL NOT NULL,
            baseline_precision REAL NOT NULL, baseline_recall REAL NOT NULL, baseline_f1 REAL NOT NULL,
            latency_ms REAL NOT NULL, details TEXT NOT NULL
        );
        """)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as c FROM users")
        if cursor.fetchone()["c"] == 0:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            cursor.executemany(
                "INSERT INTO users (id, username, email, role, created_at) VALUES (?, ?, ?, ?, ?)",
                [("usr-admin", "admin", "admin@alanvo.local", "admin", now),
                 ("usr-analyst", "analyst", "analyst@alanvo.local", "analyst", now),
                 ("usr-viewer", "viewer", "viewer@alanvo.local", "viewer", now)]
            )
