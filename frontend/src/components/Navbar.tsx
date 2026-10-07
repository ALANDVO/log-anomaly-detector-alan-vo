import React from 'react';
import { UserSession } from '../types';
import { Activity, LogOut } from 'lucide-react';

interface NavbarProps {
  session: UserSession | null;
  activeTab: string;
  onTabChange: (tab: string) => void;
  onLoginRole: (role: 'viewer' | 'analyst' | 'admin') => void;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ session, activeTab, onTabChange, onLoginRole, onLogout }) => {
  const tabs = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'logs', label: 'Log Stream' },
    { id: 'incidents', label: 'Incident Cascades' },
    { id: 'evaluation', label: 'ML Benchmark' },
    ...(session?.user.role === 'admin' ? [{ id: 'audit', label: 'Audit Trail' }] : [])
  ];

  return (
    <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600/20 text-blue-400 rounded-lg border border-blue-500/30">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <span className="font-bold text-white text-lg tracking-tight">Log Anomaly Detector</span>
              <span className="text-xs text-slate-400 block -mt-1">Alan Vo | AI & ML Observability</span>
            </div>
          </div>

          <nav className="flex items-center gap-1 sm:gap-2">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  activeTab === tab.id ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            {session ? (
              <div className="flex items-center gap-3">
                <div className="text-right hidden sm:block">
                  <div className="text-xs font-medium text-white">{session.user.username}</div>
                  <div className="flex items-center justify-end gap-1">
                    <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      {session.user.role}
                    </span>
                    {session.demo_mode && (
                      <span className="text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 px-1 py-0.5 rounded">DEMO</span>
                    )}
                  </div>
                </div>

                {session.demo_mode && (
                  <div className="flex items-center gap-1 border border-slate-700 rounded-md p-1 bg-slate-800 text-xs">
                    <span className="text-slate-400 px-1">Role:</span>
                    {(['viewer', 'analyst', 'admin'] as const).map((r) => (
                      <button
                        key={r}
                        onClick={() => onLoginRole(r)}
                        className={`px-1.5 py-0.5 rounded text-[11px] ${session.user.role === r ? 'bg-blue-600 text-white font-bold' : 'text-slate-400 hover:text-white'}`}
                      >
                        {r[0].toUpperCase()}
                      </button>
                    ))}
                  </div>
                )}

                <button onClick={onLogout} title="Logout" className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-md">
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <button onClick={() => onLoginRole('analyst')} className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-md font-medium">
                Demo Login
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
