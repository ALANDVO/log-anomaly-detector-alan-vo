import React, { useState } from 'react';
import { api } from '../api/client';
import { LLMAdvisoryResult } from '../types';
import { Bot, Sparkles, AlertCircle, Info, Loader2 } from 'lucide-react';

interface AdvisoryProps {
  incidentId: string;
  canMutate: boolean;
  existingHypothesis: string | null;
  onAdvisoryGenerated: () => Promise<void>;
}

export const AdvisoryPanel: React.FC<AdvisoryProps> = ({
  incidentId, canMutate, existingHypothesis, onAdvisoryGenerated
}) => {
  const [loading, setLoading] = useState(false);
  const [guidance, setGuidance] = useState('');
  const [result, setResult] = useState<LLMAdvisoryResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGen = async () => {
    if (!canMutate) return;
    try {
      setLoading(true);
      setError(null);
      const res = await api.generateAdvisory(incidentId, guidance || undefined);
      setResult(res);
      await onAdvisoryGenerated();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Advisory failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3 font-sans">
      <div className="flex justify-between items-center gap-2">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-purple-400" />
          <h3 className="text-xs font-bold text-white uppercase flex items-center gap-1.5">
            Opt-In LLM Root-Cause Advisory
            <span className="text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/30 px-1 py-0.2 rounded">ADVISORY</span>
          </h3>
        </div>
        {canMutate && (
          <button onClick={handleGen} disabled={loading} className="flex items-center gap-1 px-2.5 py-1 bg-purple-600 hover:bg-purple-500 text-white rounded text-xs font-semibold disabled:opacity-50">
            {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
            {loading ? 'Synthesizing...' : 'Request Advisory'}
          </button>
        )}
      </div>

      {canMutate && (
        <input type="text" value={guidance} onChange={(e) => setGuidance(e.target.value)} placeholder="Optional operator guidance..." className="w-full px-2.5 py-1 bg-slate-950 border border-slate-800 rounded text-xs text-white" />
      )}

      {error && <div className="p-2 bg-red-950 border border-red-800 text-red-200 text-xs rounded">{error}</div>}

      {result?.advisory_status === 'skipped' && (
        <div className="p-2.5 bg-amber-950/40 border border-amber-800/80 rounded text-xs text-amber-200">
          <div className="font-semibold flex items-center gap-1"><Info className="w-3.5 h-3.5" /> LLM API Key Not Configured</div>
          <div className="text-[11px] text-amber-300/80">{result.provider_error}</div>
        </div>
      )}

      {result?.advisory_status === 'error' && (
        <div className="p-2.5 bg-red-950/40 border border-red-800/80 rounded text-xs text-red-200">
          <div className="font-semibold flex items-center gap-1"><AlertCircle className="w-3.5 h-3.5" /> Provider Error</div>
          <div className="text-[11px] text-red-300/80">{result.provider_error}</div>
        </div>
      )}

      <div className="p-2.5 bg-slate-950 rounded border border-slate-800 text-xs space-y-1">
        <div className="text-[10px] font-bold text-slate-400 uppercase">Hypothesis:</div>
        <p className="text-slate-200">{result?.root_cause_hypothesis || existingHypothesis || 'No advisory synthesized yet.'}</p>
      </div>

      {result?.recommended_remediation && result.recommended_remediation.length > 0 && (
        <div className="p-2.5 bg-slate-950 rounded border border-slate-800 text-xs space-y-1">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Remediation:</div>
          <ul className="list-disc list-inside text-slate-300 space-y-0.5 text-[11px]">
            {result.recommended_remediation.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
};
