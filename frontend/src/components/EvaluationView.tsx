import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { BenchmarkResult } from '../types';
import { Cpu, Play, AlertTriangle } from 'lucide-react';

export const EvaluationView: React.FC<{ canMutate: boolean }> = ({ canMutate }) => {
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBenchmark = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getBenchmark();
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Benchmark retrieval failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRun = async () => {
    if (!canMutate) return;
    try {
      setRunning(true);
      const data = await api.runBenchmark();
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Benchmark run failed');
    } finally {
      setRunning(false);
    }
  };

  useEffect(() => { fetchBenchmark(); }, []);

  if (loading && !result) {
    return <div className="p-12 text-center text-slate-500 text-xs">Loading ML benchmark...</div>;
  }

  return (
    <div className="space-y-4 font-sans">
      <div className="flex justify-between items-center bg-slate-900 border border-slate-800 p-4 rounded-xl">
        <div>
          <div className="flex items-center gap-2">
            <Cpu className="w-5 h-5 text-emerald-400" />
            <h1 className="text-base font-bold text-white">ML Evaluation & Baseline Benchmark</h1>
          </div>
          <p className="text-xs text-slate-400">Offline validation against labeled ground truth.</p>
        </div>
        {canMutate && (
          <button onClick={handleRun} disabled={running} className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold shadow-sm">
            <Play className={`w-3.5 h-3.5 ${running ? 'animate-spin' : ''}`} />
            {running ? 'Evaluating...' : 'Run Benchmark'}
          </button>
        )}
      </div>

      {error && <div className="p-3 bg-red-950/50 border border-red-800 text-red-200 text-xs rounded-lg">{error}</div>}

      {result && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
              <span className="text-[11px] text-slate-400">Detector F1 Score</span>
              <div className="text-xl font-bold text-emerald-400">{(result.f1_score * 100).toFixed(2)}%</div>
              <div className="text-[10px] text-slate-500">Baseline: {(result.baseline_f1 * 100).toFixed(2)}% (+{result.f1_improvement_pct.toFixed(1)}%)</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
              <span className="text-[11px] text-slate-400">Precision / Recall</span>
              <div className="text-xl font-bold text-white">{(result.precision * 100).toFixed(1)}% / {(result.recall * 100).toFixed(1)}%</div>
              <div className="text-[10px] text-slate-500">Baseline: {(result.baseline_precision * 100).toFixed(1)}% / {(result.baseline_recall * 100).toFixed(1)}%</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
              <span className="text-[11px] text-slate-400">Accuracy & Size</span>
              <div className="text-xl font-bold text-blue-400">{(result.accuracy * 100).toFixed(1)}%</div>
              <div className="text-[10px] text-slate-500">{result.sample_count} labeled records</div>
            </div>
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl">
              <span className="text-[11px] text-slate-400">Inference Latency</span>
              <div className="text-xl font-bold text-white">{result.latency_ms_per_item.toFixed(2)} ms</div>
              <div className="text-[10px] text-slate-500">Per log item</div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
              <h2 className="text-xs font-bold text-white uppercase tracking-wider">Confusion Matrix ({result.dataset_name})</h2>
              <div className="grid grid-cols-2 gap-2 text-center font-mono text-xs">
                <div className="p-2.5 bg-emerald-950/40 border border-emerald-800/80 rounded">
                  <span className="text-[10px] text-emerald-400 block">TP (True Outage)</span>
                  <span className="text-lg font-bold text-white">{result.true_positives}</span>
                </div>
                <div className="p-2.5 bg-red-950/30 border border-red-800/60 rounded">
                  <span className="text-[10px] text-red-400 block">FP (False Alarm)</span>
                  <span className="text-lg font-bold text-white">{result.false_positives}</span>
                </div>
                <div className="p-2.5 bg-amber-950/30 border border-amber-800/60 rounded">
                  <span className="text-[10px] text-amber-400 block">FN (Missed Outage)</span>
                  <span className="text-lg font-bold text-white">{result.false_negatives}</span>
                </div>
                <div className="p-2.5 bg-blue-950/40 border border-blue-800/80 rounded">
                  <span className="text-[10px] text-blue-400 block">TN (Nominal Traffic)</span>
                  <span className="text-lg font-bold text-white">{result.true_negatives}</span>
                </div>
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
              <h2 className="text-xs font-bold text-white uppercase tracking-wider">Model vs Baseline Heuristics</h2>
              <table className="w-full text-xs font-mono text-left">
                <thead className="text-slate-400 border-b border-slate-800">
                  <tr><th className="pb-1.5">Metric</th><th className="pb-1.5">Baseline</th><th className="pb-1.5 text-emerald-400">Detector</th><th className="pb-1.5 text-blue-400">Delta</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  <tr><td className="py-1.5">F1</td><td>{(result.baseline_f1 * 100).toFixed(1)}%</td><td className="text-emerald-400 font-bold">{(result.f1_score * 100).toFixed(1)}%</td><td className="text-blue-400">+{result.f1_improvement_pct.toFixed(1)}%</td></tr>
                  <tr><td className="py-1.5">Precision</td><td>{(result.baseline_precision * 100).toFixed(1)}%</td><td className="text-emerald-400 font-bold">{(result.precision * 100).toFixed(1)}%</td><td>+{((result.precision - result.baseline_precision) * 100).toFixed(1)}%</td></tr>
                  <tr><td className="py-1.5">Recall</td><td>{(result.baseline_recall * 100).toFixed(1)}%</td><td className="text-emerald-400 font-bold">{(result.recall * 100).toFixed(1)}%</td><td>+{((result.recall - result.baseline_recall) * 100).toFixed(1)}%</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
            <h2 className="text-xs font-bold text-white flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Failure Cases ({result.failure_cases.length})</h2>
            <div className="space-y-1.5">
              {result.failure_cases.map((fc, i) => (
                <div key={i} className="p-2 bg-slate-950 border border-slate-800 rounded text-xs space-y-0.5">
                  <div className="flex justify-between text-[10px] text-amber-400 font-bold uppercase"><span>{fc.error_type}</span><span>{(fc.verdict_score * 100).toFixed(0)}%</span></div>
                  <div className="font-mono text-slate-200 select-all text-[11px]">{fc.message}</div>
                  <div className="text-slate-400 text-[10px]">{fc.explanation}</div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
