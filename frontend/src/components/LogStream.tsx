import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { LogEntry, LogTemplate } from '../types';
import { Search, Filter, Plus, FileCode, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';

export const LogStream: React.FC<{ canMutate: boolean }> = ({ canMutate }) => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [service, setService] = useState('');
  const [level, setLevel] = useState('');
  const [severity, setSeverity] = useState('');
  const [anomalyOnly, setAnomalyOnly] = useState(false);
  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const [showIngest, setShowIngest] = useState(false);
  const [rawLogs, setRawLogs] = useState('');
  const [ingestSvc, setIngestSvc] = useState('api-gateway');
  const [ingestLvl, setIngestLvl] = useState('INFO');
  const [ingesting, setIngesting] = useState(false);

  const [showTpls, setShowTpls] = useState(false);
  const [templates, setTemplates] = useState<LogTemplate[]>([]);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getLogs({
        service: service || undefined,
        level: level || undefined,
        severity: severity || undefined,
        is_anomaly: anomalyOnly ? true : undefined,
        search: search || undefined,
        limit: 50,
        offset: 0
      });
      setLogs(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Query failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [service, level, severity, anomalyOnly]);

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawLogs.trim()) return;
    try {
      setIngesting(true);
      const lines = rawLogs.split('\n').filter((l) => l.trim().length > 0);
      await api.ingestLogs(lines.map((msg) => ({ service: ingestSvc, level: ingestLvl, message: msg })));
      setRawLogs('');
      setShowIngest(false);
      await fetchLogs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Ingest failed');
    } finally {
      setIngesting(false);
    }
  };

  const openTemplates = async () => {
    setShowTpls(true);
    try {
      const tpls = await api.getTemplates();
      setTemplates(tpls);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Template fetch failed');
    }
  };

  return (
    <div className="space-y-4 font-sans">
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl space-y-3">
        <div className="flex flex-col sm:flex-row gap-3 justify-between items-center">
          <form onSubmit={(e) => { e.preventDefault(); fetchLogs(); }} className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search message text or parameters..."
              className="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none"
            />
          </form>

          <div className="flex items-center gap-2">
            <button onClick={openTemplates} className="flex items-center gap-1.5 px-3 py-2 text-xs bg-slate-800 text-slate-200 border border-slate-700 rounded-lg hover:bg-slate-700">
              <FileCode className="w-3.5 h-3.5" /> Templates
            </button>
            {canMutate && (
              <button onClick={() => setShowIngest(true)} className="flex items-center gap-1.5 px-3 py-2 text-xs bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg shadow-sm">
                <Plus className="w-3.5 h-3.5" /> Ingest
              </button>
            )}
            <button onClick={fetchLogs} title="Refresh" className="p-2 bg-slate-800 border border-slate-700 rounded-lg hover:bg-slate-700 text-slate-300">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800 text-xs">
          <span className="text-slate-400 flex items-center gap-1"><Filter className="w-3 h-3" /> Filters:</span>
          <select value={service} onChange={(e) => setService(e.target.value)} className="bg-slate-950 border border-slate-800 text-slate-200 px-2 py-1 rounded">
            <option value="">All Services</option>
            <option value="api-gateway">api-gateway</option>
            <option value="auth-service">auth-service</option>
            <option value="payment-service">payment-service</option>
            <option value="db-proxy">db-proxy</option>
            <option value="cache-layer">cache-layer</option>
          </select>

          <select value={level} onChange={(e) => setLevel(e.target.value)} className="bg-slate-950 border border-slate-800 text-slate-200 px-2 py-1 rounded">
            <option value="">All Levels</option>
            <option value="INFO">INFO</option>
            <option value="WARN">WARN</option>
            <option value="ERROR">ERROR</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>

          <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="bg-slate-950 border border-slate-800 text-slate-200 px-2 py-1 rounded">
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
          </select>

          <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 ml-auto">
            <input type="checkbox" checked={anomalyOnly} onChange={(e) => setAnomalyOnly(e.target.checked)} className="rounded bg-slate-950 text-blue-600" />
            <span>Anomalies Only</span>
          </label>
        </div>
      </div>

      {error && <div className="p-3 bg-red-950/50 border border-red-800 text-red-200 text-xs rounded-lg">{error}</div>}

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="px-4 py-2 border-b border-slate-800 text-xs text-slate-400 flex justify-between">
          <span>{logs.length} of {total} records</span>
          <span>Deterministic scoring</span>
        </div>

        {logs.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-xs">{loading ? 'Loading...' : 'No logs found.'}</div>
        ) : (
          <div className="divide-y divide-slate-800/60 font-mono text-xs">
            {logs.map((log) => {
              const exp = expandedId === log.id;
              return (
                <div key={log.id} className="hover:bg-slate-800/30">
                  <div onClick={() => setExpandedId(exp ? null : log.id)} className="p-3 flex items-start gap-2.5 cursor-pointer">
                    <span className="text-slate-500 pt-0.5">{exp ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}</span>
                    <span className="text-[11px] text-slate-400 min-w-[120px]">{log.timestamp.slice(11, 23)}</span>
                    <span className="font-semibold text-slate-300 min-w-[95px]">{log.service}</span>
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase border ${log.level === 'CRITICAL' ? 'bg-red-950 text-red-400 border-red-800' : log.level === 'ERROR' ? 'bg-rose-950 text-rose-400 border-rose-800' : 'bg-slate-800 text-slate-300 border-slate-700'}`}>{log.level}</span>
                    <span className="flex-1 text-slate-200 truncate">{log.message}</span>
                    {log.is_anomaly && <span className="text-[10px] font-bold px-1.5 py-0.5 rounded border bg-amber-500/20 text-amber-300 border-amber-500/30">{(log.anomaly_score * 100).toFixed(0)}%</span>}
                  </div>
                  {exp && (
                    <div className="px-8 pb-3 bg-slate-950/70 border-t border-slate-800/50 space-y-2 text-xs">
                      <div className="text-slate-200 p-2 bg-slate-900 rounded select-all">{log.message}</div>
                      {log.anomaly_reasons && log.anomaly_reasons.length > 0 && (
                        <div className="text-amber-300 text-[11px]">Signals: {log.anomaly_reasons.join(' • ')}</div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {showIngest && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-5 space-y-3">
            <h2 className="text-sm font-bold text-white">Ingest Application Logs</h2>
            <form onSubmit={handleIngest} className="space-y-3">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <select value={ingestSvc} onChange={(e) => setIngestSvc(e.target.value)} className="p-1.5 bg-slate-950 border border-slate-800 rounded text-white">
                  <option value="api-gateway">api-gateway</option>
                  <option value="db-proxy">db-proxy</option>
                  <option value="auth-service">auth-service</option>
                </select>
                <select value={ingestLvl} onChange={(e) => setIngestLvl(e.target.value)} className="p-1.5 bg-slate-950 border border-slate-800 rounded text-white">
                  <option value="INFO">INFO</option>
                  <option value="ERROR">ERROR</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </div>
              <textarea rows={5} value={rawLogs} onChange={(e) => setRawLogs(e.target.value)} placeholder="Paste newline-separated log messages..." className="w-full p-2 bg-slate-950 border border-slate-800 rounded text-xs font-mono text-white" />
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setShowIngest(false)} className="px-3 py-1 bg-slate-800 text-slate-300 rounded text-xs">Cancel</button>
                <button type="submit" disabled={ingesting} className="px-3 py-1 bg-blue-600 text-white rounded text-xs font-semibold">{ingesting ? 'Analyzing...' : 'Ingest'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showTpls && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-xl w-full p-5 space-y-3 max-h-[80vh] flex flex-col">
            <div className="flex justify-between items-center text-xs">
              <span className="font-bold text-white">Mined Drain Templates</span>
              <button onClick={() => setShowTpls(false)} className="text-slate-400 hover:text-white">Close</button>
            </div>
            <div className="flex-1 overflow-y-auto space-y-2 text-xs font-mono">
              {templates.map((t) => (
                <div key={t.id} className="p-2 bg-slate-950 border border-slate-800 rounded">
                  <div className="text-blue-400 text-[10px]">{t.id} ({t.occurrence_count}x)</div>
                  <div className="text-slate-200">{t.pattern}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
