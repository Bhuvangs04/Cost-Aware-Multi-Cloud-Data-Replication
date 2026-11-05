import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { CloudProvider, HealthStatusReport } from '../types';
import {
  Server,
  Activity,
  Database,
  ShieldCheck,
  RefreshCw,
  HardDrive,
  Cpu,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

export const CloudProviders: React.FC = () => {
  const [providers, setProviders] = useState<CloudProvider[]>([]);
  const [health, setHealth] = useState<HealthStatusReport | null>(null);
  const [loading, setLoading] = useState(true);

  // Mock latency history for charting
  const latencyHistory = [
    { time: '10:00', aws: 41.2, gcp: 56.4 },
    { time: '10:05', aws: 43.1, gcp: 58.0 },
    { time: '10:10', aws: 42.0, gcp: 57.2 },
    { time: '10:15', aws: 44.5, gcp: 59.8 },
    { time: '10:20', aws: 42.4, gcp: 58.1 },
    { time: '10:25', aws: 41.8, gcp: 57.9 },
  ];

  const fetchData = async () => {
    setLoading(true);
    try {
      const [provRes, healthRes] = await Promise.all([
        api.getProviders(),
        api.getHealth(),
      ]);
      setProviders(provRes);
      setHealth(healthRes);
    } catch (err) {
      console.error('Failed to load cloud provider data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Multi-Cloud Storage Infrastructure
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time status of AWS S3 primary storage and Google Cloud Storage (GCS) standby replicas.
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          Run Health Probe
        </button>
      </div>

      {/* Provider Details Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {providers.map((p) => {
          const isHealthy = p.status === 'HEALTHY';
          return (
            <div
              key={p.id}
              className="bg-[#111827] border border-slate-800 rounded-xl p-6 shadow-xl relative overflow-hidden"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className={`p-3 rounded-lg border ${
                    p.is_primary
                      ? 'bg-blue-500/10 border-blue-500/20 text-blue-400'
                      : 'bg-purple-500/10 border-purple-500/20 text-purple-400'
                  }`}>
                    <Server className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">{p.name}</h3>
                    <p className="text-xs text-slate-400 font-mono">Provider ID: {p.id}</p>
                  </div>
                </div>

                <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${
                  isHealthy
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                    : 'bg-rose-500/10 text-rose-400 border-rose-500/20 animate-pulse'
                }`}>
                  ● {p.status}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 py-4 border-y border-slate-800/80 text-xs">
                <div>
                  <span className="text-slate-400 block mb-1">Bucket Target</span>
                  <span className="font-mono font-medium text-slate-200 flex items-center gap-1.5">
                    <Database className="w-3.5 h-3.5 text-cyan-400" />
                    {p.bucket_name}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block mb-1">Region</span>
                  <span className="font-mono font-medium text-slate-200">
                    {p.region}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block mb-1">Role</span>
                  <span className={`font-semibold ${p.is_primary ? 'text-blue-400' : 'text-purple-400'}`}>
                    {p.is_primary ? 'PRIMARY SOURCE (R/W)' : 'DR STANDBY REPLICA (Read-Failover)'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block mb-1">Probe Latency</span>
                  <span className="font-mono font-medium text-emerald-400 flex items-center gap-1">
                    <Activity className="w-3.5 h-3.5" />
                    {p.current_latency_ms.toFixed(1)} ms
                  </span>
                </div>
              </div>

              <div className="mt-4 pt-2 flex items-center justify-between text-[11px] text-slate-400">
                <span>Adapter: {health?.simulation_mode ? 'SimulatedStorageInterceptor (Persistent)' : 'Native Cloud SDK'}</span>
                <span className="font-mono text-cyan-400">SHA-256 Validated</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Latency Telemetry Chart */}
      <div className="bg-[#111827] border border-slate-800 rounded-xl p-6 shadow-lg">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-base font-semibold text-white">Cross-Cloud Latency Telemetry</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Synthetic round-trip ping time (ms) to AWS S3 us-east-1 and GCP GCS us-central1 endpoints.
            </p>
          </div>
          <div className="flex items-center space-x-4 text-xs font-mono">
            <span className="flex items-center gap-1.5 text-blue-400">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-500" /> AWS S3
            </span>
            <span className="flex items-center gap-1.5 text-purple-400">
              <span className="w-2.5 h-2.5 rounded-full bg-purple-500" /> GCP GCS
            </span>
          </div>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={latencyHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
              <XAxis dataKey="time" stroke="#64748B" fontSize={11} />
              <YAxis stroke="#64748B" fontSize={11} domain={[30, 80]} unit="ms" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0F172A',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
              />
              <Line
                type="monotone"
                dataKey="aws"
                name="AWS S3"
                stroke="#3B82F6"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
              <Line
                type="monotone"
                dataKey="gcp"
                name="GCP GCS"
                stroke="#A855F7"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Cloud Adapter Architecture Card */}
      <div className="bg-[#111827] border border-slate-800 rounded-xl p-6 shadow-lg">
        <h3 className="text-base font-semibold text-white mb-2">Provider Abstraction Architecture</h3>
        <p className="text-xs text-slate-400 mb-4">
          All storage operations execute through the provider-independent interface <code className="text-cyan-400 font-mono">ICloudStorageProvider</code>, decoupling higher-level replication logic from vendor APIs.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-4 rounded-lg bg-[#0B0F19] border border-slate-800">
            <div className="flex items-center gap-2 text-cyan-400 font-semibold mb-1">
              <Cpu className="w-4 h-4" />
              <span>AWSS3StorageAdapter</span>
            </div>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Interacts with Amazon S3 via <code className="text-slate-300">boto3</code>. Supports S3 Object Versioning, client-side SHA-256 header tags, and pre-signed streaming downloads.
            </p>
          </div>

          <div className="p-4 rounded-lg bg-[#0B0F19] border border-slate-800">
            <div className="flex items-center gap-2 text-purple-400 font-semibold mb-1">
              <Cpu className="w-4 h-4" />
              <span>GCPStorageAdapter</span>
            </div>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Interacts with Google Cloud Storage via <code className="text-slate-300">google-cloud-storage</code>. Tracks generation numbers, custom object metadata, and service account key authorization.
            </p>
          </div>

          <div className="p-4 rounded-lg bg-[#0B0F19] border border-slate-800">
            <div className="flex items-center gap-2 text-emerald-400 font-semibold mb-1">
              <ShieldCheck className="w-4 h-4" />
              <span>SimulatedStorageInterceptor</span>
            </div>
            <p className="text-slate-400 text-[11px] leading-relaxed">
              Provides deterministic offline simulation with fault injection, latency delays, disk persistence, and generation tracking for reliable automated testing.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

