import React from 'react';
import { Cloud, ShieldCheck, AlertTriangle } from 'lucide-react';
import { HealthStatusReport } from '../types';

interface NavbarProps {
  healthReport: HealthStatusReport | null;
  activeTab: string;
}

export const Navbar: React.FC<NavbarProps> = ({ healthReport, activeTab }) => {
  const isSimulation = healthReport?.simulation_mode ?? true;
  const isFailover = healthReport?.failover_active ?? false;

  const tabLabels: Record<string, string> = {
    overview: 'Overview & System Telemetry',
    providers: 'Multi-Cloud Providers (AWS S3 & GCS)',
    files: 'File Management & Object Versioning',
    policies: 'Replication Policies & Scoring Weights',
    cost: 'Cost Analytics & Budget Optimization',
    dr: 'Disaster Recovery & Failover Simulator',
    benchmarks: 'Research Experiments & Benchmarks',
  };

  return (
    <header className="h-16 border-b border-slate-800 bg-[#0E131F]/90 backdrop-blur sticky top-0 z-30 flex items-center justify-between px-6">
      <div className="flex items-center space-x-4">
        <h2 className="text-lg font-semibold text-white tracking-tight">
          {tabLabels[activeTab] || 'Dashboard'}
        </h2>
      </div>

      <div className="flex items-center space-x-4">
        {/* Failover Status Pill */}
        {isFailover ? (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30 animate-pulse">
            <AlertTriangle className="w-3.5 h-3.5" />
            FAILOVER ACTIVE (SERVING FROM GCS)
          </span>
        ) : (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <ShieldCheck className="w-3.5 h-3.5" />
            PRIMARY ROUTED (AWS S3)
          </span>
        )}

        {/* Storage Mode Pill */}
        <span className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${
          isSimulation
            ? 'bg-amber-500/10 text-amber-300 border-amber-500/20'
            : 'bg-cyan-500/10 text-cyan-300 border-cyan-500/20'
        }`}>
          <Cloud className="w-3.5 h-3.5" />
          {isSimulation ? 'Mode: Local Simulation' : 'Mode: Live Cloud SDKs'}
        </span>

        {/* User Badge */}
        <div className="flex items-center space-x-2 pl-2 border-l border-slate-800">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center text-xs font-bold text-white shadow-inner">
            AD
          </div>
          <div className="hidden md:block text-left">
            <div className="text-xs font-semibold text-slate-200">Admin Engineer</div>
            <div className="text-[10px] text-slate-400 font-mono">B.Tech CS Research</div>
          </div>
        </div>
      </div>
    </header>
  );
};

