import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { CostSummary } from '../types';
import {
  DollarSign,
  TrendingDown,
  PieChart as PieIcon,
  HardDrive,
  ArrowRight,
  Calculator,
  RefreshCw,
  Info,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  AreaChart,
  Area,
} from 'recharts';

export const CostAnalytics: React.FC = () => {
  const [costSummary, setCostSummary] = useState<CostSummary | null>(null);
  const [loading, setLoading] = useState(true);

  // Estimator calculator state
  const [estFileSizeMB, setEstFileSizeMB] = useState(100);
  const [estPriority, setEstPriority] = useState<'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'>('MEDIUM');
  const [estAccessTier, setEstAccessTier] = useState<'FREQUENT' | 'INFREQUENT' | 'ARCHIVE'>('FREQUENT');
  const [estMonths, setEstMonths] = useState(6);

  const fetchCostData = async () => {
    setLoading(true);
    try {
      const data = await api.getCostSummary();
      setCostSummary(data);
    } catch (err) {
      console.error('Failed to load cost data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCostData();
  }, []);

  const formatCurrency = (val?: number) => {
    if (val === undefined || val === null) return '$0.00';
    if (val > 0 && val < 0.01) return `$${val.toFixed(5)}`;
    return `$${val.toFixed(2)}`;
  };

  // Breakdown chart data
  const costBreakdownData = [
    {
      category: 'AWS S3 Primary Storage',
      amount: costSummary ? costSummary.total_aws_storage_usd : 0,
      color: '#3B82F6',
    },
    {
      category: 'GCP GCS Standby Storage',
      amount: costSummary ? costSummary.total_gcp_storage_usd : 0,
      color: '#A855F7',
    },
    {
      category: 'Cross-Cloud Egress Transfer',
      amount: costSummary ? costSummary.total_egress_transfer_usd : 0,
      color: '#F59E0B',
    },
    {
      category: 'Replication API Operations',
      amount: costSummary ? costSummary.total_replication_ops_usd : 0,
      color: '#10B981',
    },
  ];

  // Cumulative savings timeline comparison
  const monthlyAdaptive = costSummary?.total_cost_current_strategy_usd || 0;
  const monthlyBaseline = costSummary?.baseline_full_replication_cost_usd || 0;
  const monthlySavings = costSummary?.net_savings_usd || 0;

  const cumulativeSavingsData = [1, 2, 3, 4, 5, 6].map((m) => ({
    month: `Month ${m}`,
    fullReplication: Number((monthlyBaseline * m).toFixed(4)),
    costAwareAdaptive: Number((monthlyAdaptive * m).toFixed(4)),
    cumulativeSavings: Number((monthlySavings * m).toFixed(4)),
  }));

  // Quick client-side estimation calculation based on pricing constants
  const sizeGB = estFileSizeMB / 1024;
  const awsRate = 0.023;
  const gcpRate = 0.020;
  const egressRate = 0.090;

  const estAwsStorage = sizeGB * awsRate * estMonths;
  const estGcpStorageFull = sizeGB * gcpRate * estMonths;
  const estEgressFull = sizeGB * egressRate;
  const estFullTotal = estAwsStorage + estGcpStorageFull + estEgressFull;

  // Adaptive replicates 100% of critical, 75% high, 40% medium, 10% low
  const priorityReplicationChance: Record<string, number> = {
    CRITICAL: 1.0,
    HIGH: 0.75,
    MEDIUM: 0.40,
    LOW: 0.10,
  };
  const factor = priorityReplicationChance[estPriority];
  const estAdaptiveGcpStorage = estGcpStorageFull * factor;
  const estAdaptiveEgress = estEgressFull * factor;
  const estAdaptiveTotal = estAwsStorage + estAdaptiveGcpStorage + estAdaptiveEgress;
  const estSavings = estFullTotal - estAdaptiveTotal;
  const estSavingsPercent = estFullTotal > 0 ? (estSavings / estFullTotal) * 100 : 0;

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Cost Analytics & Budget Optimization
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Auditing cross-cloud data egress fees, dual-provider storage expenses, and experimental savings vs. full replication baseline.
          </p>
        </div>
        <button
          onClick={fetchCostData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          Recalculate Costs
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#111827] border border-slate-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Adaptive Strategy Cost</span>
            <span className="p-2 rounded bg-cyan-500/10 text-cyan-400">
              <DollarSign className="w-4 h-4" />
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {formatCurrency(costSummary?.total_cost_current_strategy_usd)}
          </div>
          <div className="mt-2 text-[11px] text-slate-400 font-mono">
            Current monthly spend
          </div>
        </div>

        <div className="bg-[#111827] border border-slate-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Baseline Full Replication</span>
            <span className="p-2 rounded bg-slate-800 text-slate-400">
              <HardDrive className="w-4 h-4" />
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-slate-300">
            {formatCurrency(costSummary?.baseline_full_replication_cost_usd)}
          </div>
          <div className="mt-2 text-[11px] text-slate-400 font-mono">
            If 100% files replicated
          </div>
        </div>

        <div className="bg-[#111827] border border-emerald-500/30 rounded-xl p-5 shadow-lg bg-emerald-950/10">
          <div className="flex items-center justify-between text-xs text-emerald-400 mb-2">
            <span>Net Monthly Savings</span>
            <span className="p-2 rounded bg-emerald-500/10 text-emerald-400">
              <TrendingDown className="w-4 h-4" />
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400">
            {formatCurrency(costSummary?.net_savings_usd)}
          </div>
          <div className="mt-2 text-[11px] text-emerald-400/80 font-mono">
            {costSummary ? costSummary.net_savings_percentage.toFixed(1) : '0.0'}% reduction
          </div>
        </div>

        <div className="bg-[#111827] border border-slate-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Monthly Budget Usage</span>
            <span className="p-2 rounded bg-slate-800 text-cyan-400">
              <PieIcon className="w-4 h-4" />
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {costSummary ? costSummary.budget_utilized_percent.toFixed(2) : '0.00'}%
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full mt-3 overflow-hidden">
            <div
              className="bg-cyan-500 h-full rounded-full transition-all duration-500"
              style={{ width: `${Math.min(costSummary?.budget_utilized_percent || 0, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cost Breakdown */}
        <div className="bg-[#111827] border border-slate-800 rounded-xl p-6 shadow-lg">
          <h3 className="text-base font-semibold text-white mb-1">Spend Breakdown by Resource</h3>
          <p className="text-xs text-slate-400 mb-4">Distribution across cloud storage, egress transfer, and worker operations.</p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={costBreakdownData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" horizontal={false} />
                <XAxis type="number" stroke="#64748B" fontSize={11} unit="$" />
                <YAxis dataKey="category" type="category" stroke="#64748B" fontSize={10} width={130} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0F172A',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  formatter={(value: any) => [`$${Number(value).toFixed(2)}`, 'Cost (USD)']}
                />
                <Bar dataKey="amount" fill="#06B6D4" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Cumulative Savings Timeline */}
        <div className="bg-[#111827] border border-slate-800 rounded-xl p-6 shadow-lg">
          <h3 className="text-base font-semibold text-white mb-1">Cumulative Cost Comparison Over Time</h3>
          <p className="text-xs text-slate-400 mb-4">Projected 6-month growth: Full Replication vs. Cost-Aware Adaptive.</p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={cumulativeSavingsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                <XAxis dataKey="month" stroke="#64748B" fontSize={11} />
                <YAxis stroke="#64748B" fontSize={11} unit="$" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0F172A',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  formatter={(val: any) => [`$${Number(val).toFixed(2)}`, '']}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                <Area
                  type="monotone"
                  dataKey="fullReplication"
                  name="Full Replication Baseline ($)"
                  stroke="#64748B"
                  fill="#334155"
                  fillOpacity={0.2}
                />
                <Area
                  type="monotone"
                  dataKey="costAwareAdaptive"
                  name="Cost-Aware Adaptive ($)"
                  stroke="#06B6D4"
                  fill="#06B6D4"
                  fillOpacity={0.2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Interactive Cost Estimator Sandbox */}
      <div className="bg-[#111827] border border-slate-800 rounded-xl p-6 shadow-xl">
        <div className="flex items-center space-x-3 mb-4">
          <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
            <Calculator className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">Interactive Cost & Savings Estimator</h3>
            <p className="text-xs text-slate-400">
              Simulate replication costs before ingest based on configurable pricing tables.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 p-4 rounded-xl bg-[#0B0F19] border border-slate-800 text-xs">
          <div>
            <label className="block text-slate-300 font-medium mb-1">Payload Size (MB)</label>
            <input
              type="number"
              min="1"
              value={estFileSizeMB}
              onChange={(e) => setEstFileSizeMB(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-full bg-[#111827] border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div>
            <label className="block text-slate-300 font-medium mb-1">File Priority Tier</label>
            <select
              value={estPriority}
              onChange={(e: any) => setEstPriority(e.target.value)}
              className="w-full bg-[#111827] border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
            >
              <option value="CRITICAL">CRITICAL (Replicate 100%)</option>
              <option value="HIGH">HIGH (Replicate ~75%)</option>
              <option value="MEDIUM">MEDIUM (Adaptive ~40%)</option>
              <option value="LOW">LOW (Conservative ~10%)</option>
            </select>
          </div>

          <div>
            <label className="block text-slate-300 font-medium mb-1">Access Frequency</label>
            <select
              value={estAccessTier}
              onChange={(e: any) => setEstAccessTier(e.target.value)}
              className="w-full bg-[#111827] border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
            >
              <option value="FREQUENT">FREQUENT</option>
              <option value="INFREQUENT">INFREQUENT</option>
              <option value="ARCHIVE">ARCHIVE</option>
            </select>
          </div>

          <div>
            <label className="block text-slate-300 font-medium mb-1">Retention Window (Months)</label>
            <input
              type="number"
              min="1"
              max="60"
              value={estMonths}
              onChange={(e) => setEstMonths(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-full bg-[#111827] border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>

        {/* Calculation Result Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4 pt-4 border-t border-slate-800 text-xs">
          <div className="p-3 rounded-lg bg-[#0B0F19] border border-slate-800">
            <span className="text-slate-400 block mb-1">Baseline Full Replication Cost</span>
            <span className="text-base font-bold font-mono text-slate-200">
              ${estFullTotal.toFixed(4)}
            </span>
            <span className="text-[10px] text-slate-500 block mt-0.5 font-mono">
              (Includes ${estEgressFull.toFixed(4)} egress + dual storage)
            </span>
          </div>

          <div className="p-3 rounded-lg bg-[#0B0F19] border border-slate-800">
            <span className="text-slate-400 block mb-1">Adaptive Strategy Cost</span>
            <span className="text-base font-bold font-mono text-cyan-400">
              ${estAdaptiveTotal.toFixed(4)}
            </span>
            <span className="text-[10px] text-slate-500 block mt-0.5 font-mono">
              (Includes adaptive filtering factor: {(factor * 100).toFixed(0)}%)
            </span>
          </div>

          <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/30">
            <span className="text-emerald-400 font-medium block mb-1">Net Estimated Savings</span>
            <span className="text-base font-bold font-mono text-emerald-400">
              ${estSavings.toFixed(4)} ({estSavingsPercent.toFixed(1)}%)
            </span>
            <span className="text-[10px] text-emerald-400/70 block mt-0.5 font-mono">
              Preserves egress & replication budget
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

