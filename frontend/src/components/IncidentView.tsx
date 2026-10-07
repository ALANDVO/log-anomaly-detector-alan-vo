import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Incident, IncidentDetail } from '../types';
import { AdvisoryPanel } from './AdvisoryPanel';
import { ArrowRight, Download, GitCommit, FileText, RefreshCw } from 'lucide-react';

export const IncidentView: React.FC<{ canMutate: boolean }> = ({ canMutate }) => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState('');
  const [updating, setUpdating] = useState(false);

  const fetchIncidents = async () => {
    try {
      setLoading(true);
      const data = await api.getIncidents();
      setIncidents(data);
      if (data.length > 0 && !selectedId) setSelectedId(data[0].id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error fetching incidents');
    } finally {
      setLoading(false);
    }
  };

  const fetchDetail = async (id: string) => {
    try {
      const d = await api.getIncidentDetail(id);
      setDetail(d);
      setNotes(d.postmortem_notes || '');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error loading details');
    }
  };

  useEffect(() => { fetchIncidents(); }, []);
  useEffect(() => { if (selectedId) fetchDetail(selectedId); }, [selectedId]);

  const handleStatus = async (st: 'open' | 'acknowledged' | 'investigating' | 'resolved') => {
    if (!selectedId || !canMutate) return;
    try {
      setUpdating(true);
      await api.updateIncident(selectedId, { status: st });
      await fetchDetail(selectedId);
      await fetchIncidents();
    } finally {
      setUpdating(false);
    }
  };

  const handleSaveNotes = async () => {
    if (!selectedId || !canMutate) return;
    try {
      setUpdating(true);
      await api.updateIncident(selectedId, { postmortem_notes: notes });
      await fetchDetail(selectedId);
    } finally {
      setUpdating(false);
    }
  };

  const handleExport = async (fmt: 'markdown' | 'json') => {
    if (!selectedId) return;
    const res = await api.exportPostmortem(selectedId, fmt);
    const blob = new Blob([typeof res === 'string' ? res : JSON.stringify(res, null, 2)], {
      type: fmt === 'markdown' ? 'text/markdown' : 'application/json'
    });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `incident-${selectedId}.${fmt === 'markdown' ? 'md' : 'json'}`;
    a.click();
  };

  return (
    <div className="space-y-4 font-sans">
      <div className="flex justify-between items-center bg-slate-900 border border-slate-800 p-4 rounded-xl">
        <div>
          <h1 className="text-base font-bold text-white">Correlated Incident Cascades</h1>
          <p className="text-xs text-slate-400">Temporal cross-service clustering & root-cause correlation.</p>
        </div>
        <button onClick={fetchIncidents} className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {error && <div className="p-3 bg-red-950/50 border border-red-800 text-red-200 text-xs rounded-lg">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden divide-y divide-slate-800">
          <div className="p-3 text-xs font-semibold text-slate-400 bg-slate-950/40">Incidents ({incidents.length})</div>
          {incidents.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-xs">No incidents detected.</div>
          ) : (
            incidents.map((inc) => (
              <div key={inc.id} onClick={() => setSelectedId(inc.id)} className={`p-3.5 cursor-pointer space-y-1.5 ${selectedId === inc.id ? 'bg-blue-950/30 border-l-4 border-l-blue-500' : 'hover:bg-slate-800/30'}`}>
                <div className="flex justify-between text-xs">
                  <span className={`font-bold px-1.5 py-0.2 rounded border text-[10px] ${inc.severity === 'P1' ? 'text-red-400 border-red-800 bg-red-950' : 'text-amber-400 border-amber-800 bg-amber-950'}`}>{inc.severity}</span>
                  <span className="font-mono text-slate-400 uppercase text-[11px]">{inc.status}</span>
                </div>
                <div className="text-xs font-semibold text-white line-clamp-1">{inc.title}</div>
                <div className="text-[11px] text-slate-400 flex justify-between"><span>{inc.service}</span><span>{inc.log_count} events</span></div>
              </div>
            ))
          )}
        </div>

        <div className="lg:col-span-2 space-y-5">
          {detail ? (
            <>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
                <div className="flex justify-between items-start gap-2">
                  <div>
                    <h2 className="text-sm font-bold text-white flex items-center gap-2">
                      <span className="px-1.5 py-0.5 bg-red-950 text-red-400 border border-red-800 rounded text-xs">{detail.severity}</span>
                      {detail.title}
                    </h2>
                    <p className="text-[11px] text-slate-400 mt-1">{detail.start_time} | Blast: {detail.blast_radius?.join(', ') || detail.service}</p>
                  </div>
                  <button onClick={() => handleExport('markdown')} className="flex items-center gap-1.5 px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg">
                    <Download className="w-3.5 h-3.5" /> Export .MD
                  </button>
                </div>

                <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1">
                    <span className="text-slate-400">Status:</span>
                    {(['open', 'acknowledged', 'investigating', 'resolved'] as const).map((st) => (
                      <button key={st} disabled={!canMutate || updating} onClick={() => handleStatus(st)} className={`px-2 py-0.5 rounded text-[10px] font-medium uppercase ${detail.status === st ? 'bg-blue-600 text-white font-bold' : 'bg-slate-800 text-slate-400 hover:text-white'}`}>
                        {st}
                      </button>
                    ))}
                  </div>
                </div>

                <p className="text-xs text-slate-300 bg-slate-950 p-2.5 rounded border border-slate-800">{detail.summary}</p>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-bold text-white flex items-center gap-1.5"><GitCommit className="w-3.5 h-3.5 text-blue-400" /> Cascade DAG</span>
                  <span className="text-slate-400 text-[11px]">Root cause: <code className="text-amber-400">{detail.graph.nodes.find((n) => n.id === detail.graph.root_cause_candidate)?.service || 'None'}</code></span>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-800 space-y-2 font-mono text-xs">
                  {detail.graph.edges.length === 0 ? (
                    <div className="text-slate-500 text-center py-2 text-[11px]">Single event incident without downstream cascade.</div>
                  ) : (
                    detail.graph.edges.map((e, idx) => (
                      <div key={idx} className="flex items-center gap-2 p-1.5 bg-slate-900/60 rounded text-[11px]">
                        <span className="text-blue-300 px-1.5 bg-slate-800 rounded">{e.source}</span>
                        <ArrowRight className="w-3 h-3 text-slate-500" />
                        <span className="text-slate-400">+{e.delay_seconds}s ({e.relationship})</span>
                        <ArrowRight className="w-3 h-3 text-slate-500" />
                        <span className="text-amber-300 px-1.5 bg-slate-800 rounded">{e.target}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <AdvisoryPanel incidentId={detail.id} canMutate={canMutate} existingHypothesis={detail.root_cause_hypothesis} onAdvisoryGenerated={async () => fetchDetail(detail.id)} />

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-bold text-white flex items-center gap-1.5"><FileText className="w-3.5 h-3.5 text-emerald-400" /> Postmortem Notes</span>
                  {canMutate && <button onClick={handleSaveNotes} disabled={updating} className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium">Save</button>}
                </div>
                <textarea rows={3} value={notes} disabled={!canMutate} onChange={(e) => setNotes(e.target.value)} placeholder="Record remediation notes..." className="w-full p-2 bg-slate-950 border border-slate-800 rounded text-xs font-mono text-slate-200" />
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2 font-mono text-xs">
                <div className="text-slate-400 font-bold uppercase text-[11px]">Correlated Timeline ({detail.correlated_logs.length})</div>
                <div className="divide-y divide-slate-800/60 max-h-48 overflow-y-auto pr-1">
                  {detail.correlated_logs.map((l) => (
                    <div key={l.id} className="py-1.5 flex gap-2 text-[11px]">
                      <span className="text-slate-400">{l.timestamp.slice(11, 19)}</span>
                      <span className="text-blue-400 font-semibold min-w-[85px]">{l.service}</span>
                      <span className="text-slate-200 flex-1 truncate">{l.message}</span>
                      {l.id === detail.graph.root_cause_candidate && <span className="text-amber-300 font-bold">root</span>}
                      <span className="text-amber-400 font-bold">{(l.anomaly_score * 100).toFixed(0)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-10 text-center text-slate-500 text-xs">Select an incident to view.</div>
          )}
        </div>
      </div>
    </div>
  );
};
