import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { ServiceDependency } from '../types';
import { Plus, RefreshCw, Trash2, Edit2, ArrowRight, GitBranch } from 'lucide-react';

export const DependencyView: React.FC<{ canMutate: boolean }> = ({ canMutate }) => {
  const [dependencies, setDependencies] = useState<ServiceDependency[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [newUpstream, setNewUpstream] = useState('');
  const [newDownstream, setNewDownstream] = useState('');
  const [newRelationship, setNewRelationship] = useState('depends_on');
  const [creating, setCreating] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editUpstream, setEditUpstream] = useState('');
  const [editDownstream, setEditDownstream] = useState('');
  const [editRelationship, setEditRelationship] = useState('depends_on');
  const [saving, setSaving] = useState(false);

  const fetchDependencies = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getDependencies();
      setDependencies(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load dependencies');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDependencies(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUpstream.trim() || !newDownstream.trim()) return;
    try {
      setCreating(true);
      setError(null);
      const dep = await api.createDependency({
        upstream: newUpstream.trim(),
        downstream: newDownstream.trim(),
        relationship: newRelationship.trim() || 'depends_on'
      });
      setDependencies(prev => [...prev, dep]);
      setShowCreate(false);
      setNewUpstream('');
      setNewDownstream('');
      setNewRelationship('depends_on');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Create failed');
    } finally {
      setCreating(false);
    }
  };

  const handleEdit = (dep: ServiceDependency) => {
    setEditingId(dep.id);
    setEditUpstream(dep.upstream);
    setEditDownstream(dep.downstream);
    setEditRelationship(dep.relationship);
  };

  const handleSave = async (id: string) => {
    if (!editUpstream.trim() || !editDownstream.trim()) return;
    try {
      setSaving(true);
      setError(null);
      const updated = await api.updateDependency(id, {
        upstream: editUpstream.trim(),
        downstream: editDownstream.trim(),
        relationship: editRelationship.trim() || 'depends_on'
      });
      setDependencies(prev => prev.map(d => d.id === id ? updated : d));
      setEditingId(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this dependency?')) return;
    try {
      setError(null);
      await api.deleteDependency(id);
      setDependencies(prev => prev.filter(d => d.id !== id));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  const handleCancel = () => {
    setEditingId(null);
    setShowCreate(false);
    setNewUpstream('');
    setNewDownstream('');
    setNewRelationship('depends_on');
  };

  if (loading && !dependencies.length) {
    return <div className="p-12 text-center text-slate-500 text-xs">Loading dependencies...</div>;
  }

  return (
    <div className="space-y-4 font-sans">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 bg-slate-900 border border-slate-800 p-4 rounded-xl">
        <div>
          <h1 className="text-base font-bold text-white">Service Dependency Topology</h1>
          <p className="text-xs text-slate-400">Configure upstream/downstream relationships for cascade correlation.</p>
        </div>
        <div className="flex items-center gap-2">
          {canMutate && (
            <button onClick={() => setShowCreate(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg shadow-sm">
              <Plus className="w-3.5 h-3.5" /> Add Dependency
            </button>
          )}
          <button onClick={fetchDependencies} className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-slate-800 text-slate-200 border border-slate-700 rounded-lg hover:bg-slate-700">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
      </div>

      {error && <div className="p-3 bg-red-950/50 border border-red-800 text-red-200 text-xs rounded-lg">{error}</div>}

      {showCreate && canMutate && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
          <h2 className="text-xs font-bold text-white">Add Service Dependency</h2>
          <form onSubmit={handleCreate} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <input type="text" value={newUpstream} onChange={e => setNewUpstream(e.target.value)} placeholder="Upstream service (provider)" className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded text-xs text-white" required />
              <ArrowRight className="self-center text-slate-500" size={16} />
              <input type="text" value={newDownstream} onChange={e => setNewDownstream(e.target.value)} placeholder="Downstream service (consumer)" className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded text-xs text-white" required />
            </div>
            <input type="text" value={newRelationship} onChange={e => setNewRelationship(e.target.value)} placeholder="Relationship (e.g., depends_on, calls, replicates)" className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded text-xs text-white" />
            <div className="flex justify-end gap-2">
              <button type="button" onClick={handleCancel} className="px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg">Cancel</button>
              <button type="submit" disabled={creating} className="px-3 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg disabled:opacity-50">
                {creating ? 'Creating...' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        {dependencies.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-xs">No dependencies configured. Click "Add Dependency" to define service topology.</div>
        ) : (
          <div className="divide-y divide-slate-800/60">
            {dependencies.map((dep) => (
              <div key={dep.id} className={`p-4 space-y-2 ${editingId === dep.id ? 'bg-slate-950/40' : ''}`}>
                {editingId === dep.id ? (
                  <form onSubmit={e => { e.preventDefault(); handleSave(dep.id); }} className="space-y-3">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <input type="text" value={editUpstream} onChange={e => setEditUpstream(e.target.value)} className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded text-xs text-white" required />
                      <ArrowRight className="self-center text-slate-500" size={16} />
                      <input type="text" value={editDownstream} onChange={e => setEditDownstream(e.target.value)} className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded text-xs text-white" required />
                    </div>
                    <input type="text" value={editRelationship} onChange={e => setEditRelationship(e.target.value)} className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded text-xs text-white" />
                    <div className="flex justify-end gap-2">
                      <button type="button" onClick={handleCancel} className="px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg">Cancel</button>
                      <button type="submit" disabled={saving} className="px-3 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg disabled:opacity-50">
                        {saving ? 'Saving...' : 'Save'}
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <GitBranch className="w-4 h-4 text-blue-400 flex-shrink-0" />
                        <div className="flex items-center gap-2 flex-wrap min-w-0">
                          <code className="text-blue-300 font-mono text-xs truncate max-w-[200px]">{dep.upstream}</code>
                          <ArrowRight className="w-4 h-4 text-slate-500 flex-shrink-0" size={16} />
                          <code className="text-amber-300 font-mono text-xs truncate max-w-[200px]">{dep.downstream}</code>
                          <span className="px-1.5 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px] font-mono">{dep.relationship}</span>
                        </div>
                      </div>
                      {canMutate && (
                        <div className="flex items-center gap-1.5">
                          <button onClick={() => handleEdit(dep)} className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded" title="Edit"><Edit2 className="w-3.5 h-3.5" /></button>
                          <button onClick={() => handleDelete(dep.id)} className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-950/30 rounded" title="Delete"><Trash2 className="w-3.5 h-3.5" /></button>
                        </div>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono">
                      Created: {dep.created_at.slice(0, 19).replace('T', ' ')} | Updated: {dep.updated_at.slice(0, 19).replace('T', ' ')}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
        <h2 className="text-xs font-bold text-white uppercase tracking-wider">Usage Notes</h2>
        <ul className="text-slate-400 text-xs space-y-1 list-disc list-inside">
          <li>Upstream services are dependencies (e.g., databases, auth providers) that downstream services rely on.</li>
          <li>During incident correlation, the engine traverses upstream from a symptom to identify the root cause candidate.</li>
          <li>Changes take effect immediately for new incident correlation runs.</li>
          <li>Default topology includes: db-proxy → auth-service/payment-service/order-service, cache-layer → api-gateway/auth-service, auth-service → api-gateway, payment-service → api-gateway/order-service.</li>
        </ul>
      </div>
    </div>
  );
};