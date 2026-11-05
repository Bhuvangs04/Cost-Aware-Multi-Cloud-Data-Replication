import React from 'react';
import { CloudProvider } from '../types';
import { Activity, Server } from 'lucide-react';

interface HealthIndicatorProps {
  provider: CloudProvider;
  isFailoverActive?: boolean;
}

export const HealthIndicator: React.FC<HealthIndicatorProps> = ({
  provider,
  isFailoverActive,
}) => {
  const isHealthy = provider.status === 'HEALTHY';
  const isDegraded = provider.status === 'DEGRADED';
  const isOutage = provider.status === 'OUTAGE';

  return (
    <div className={`p-4 rounded-xl border transition-all ${
      isOutage
        ? 'bg-rose-950/20 border-rose-900/40'
        : isDegraded
        ? 'bg-amber-950/20 border-amber-900/40'
        : 'bg-[#111827] border-slate-800'
    }`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-slate-800 border border-slate-700">
            <Server className={`w-5 h-5 ${isHealthy ? 'text-cyan-400' : isDegraded ? 'text-amber-400' : 'text-rose-400'}`} />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white flex items-center gap-2">
              {provider.name}
              {provider.is_primary && (
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  Primary Source
                </span>
              )}
              {!provider.is_primary && (
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  DR Standby Replica
                </span>
              )}
            </h4>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Bucket: {provider.bucket_name} ({provider.region})
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${
            isHealthy
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : isDegraded
              ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
              : 'bg-rose-500/10 text-rose-400 border border-rose-500/20 animate-pulse'
          }`}>
            <span className={`w-2 h-2 rounded-full mr-1.5 ${
              isHealthy ? 'bg-emerald-400' : isDegraded ? 'bg-amber-400' : 'bg-rose-400'
            }`} />
            {provider.status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 pt-3 border-t border-slate-800/60 text-xs">
        <div>
          <span className="text-slate-400 block mb-0.5">Response Latency</span>
          <span className="font-mono font-medium text-slate-200 flex items-center gap-1">
            <Activity className="w-3.5 h-3.5 text-slate-400" />
            {provider.current_latency_ms.toFixed(1)} ms
          </span>
        </div>
        <div>
          <span className="text-slate-400 block mb-0.5">Failover Routing</span>
          <span className={`font-medium ${
            provider.is_primary
              ? isFailoverActive ? 'text-rose-400 font-semibold' : 'text-emerald-400'
              : isFailoverActive ? 'text-amber-400 font-semibold animate-pulse' : 'text-slate-400'
          }`}>
            {provider.is_primary
              ? (isFailoverActive ? 'OFFLINE (Rerouted)' : 'ACTIVE (Primary Reads)')
              : (isFailoverActive ? 'SERVING FAILOVER READS' : 'HOT STANDBY')}
          </span>
        </div>
      </div>
    </div>
  );
};

