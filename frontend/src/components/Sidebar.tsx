import React from 'react';
import {
  LayoutDashboard,
  Cloud,
  FolderLock,
  Sliders,
  DollarSign,
  Radio,
  FlaskConical,
  Database,
  Layers,
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab }) => {
  const menuItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'providers', label: 'Cloud Providers', icon: Cloud },
    { id: 'files', label: 'File Management', icon: FolderLock },
    { id: 'policies', label: 'Replication Policies', icon: Sliders },
    { id: 'cost', label: 'Cost Analytics', icon: DollarSign },
    { id: 'dr', label: 'Disaster Recovery', icon: Radio },
    { id: 'benchmarks', label: 'Research Benchmarks', icon: FlaskConical },
  ];

  return (
    <aside className="w-64 bg-[#0B0F19] border-r border-slate-800 flex flex-col justify-between flex-shrink-0 h-screen sticky top-0">
      <div>
        {/* Brand / Logo */}
        <div className="h-16 flex items-center px-6 border-b border-slate-800 gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 text-white">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white leading-tight">
              Multi-Cloud DR
            </h1>
            <span className="text-[10px] text-cyan-400 font-mono tracking-wider uppercase font-semibold">
              Cost-Aware Engine
            </span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="p-4 space-y-1.5">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-sm shadow-cyan-950'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Architecture Footer Box */}
      <div className="p-4 m-3 bg-[#111827] border border-slate-800 rounded-xl">
        <div className="flex items-center gap-2 mb-2 text-xs font-semibold text-slate-300">
          <Database className="w-3.5 h-3.5 text-cyan-400" />
          <span>Active Architecture</span>
        </div>
        <div className="text-[11px] text-slate-400 space-y-1 font-mono">
          <div className="flex justify-between">
            <span>Primary:</span>
            <span className="text-blue-400">AWS S3</span>
          </div>
          <div className="flex justify-between">
            <span>Secondary:</span>
            <span className="text-purple-400">GCP GCS</span>
          </div>
          <div className="flex justify-between">
            <span>Integrity:</span>
            <span className="text-emerald-400">SHA-256</span>
          </div>
        </div>
      </div>
    </aside>
  );
};

