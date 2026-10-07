import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../App';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    getMe: vi.fn(),
    demoLogin: vi.fn(),
    logout: vi.fn(),
    getStats: vi.fn(),
    getLogs: vi.fn(),
    getIncidents: vi.fn(),
    getIncidentDetail: vi.fn(),
    getBenchmark: vi.fn(),
    getAuditLogs: vi.fn(),
    setCsrfToken: vi.fn(),
    getCsrfToken: vi.fn()
  }
}));

describe('Log Anomaly Detector Frontend Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(api.getMe).mockResolvedValue({
      user: {
        id: 'usr-1',
        username: 'analyst-user',
        email: 'analyst@alanvo.local',
        role: 'analyst'
      },
      csrf_token: 'csrf_mock_123',
      expires_at: '2026-10-08T00:00:00Z',
      demo_mode: true
    });

    vi.mocked(api.getStats).mockResolvedValue({
      total_logs: 1250,
      total_anomalies: 42,
      anomaly_rate: 0.0336,
      service_breakdown: { 'api-gateway': 800, 'db-proxy': 450 },
      severity_breakdown: { critical: 10, high: 20, medium: 12, low: 0 },
      active_incidents: 2,
      recent_trend: []
    });

    vi.mocked(api.getLogs).mockResolvedValue({
      total: 2,
      limit: 50,
      offset: 0,
      items: [
        {
          id: 'log-1',
          timestamp: '2026-10-07T12:00:00Z',
          service: 'db-proxy',
          level: 'CRITICAL',
          message: 'Connection pool exhausted: 50/50 connections',
          template_id: 'tpl-1',
          parameters: ['50/50'],
          anomaly_score: 0.95,
          is_anomaly: true,
          severity: 'critical',
          anomaly_reasons: ['Critical log severity', 'Resource exhaustion'],
          metadata: null,
          created_at: '2026-10-07T12:00:00Z'
        }
      ]
    });

    vi.mocked(api.getBenchmark).mockResolvedValue({
      run_id: 'eval_mock_1',
      timestamp: '2026-10-07T12:00:00Z',
      dataset_name: 'CloudMicroservice-Benchmark-v1',
      sample_count: 25,
      true_positives: 11,
      false_positives: 2,
      true_negatives: 12,
      false_negatives: 0,
      precision: 0.8462,
      recall: 1.0,
      f1_score: 0.9167,
      accuracy: 0.92,
      latency_ms_per_item: 3.4,
      baseline_precision: 0.8,
      baseline_recall: 0.7273,
      baseline_f1: 0.7619,
      f1_improvement_pct: 20.32,
      failure_cases: [],
      limitations: ['Cold start template penalty']
    });
  });

  it('renders navbar brand and telemetry dashboard stats correctly', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Log Anomaly Detector/i)).toBeInTheDocument();
    });

    expect(await screen.findByText('1,250')).toBeInTheDocument();
    expect(await screen.findByText('42')).toBeInTheDocument();
  });

  it('navigates to Log Stream tab and renders log records', async () => {
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Log Stream')).toBeInTheDocument();
    });

    const logsTab = screen.getByText('Log Stream');
    await user.click(logsTab);

    expect(await screen.findByPlaceholderText(/Search message text/i)).toBeInTheDocument();
    expect(await screen.findByText(/Connection pool exhausted/i)).toBeInTheDocument();
  });

  it('navigates to ML Benchmark tab and displays F1 evaluation metrics', async () => {
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('ML Benchmark')).toBeInTheDocument();
    });

    const evalTab = screen.getByText('ML Benchmark');
    await user.click(evalTab);

    expect(await screen.findByText(/ML Evaluation & Baseline Benchmark/i)).toBeInTheDocument();
    expect(await screen.findByText('91.67%')).toBeInTheDocument();
    expect(await screen.findByText(/Baseline:.*20\.3%/i)).toBeInTheDocument();
  });

  it('shows the upstream service as the incident root cause', async () => {
    vi.mocked(api.getIncidents).mockResolvedValue([
      {
        id: 'inc-1',
        title: 'Correlated P1 Alert: db-proxy Cascade',
        status: 'open',
        severity: 'P1',
        service: 'db-proxy',
        start_time: '2026-10-07T16:00:00+00:00',
        end_time: '2026-10-07T16:01:04+00:00',
        log_count: 2,
        summary: 'Cascade from gateway symptom to db-proxy.',
        root_cause_hypothesis: 'Root cause candidate is db-proxy: pool exhausted.',
        postmortem_notes: '',
        blast_radius: ['db-proxy', 'api-gateway'],
        advisory_provider: null,
        advisory_model: null,
        created_at: '2026-10-07T16:02:00+00:00',
        updated_at: '2026-10-07T16:02:00+00:00'
      }
    ]);
    vi.mocked(api.getIncidentDetail).mockResolvedValue({
      id: 'inc-1',
      title: 'Correlated P1 Alert: db-proxy Cascade',
      status: 'open',
      severity: 'P1',
      service: 'db-proxy',
      start_time: '2026-10-07T16:00:00+00:00',
      end_time: '2026-10-07T16:01:04+00:00',
      log_count: 2,
      summary: 'Cascade from gateway symptom to db-proxy.',
      root_cause_hypothesis: 'Root cause candidate is db-proxy: pool exhausted.',
      postmortem_notes: '',
      blast_radius: ['db-proxy', 'api-gateway'],
      advisory_provider: null,
      advisory_model: null,
      created_at: '2026-10-07T16:02:00+00:00',
      updated_at: '2026-10-07T16:02:00+00:00',
      correlated_logs: [
        {
          id: 'log-symptom',
          timestamp: '2026-10-07T16:00:00+00:00',
          service: 'api-gateway',
          level: 'CRITICAL',
          message: 'Circuit breaker OPEN for auth-service',
          template_id: 'tpl-gw',
          parameters: null,
          anomaly_score: 0.95,
          is_anomaly: true,
          severity: 'critical',
          anomaly_reasons: ['Critical log severity'],
          metadata: null,
          created_at: '2026-10-07T16:02:00+00:00'
        },
        {
          id: 'log-origin',
          timestamp: '2026-10-07T16:01:04+00:00',
          service: 'db-proxy',
          level: 'CRITICAL',
          message: 'Connection pool exhausted',
          template_id: 'tpl-db',
          parameters: null,
          anomaly_score: 0.88,
          is_anomaly: true,
          severity: 'critical',
          anomaly_reasons: ['Critical log severity'],
          metadata: null,
          created_at: '2026-10-07T16:02:00+00:00'
        }
      ],
      graph: {
        nodes: [
          { id: 'log-symptom', service: 'api-gateway', timestamp: '2026-10-07T16:00:00+00:00', level: 'CRITICAL', message: 'Circuit breaker OPEN', anomaly_score: 0.95 },
          { id: 'log-origin', service: 'db-proxy', timestamp: '2026-10-07T16:01:04+00:00', level: 'CRITICAL', message: 'Connection pool exhausted', anomaly_score: 0.88 }
        ],
        edges: [
          { source: 'log-symptom', target: 'log-origin', delay_seconds: 64, relationship: 'correlated_temporal_cluster' }
        ],
        root_cause_candidate: 'log-origin'
      }
    });

    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByText('Incident Cascades'));

    const rootLabel = await screen.findByText(/Root cause:/);
    expect(rootLabel).toHaveTextContent('db-proxy');
    expect(screen.getByText('root')).toBeInTheDocument();
  });
});
