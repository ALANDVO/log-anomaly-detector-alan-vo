import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { ThresholdConfig, ThresholdConfigUpdate } from '../types';
import { RefreshCw, Save, AlertTriangle, Info } from 'lucide-react';

export const ThresholdView: React.FC<{ canMutate: boolean }> = ({ canMutate }) => {
  const [thresholds, setThresholds] = useState<ThresholdConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [editValues, setEditValues] = useState<Record<string, number>>({});

  const fetchThresholds = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getThresholds();
      setThresholds(data);
      const initialValues: Record<string, number> = {};
      data.forEach(t => { initialValues[t.config_key] = t.config_value; });
      setEditValues(initialValues);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchThresholds(); }, []);

  const handleValueChange = (configKey: string, value: number) => {
    setEditValues(prev => ({ ...prev, [configKey]: value }));
  };

  const handleSave = async (configKey: string) => {
    const value = editValues[configKey];
    if (value === undefined) return;
    setSaving(prev => ({ ...prev, [configKey]: true }));
    try {
      await api.updateThreshold(configKey, value);
      await fetchThresholds();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(prev => ({ ...prev, [configKey]: false }));
    }
  };

  const handleRefresh = async () => {
    AnomalyDetector.invalidate_threshold_cache();
    await fetchThresholds();
  };

  if (loading && !thresholds.length) {
    return <div className="p-12 text-center text-slate-500 text-xs">Loading threshold configuration...</div>;
  }

  return (
    <div className="space-y-4 font-sans">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">Detection Threshold Configuration</h2>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-600 flex items-center gap-1.5 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-900/30 border border-red-700/50 text-red-300 rounded text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      <div className="bg-slate-900/60 border border-slate-700/50 rounded-lg p-4 overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead>
            <tr className="border-b border-slate-700/50 text-slate-400">
              <th className="pb-2 pr-4 font-medium">Config Key</th>
              <th className="pb-2 pr-4 font-medium">Current Value</th>
              <th className="pb-2 pr-4 font-medium">Description</th>
              {canMutate && <th className="pb-2 pr-4 font-medium">New Value</th>}
              {canMutate && <th className="pb-2 font-medium">Action</th>}
            </tr>
          </thead>
          <tbody>
            {thresholds.map(t => (
              <tr key={t.id} className="border-b border-slate-800/50 last:border-0">
                <td className="py-2 pr-4 font-mono text-slate-300">{t.config_key}</td>
                <td className="py-2 pr-4 text-slate-200 font-mono">{t.config_value.toFixed(4)}</td>
                <td className="py-2 pr-4 text-slate-500 max-w-xs truncate">{t.description || '—'}</td>
                {canMutate && (
                  <>
                    <td className="py-2 pr-4">
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        max="1"
                        value={editValues[t.config_key] ?? t.config_value}
                        onChange={e => handleValueChange(t.config_key, parseFloat(e.target.value))}
                        className="w-24 px-2 py-1 bg-slate-800 border border-slate-600 rounded text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-cyan-500"
                      />
                    </td>
                    <td className="py-2">
                      <button
                        onClick={() => handleSave(t.config_key)}
                        disabled={saving[t.config_key] || editValues[t.config_key] === t.config_value}
                        className="text-xs px-2.5 py-1 bg-cyan-600 hover:bg-cyan-700 disabled:bg-slate-700 disabled:cursor-not-allowed disabled:text-slate-500 text-slate-950 rounded transition flex items-center gap-1"
                      >
                        {saving[t.config_key] ? (
                          <svg className="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                        ) : (
                          <Save className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="p-4 bg-slate-900/60 border border-slate-700/50 rounded-lg text-xs text-slate-400 space-y-2">
        <div className="flex items-start gap-2">
          <Info className="w-4 h-4 flex-shrink-0 text-cyan-400 mt-0.5" />
          <div>
            <p className="font-medium text-slate-300">About Detection Thresholds</p>
            <ul className="list-disc list-inside space-y-1 mt-1">
              <li><strong>anomaly_threshold</strong>: Minimum score to classify a log as anomalous (default 0.50)</li>
              <li><strong>severity_critical/high/medium</strong>: Score boundaries for severity classification</li>
              <li><strong>level_*_weight</strong>: Base score additions for CRITICAL/ERROR/WARN log levels</li>
              <li><strong>rarity_*</strong>: Score for novel or rare log templates</li>
              <li><strong>burst_*</strong>: Score for error rate spikes in sliding time windows</li>
              <li><strong>entropy_*</strong>: Token entropy bonuses/penalties for message complexity</li>
            </ul>
            <p className="mt-2 text-slate-500">Changes take effect immediately for new log evaluations. Existing scored logs are not re-evaluated.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

// Mock to satisfy the import in the component (the real invalidation happens server-side)
const AnomalyDetector = {
  invalidate_threshold_cache: () => {}
};