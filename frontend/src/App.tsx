import React, { useState, useEffect } from 'react';
import { api } from './api/client';
import { UserSession } from './types';
import { Navbar } from './components/Navbar';
import { Dashboard } from './components/Dashboard';
import { LogStream } from './components/LogStream';
import { IncidentView } from './components/IncidentView';
import { EvaluationView } from './components/EvaluationView';
import { AuditView } from './components/AuditView';
import { AlertCircle, ShieldAlert } from 'lucide-react';

export const App: React.FC = () => {
  const [session, setSession] = useState<UserSession | null>(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [initializing, setInitializing] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);

  const init = async () => {
    try {
      setInitializing(true);
      setInitError(null);
      const s = await api.getMe();
      setSession(s);
    } catch {
      try {
        const demo = await api.demoLogin('analyst');
        setSession(demo);
      } catch (err: unknown) {
        setInitError(err instanceof Error ? err.message : 'Login required');
      }
    } finally {
      setInitializing(false);
    }
  };

  useEffect(() => { init(); }, []);

  const handleRole = async (r: 'viewer' | 'analyst' | 'admin') => {
    try {
      const s = await api.demoLogin(r);
      setSession(s);
    } catch (e: unknown) {
      alert(`Demo login failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const handleLogout = async () => {
    try {
      await api.logout();
      setSession(null);
      setActiveTab('dashboard');
    } catch {}
  };

  const canMutate = session?.user.role === 'analyst' || session?.user.role === 'admin';

  if (initializing) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-400 font-mono text-xs">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mb-2" />
        <p>Initializing telemetry channels...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col text-slate-100 font-sans">
      <Navbar session={session} activeTab={activeTab} onTabChange={setActiveTab} onLoginRole={handleRole} onLogout={handleLogout} />

      {session?.demo_mode && (
        <div className="bg-amber-950/40 border-b border-amber-900/60 px-4 py-1 text-center text-xs text-amber-300 flex items-center justify-center gap-1.5">
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Local Demo Mode Active (127.0.0.1). Production builds enforce Keycloak OIDC.</span>
        </div>
      )}

      {initError && !session && (
        <div className="max-w-7xl mx-auto px-4 mt-4">
          <div className="p-3 bg-red-950/40 border border-red-800 rounded-lg text-xs text-red-200 flex items-center justify-between">
            <span className="flex items-center gap-2"><AlertCircle className="w-4 h-4" /> {initError}</span>
            <button onClick={() => handleRole('analyst')} className="px-2 py-0.5 bg-red-800 rounded font-bold">Retry</button>
          </div>
        </div>
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-5">
        {activeTab === 'dashboard' && <Dashboard onNavigate={setActiveTab} canMutate={canMutate} />}
        {activeTab === 'logs' && <LogStream canMutate={canMutate} />}
        {activeTab === 'incidents' && <IncidentView canMutate={canMutate} />}
        {activeTab === 'evaluation' && <EvaluationView canMutate={canMutate} />}
        {activeTab === 'audit' && session?.user.role === 'admin' && <AuditView />}
      </main>

      <footer className="bg-slate-900 border-t border-slate-800 py-4 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex justify-between items-center">
          <div>Built by <strong className="text-slate-300">Alan Vo</strong> (alanvo@gmail.com) — AI/ML Observability</div>
          <div className="space-x-3 text-[11px]"><span>Template Mining</span>•<span>Keycloak OIDC</span>•<span>LLM Advisory</span></div>
        </div>
      </footer>
    </div>
  );
};
