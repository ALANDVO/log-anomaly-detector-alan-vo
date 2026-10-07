import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { LogStats } from '../types';
import { Activity, AlertTriangle, ShieldAlert, Layers, RefreshCw, Database } from 'lucide-react';

export const Dashboard: React.FC<{ onNavigate: (tab: string) => void; canMutate: boolean }> = ({ onNavigate, canMutate }) => {
  const [stats, setStats] = useState<LogStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getStats();
      setStats(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Telemetry load error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchStats(); }, []);

  const handleSeed = async () => {
    try {
      setSeeding(true);
      await api.seedSampleData();
      await fetchStats();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Seed failed');
    } finally {
      setSeeding(false);
    }
  };

  if (loading && !stats) {
    return <div className="p-16 text-center text-slate-500 text-xs">Loading telemetry...</div>;
  }

  return (
    <div className="space-y-4 font-sans">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 bg-slate-900 border border-slate-800 p-4 rounded-xl">
        <div>
          <h1 className="text-base font-bold text-white">System Anomaly Telemetry</h1>
          <p className="text-xs text-slate-400">Deterministic log anomaly detection & cascade correlation.</p>
        </div>
        <div className="flex items-center gap-2">
          {canMutate && (
            <button onClick={handleSeed} disabled={seeding} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg shadow-sm">
              <Database className="w-3.5 h-3.5" /> {seeding ? 'Generating...' : 'Seed Cascade Trace'}
            </button>
          )}
          <button onClick={fetchStats} className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-slate-800 text-slate-200 border border-slate-700 rounded-lg hover:bg-slate-700">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
      </div>

      {error && <div className="p-3 bg-red-950/50 border border-red-800 text-red-200 text-xs rounded-lg">{error}</div>}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
          <div className="flex justify-between items-center text-xs text-slate-400"><span>Total Ingested</span><Activity className="w-4 h-4 text-blue-400" /></div>
          <div className="text-2xl font-bold text-white mt-1">{stats?.total_logs.toLocaleString() ?? 0}</div>
        </div>
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
          <div className="flex justify-between items-center text-xs text-slate-400"><span>Anomalies</span><AlertTriangle className="w-4 h-4 text-amber-400" /></div>
          <div className="text-2xl font-bold text-amber-300 mt-1">{stats?.total_anomalies.toLocaleString() ?? 0}</div>
          <div className="text-[10px] text-slate-500">Rate: {((stats?.anomaly_rate ?? 0) * 100).toFixed(1)}%</div>
        </div>
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
          <div className="flex justify-between items-center text-xs text-slate-400"><span>Active Incidents</span><ShieldAlert className="w-4 h-4 text-red-400" /></div>
          <div className="text-2xl font-bold text-red-300 mt-1">{stats?.active_incidents ?? 0}</div>
        </div>
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
          <div className="flex justify-between items-center text-xs text-slate-400"><span>Services</span><Layers className="w-4 h-4 text-emerald-400" /></div>
          <div className="text-2xl font-bold text-white mt-1">{Object.keys(stats?.service_breakdown || {}).length}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
          <h2 className="text-xs font-bold text-white uppercase tracking-wider">Service Distribution</h2>
          <div className="space-y-2 text-xs">
            {Object.entries(stats?.service_breakdown || {}).map(([s, c]) => (
              <div key={s} className="space-y-1">
                <div className="flex justify-between text-[11px]"><span className="text-slate-300">{s}</span><span className="text-slate-500">{c}</span></div>
                <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500" style={{ width: `${(c / Math.max(1, stats?.total_logs || 1)) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
          <h2 className="text-xs font-bold text-white uppercase tracking-wider">Severity Distribution</h2>
          <div className="space-y-2 text-xs">
            {(['critical', 'high', 'medium', 'low'] as const).map((sev) => {
              const c = stats?.severity_breakdown[sev] || 0;
              const color = sev === 'critical' ? 'bg-red-500' : sev === 'high' ? 'bg-amber-500' : 'bg-blue-500';
              return (
                <div key={sev} className="space-y-1">
                  <div className="flex justify-between text-[11px]"><span className="uppercase text-slate-300">{sev}</span><span className="text-slate-500">{c}</span></div>
                  <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                    <div className={`h-full ${color}`} style={{ width: `${(c / Math.max(1, stats?.total_anomalies || 1)) * 100}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <button onClick={() => onNavigate('logs')} className="p-3 bg-slate-900 border border-slate-800 rounded-xl text-left hover:border-slate-700">
          <div className="text-xs font-bold text-white">Inspect Log Stream →</div>
          <div className="text-[11px] text-slate-400 mt-0.5">Filter by service, templates & scores.</div>
        </button>
        <button onClick={() => onNavigate('incidents')} className="p-3 bg-slate-900 border border-slate-800 rounded-xl text-left hover:border-slate-700">
          <div className="text-xs font-bold text-white">Analyze Incident Cascades →</div>
          <div className="text-[11px] text-slate-400 mt-0.5">Explore DAG graphs & LLM advisory.</div>
        </button>
        <button onClick={() => onNavigate('evaluation')} className="p-3 bg-slate-900 border border-slate-800 rounded-xl text-left hover:border-slate-700">
          <div className="text-xs font-bold text-white">ML Benchmark Pipeline →</div>
          <div className="text-[11px] text-slate-400 mt-0.5">Reproduce F1 against ground truth.</div>
        </button>
      </div>
    </div>
  );
};
