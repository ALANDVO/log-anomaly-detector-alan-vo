import {
  UserSession, LogEntry, LogStats, LogTemplate, Incident, IncidentDetail,
  LLMAdvisoryResult, BenchmarkResult, AuditRecord
} from '../types';

let currentCsrf = '';
export const setCsrfToken = (t: string) => { currentCsrf = t; };
export const getCsrfToken = () => currentCsrf;

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  headers.set('Accept', 'application/json');
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (currentCsrf && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method || 'GET')) {
    headers.set('X-CSRF-Token', currentCsrf);
  }

  const res = await fetch(path, { ...options, headers, credentials: 'include' });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      if (err?.detail) msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
    } catch {}
    throw new Error(msg);
  }
  return res.headers.get('content-type')?.includes('application/json') ? res.json() : (res.text() as unknown as T);
}

export const api = {
  async getMe(): Promise<UserSession> {
    const s = await request<UserSession>('/api/auth/me');
    if (s.csrf_token) setCsrfToken(s.csrf_token);
    return s;
  },
  async demoLogin(role: 'viewer' | 'analyst' | 'admin' = 'analyst'): Promise<UserSession> {
    const s = await request<UserSession>('/api/auth/demo-login', { method: 'POST', body: JSON.stringify({ role }) });
    if (s.csrf_token) setCsrfToken(s.csrf_token);
    return s;
  },
  async logout(): Promise<void> {
    await request('/api/auth/logout', { method: 'POST' });
    setCsrfToken('');
  },
  async getLogs(params: { service?: string; level?: string; is_anomaly?: boolean; severity?: string; search?: string; limit?: number; offset?: number } = {}) {
    const q = new URLSearchParams();
    if (params.service) q.set('service', params.service);
    if (params.level) q.set('level', params.level);
    if (params.is_anomaly !== undefined) q.set('is_anomaly', String(params.is_anomaly));
    if (params.severity) q.set('severity', params.severity);
    if (params.search) q.set('search', params.search);
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    return request<{ total: number; limit: number; offset: number; items: LogEntry[] }>(`/api/logs?${q}`);
  },
  getStats: () => request<LogStats>('/api/logs/stats'),
  getTemplates: () => request<LogTemplate[]>('/api/logs/templates'),
  ingestLogs: (logs: Array<{ service: string; level: string; message: string; timestamp?: string }>) =>
    request<{ total_ingested: number; anomalies_detected: number; incidents_created: number; items: LogEntry[] }>('/api/logs/ingest', { method: 'POST', body: JSON.stringify({ logs, trigger_correlation: true }) }),
  seedSampleData: () => request('/api/logs/seed-sample-data', { method: 'POST' }),
  getIncidents: (st?: string) => request<Incident[]>(`/api/incidents${st ? `?status=${encodeURIComponent(st)}` : ''}`),
  getIncidentDetail: (id: string) => request<IncidentDetail>(`/api/incidents/${id}`),
  updateIncident: (id: string, u: { status?: string; postmortem_notes?: string }) =>
    request<Incident>(`/api/incidents/${id}`, { method: 'PATCH', body: JSON.stringify(u) }),
  generateAdvisory: (id: string, guidance?: string) =>
    request<LLMAdvisoryResult>(`/api/incidents/${id}/advisory`, { method: 'POST', body: JSON.stringify({ operator_guidance: guidance }) }),
  exportPostmortem: (id: string, fmt: 'json' | 'markdown' = 'markdown') =>
    request(`/api/incidents/${id}/export?format=${fmt}`),
  getBenchmark: () => request<BenchmarkResult>('/api/evaluation/benchmark'),
  runBenchmark: () => request<BenchmarkResult>('/api/evaluation/benchmark', { method: 'POST' }),
  getAuditLogs: () => request<AuditRecord[]>('/api/audit')
};
