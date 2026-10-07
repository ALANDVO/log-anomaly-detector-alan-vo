export type UserRole = 'viewer' | 'analyst' | 'admin';

export interface User { id: string; username: string; email: string; role: UserRole; }
export interface UserSession { user: User; csrf_token: string; expires_at: string; demo_mode: boolean; }

export interface LogEntry {
  id: string; timestamp: string; service: string; level: string; message: string;
  template_id: string | null; parameters: string[] | null; anomaly_score: number;
  is_anomaly: boolean; severity: 'low' | 'medium' | 'high' | 'critical';
  anomaly_reasons: string[] | null; metadata: Record<string, unknown> | null; created_at: string;
}

export interface LogTemplate {
  id: string; pattern: string; sample_message: string; occurrence_count: number; first_seen: string; last_seen: string;
}

export interface LogStats {
  total_logs: number; total_anomalies: number; anomaly_rate: number;
  service_breakdown: Record<string, number>; severity_breakdown: Record<string, number>;
  active_incidents: number; recent_trend: Array<{ bucket: string; total: number; anomalies: number }>;
}

export interface CascadeNode { id: string; service: string; timestamp: string; level: string; message: string; anomaly_score: number; }
export interface CascadeEdge { source: string; target: string; delay_seconds: number; relationship: string; }
export interface CorrelationGraph { nodes: CascadeNode[]; edges: CascadeEdge[]; root_cause_candidate: string | null; }

export interface Incident {
  id: string; title: string; status: 'open' | 'acknowledged' | 'investigating' | 'resolved';
  severity: 'P1' | 'P2' | 'P3' | 'P4'; service: string; start_time: string; end_time: string;
  log_count: number; summary: string; root_cause_hypothesis: string | null;
  postmortem_notes: string | null; blast_radius: string[] | null;
  advisory_provider: string | null; advisory_model: string | null; created_at: string; updated_at: string;
}

export interface IncidentDetail extends Incident { correlated_logs: LogEntry[]; graph: CorrelationGraph; }

export interface LLMAdvisoryResult {
  provider: string; model: string; advisory_status: 'success' | 'error' | 'skipped';
  is_advisory: boolean; grounded_record_count: number; root_cause_hypothesis: string;
  recommended_remediation: string[]; timeline_narrative: string; provider_error: string | null;
}

export interface BenchmarkResult {
  run_id: string; timestamp: string; dataset_name: string; sample_count: number;
  true_positives: number; false_positives: number; true_negatives: number; false_negatives: number;
  precision: number; recall: number; f1_score: number; accuracy: number; latency_ms_per_item: number;
  baseline_precision: number; baseline_recall: number; baseline_f1: number; f1_improvement_pct: number;
  failure_cases: Array<{ id: string; error_type: string; message: string; verdict_score: number; reasons: string[]; explanation: string; }>;
  limitations: string[];
}

export interface AuditRecord {
  id: string; timestamp: string; user_id: string; username: string; action: string;
  entity_type: string; entity_id: string; details: string | null; ip_address: string;
}
