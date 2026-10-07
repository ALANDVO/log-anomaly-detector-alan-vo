import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { AuditRecord } from '../types';
import { Shield, RefreshCw } from 'lucide-react';

export const AuditView: React.FC = () => {
  const [logs, setLogs] = useState<AuditRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAudit = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getAuditLogs();
      setLogs(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Audit query failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAudit(); }, []);

  return (
    <div className="space-y-4 font-sans">
      <div className="flex justify-between items-center bg-slate-900 border border-slate-800 p-4 rounded-xl">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-red-400" />
          <div>
            <h1 className="text-base font-bold text-white">Security & Mutation Audit Trail</h1>
            <p className="text-xs text-slate-400">Immutable ledger of administrative mutations and session events.</p>
          </div>
        </div>
        <button onClick={fetchAudit} className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {error && <div className="p-3 bg-red-950/50 border border-red-800 text-red-200 text-xs rounded-lg">{error}</div>}

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <table className="w-full text-xs text-left font-mono">
          <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400">
            <tr>
              <th className="py-2 px-3">Timestamp</th>
              <th className="py-2 px-3">User</th>
              <th className="py-2 px-3">Action</th>
              <th className="py-2 px-3">Target</th>
              <th className="py-2 px-3">IP</th>
              <th className="py-2 px-3">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-200">
            {logs.length === 0 ? (
              <tr><td colSpan={6} className="text-center py-8 text-slate-500">{loading ? 'Loading...' : 'No audit records.'}</td></tr>
            ) : (
              logs.map((r) => (
                <tr key={r.id} className="hover:bg-slate-800/30">
                  <td className="py-2 px-3 text-slate-400">{r.timestamp.slice(0, 19).replace('T', ' ')}</td>
                  <td className="py-2 px-3 font-bold text-white">{r.username}</td>
                  <td className="py-2 px-3"><span className="px-1.5 py-0.5 bg-slate-800 text-blue-300 rounded text-[11px]">{r.action}</span></td>
                  <td className="py-2 px-3 text-slate-300">{r.entity_type}:{r.entity_id}</td>
                  <td className="py-2 px-3 text-slate-400">{r.ip_address}</td>
                  <td className="py-2 px-3 text-slate-300 truncate max-w-xs">{r.details || '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
