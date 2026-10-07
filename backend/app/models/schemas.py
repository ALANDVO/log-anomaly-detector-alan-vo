from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

class UserBase(BaseModel):
    id: str; username: str; email: str; role: Literal["viewer", "analyst", "admin"]

class UserSession(BaseModel):
    user: UserBase; csrf_token: str; expires_at: str; demo_mode: bool

class DemoLoginRequest(BaseModel):
    role: Literal["viewer", "analyst", "admin"] = "analyst"
    username: Optional[str] = None

class LogEntryCreate(BaseModel):
    timestamp: Optional[str] = None
    service: str = "api-gateway"
    level: str = "INFO"
    message: str
    metadata: Optional[Dict[str, Any]] = None

class LogIngestRequest(BaseModel):
    logs: List[LogEntryCreate]
    trigger_correlation: bool = True

class LogTemplateResponse(BaseModel):
    id: str; pattern: str; sample_message: str; occurrence_count: int; first_seen: str; last_seen: str

class AnomalyVerdict(BaseModel):
    is_anomaly: bool; anomaly_score: float; severity: Literal["low", "medium", "high", "critical"]; reasons: List[str]; template_id: Optional[str] = None

class LogEntryResponse(BaseModel):
    id: str; timestamp: str; service: str; level: str; message: str
    template_id: Optional[str]; parameters: Optional[List[str]]; anomaly_score: float
    is_anomaly: bool; severity: str; anomaly_reasons: Optional[List[str]]; metadata: Optional[Dict[str, Any]]; created_at: str

class LogIngestResponse(BaseModel):
    total_ingested: int; anomalies_detected: int; incidents_created: int; items: List[LogEntryResponse]

class LogStatsResponse(BaseModel):
    total_logs: int; total_anomalies: int; anomaly_rate: float
    service_breakdown: Dict[str, int]; severity_breakdown: Dict[str, int]; active_incidents: int; recent_trend: List[Dict[str, Any]]

class CascadeNode(BaseModel):
    id: str; service: str; timestamp: str; level: str; message: str; anomaly_score: float

class CascadeEdge(BaseModel):
    source: str; target: str; delay_seconds: float; relationship: str

class CorrelationGraph(BaseModel):
    nodes: List[CascadeNode]; edges: List[CascadeEdge]; root_cause_candidate: Optional[str]

class IncidentResponse(BaseModel):
    id: str; title: str; status: Literal["open", "acknowledged", "investigating", "resolved"]
    severity: Literal["P1", "P2", "P3", "P4"]; service: str; start_time: str; end_time: str
    log_count: int; summary: str; root_cause_hypothesis: Optional[str] = None
    postmortem_notes: Optional[str] = None; blast_radius: Optional[List[str]] = None
    advisory_provider: Optional[str] = None; advisory_model: Optional[str] = None
    created_at: str; updated_at: str

class IncidentDetailResponse(IncidentResponse):
    correlated_logs: List[LogEntryResponse]; graph: CorrelationGraph

class IncidentUpdateRequest(BaseModel):
    status: Optional[Literal["open", "acknowledged", "investigating", "resolved"]] = None
    postmortem_notes: Optional[str] = None

class LLMAdvisoryRequest(BaseModel):
    operator_guidance: Optional[str] = None

class LLMAdvisoryResponse(BaseModel):
    provider: str; model: str; advisory_status: Literal["success", "error", "skipped"]
    is_advisory: bool = True; grounded_record_count: int; root_cause_hypothesis: str
    recommended_remediation: List[str]; timeline_narrative: str; provider_error: Optional[str] = None

class LabeledLogItem(BaseModel):
    id: str; service: str; level: str; message: str; is_ground_truth_anomaly: bool; ground_truth_category: str

class BenchmarkResultResponse(BaseModel):
    run_id: str; timestamp: str; dataset_name: str; sample_count: int
    true_positives: int; false_positives: int; true_negatives: int; false_negatives: int
    precision: float; recall: float; f1_score: float; accuracy: float; latency_ms_per_item: float
    baseline_precision: float; baseline_recall: float; baseline_f1: float; f1_improvement_pct: float
    failure_cases: List[Dict[str, Any]]; limitations: List[str]

class AuditLogResponse(BaseModel):
    id: str; timestamp: str; user_id: str; username: str; action: str; entity_type: str; entity_id: str; details: Optional[str]; ip_address: str
