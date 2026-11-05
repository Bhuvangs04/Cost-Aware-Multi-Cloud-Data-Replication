import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ReplicationPolicy } from '../types';
import {
  Sliders,
  DollarSign,
  ShieldCheck,
  Zap,
  Info,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';

export const ReplicationPolicies: React.FC = () => {
  const [policies, setPolicies] = useState<ReplicationPolicy[]>([]);
  const [activePolicy, setActivePolicy] = useState<ReplicationPolicy | null>(null);
  const [loading, setLoading] = useState(true);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Form states for active policy
  const [strategyType, setStrategyType] = useState<'FULL' | 'PRIORITY' | 'COST_AWARE_ADAPTIVE'>('COST_AWARE_ADAPTIVE');
  const [targetRpo, setTargetRpo] = useState(3600);
  const [targetRto, setTargetRto] = useState(300);
  const [maxBudget, setMaxBudget] = useState(150.0);
  const [thresholdScore, setThresholdScore] = useState(0.5);

  // Weight sliders
  const [wp, setWp] = useState(0.35);
  const [wa, setWa] = useState(0.25);
  const [wr, setWr] = useState(0.15);
  const [ws, setWs] = useState(0.15);
  const [wc, setWc] = useState(0.10);

  const fetchPolicies = async () => {
    setLoading(true);
    try {
      const data = await api.getPolicies();
      setPolicies(data);
      const active = data.find((p) => p.is_active) || data[0];
      if (active) {
        setActivePolicy(active);
        setStrategyType(active.strategy_type);
        setTargetRpo(active.target_rpo_seconds);
        setTargetRto(active.target_rto_seconds);
        setMaxBudget(active.max_budget_monthly_usd);
        setThresholdScore(active.threshold_score);
        try {
          const weights = JSON.parse(active.weights_json);
          setWp(weights.w_priority ?? 0.35);
          setWa(weights.w_access ?? 0.25);
          setWr(weights.w_rpo ?? 0.15);
          setWs(weights.w_size ?? 0.15);
          setWc(weights.w_cost ?? 0.10);
        } catch {
          // keep defaults
        }
      }
    } catch (err) {
      console.error('Failed to load policies', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicies();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activePolicy) return;

    const updatedWeights = JSON.stringify({
      w_priority: wp,
      w_access: wa,
      w_rpo: wr,
      w_size: ws,
      w_cost: wc,
    });

    try {
      await api.updatePolicy(activePolicy.id, {
        name: activePolicy.name,
        strategy_type: strategyType,
        target_rpo_seconds: targetRpo,
        target_rto_seconds: targetRto,
        max_budget_monthly_usd: maxBudget,
        threshold_score: thresholdScore,
        weights_json: updatedWeights,
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      await fetchPolicies();
    } catch (err) {
      console.error('Failed to update policy', err);
    }
  };

  const sumWeights = (wp + wa + wr + ws + wc).toFixed(2);

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Replication Policies & Adaptive Algorithm Tuning
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Configure the objective scoring weights, budget constraints, and strategy engines governing AWS-to-GCP replication.
          </p>
        </div>
        <button
          onClick={fetchPolicies}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          Reload Policies
        </button>
      </div>

      {/* Mathematical Research Formulation Banner */}
      <div className="bg-[#111827] border border-cyan-500/30 rounded-xl p-6 shadow-xl relative overflow-hidden">
        <div className="flex items-start space-x-4">
          <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
            <Zap className="w-6 h-6" />
          </div>
          <div>
            <span className="text-[10px] uppercase font-mono tracking-wider text-cyan-400 font-bold">
              Research Objective Scoring Formulation
            </span>
            <h3 className="text-base font-bold text-white mt-0.5">
              Cost-Aware Adaptive Replication Function
            </h3>
            <div className="my-3 p-3 rounded-lg bg-[#0B0F19] border border-slate-800 font-mono text-cyan-300 text-xs md:text-sm">
              Φ(i) = w_p · P̂_i + w_a · Â_i + w_r · R̂_i + w_s · Ŝ_i - w_c · Ĉ_i
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Where <span className="text-slate-200 font-medium">P̂</span> is normalized priority tier, <span className="text-slate-200 font-medium">Â</span> is access frequency weight, <span className="text-slate-200 font-medium">R̂</span> is disaster recovery requirement, <span className="text-slate-200 font-medium">Ŝ</span> is file size value retention, and <span className="text-slate-200 font-medium">Ĉ</span> is cross-cloud egress and storage cost penalty.
            </p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSave} className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Strategy & Thresholds */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-[#111827] border border-slate-800 rounded-xl p-6 shadow-lg space-y-5">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Sliders className="w-4 h-4 text-cyan-400" />
              Engine Strategy Mode
            </h3>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-2">Replication Strategy</label>
              <div className="space-y-2">
                {[
                  { id: 'COST_AWARE_ADAPTIVE', name: 'Cost-Aware Adaptive (Research Engine)', desc: 'Scored evaluation with budget guardrails & Critical zero-RPO bypass.' },
                  { id: 'PRIORITY', name: 'Priority-Based Tiering', desc: 'Critical/High immediately replicated; Medium/Low filtered.' },
                  { id: 'FULL', name: 'Full Replication (Baseline)', desc: '100% of objects replicated regardless of cost or access pattern.' },
                ].map((s) => (
                  <label
                    key={s.id}
                    className={`block p-3 rounded-lg border cursor-pointer transition ${
                      strategyType === s.id
                        ? 'bg-cyan-500/10 border-cyan-500/40 text-white'
                        : 'bg-[#0B0F19] border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <input
                      type="radio"
                      name="strategy"
                      value={s.id}
                      checked={strategyType === s.id}
                      onChange={(e: any) => setStrategyType(e.target.value)}
                      className="hidden"
                    />
                    <div className="font-semibold text-xs text-slate-200">{s.name}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5 leading-snug">{s.desc}</div>
                  </label>
                ))}
              </div>
            </div>

            <div className="pt-2 border-t border-slate-800/80 space-y-4">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-300 font-medium">Threshold Score (θ)</span>
                  <span className="font-mono text-cyan-400 font-semibold">{thresholdScore.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="0.9"
                  step="0.05"
                  value={thresholdScore}
                  onChange={(e) => setThresholdScore(parseFloat(e.target.value))}
                  className="w-full accent-cyan-500"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>Aggressive (0.1)</span>
                  <span>Conservative (0.9)</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Monthly Budget Cap ($ USD)</label>
                <div className="relative">
                  <DollarSign className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type="number"
                    value={maxBudget}
                    onChange={(e) => setMaxBudget(parseFloat(e.target.value))}
                    className="w-full bg-[#0B0F19] border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Target RPO (s)</label>
                  <input
                    type="number"
                    value={targetRpo}
                    onChange={(e) => setTargetRpo(parseInt(e.target.value))}
                    className="w-full bg-[#0B0F19] border border-slate-800 rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Target RTO (s)</label>
                  <input
                    type="number"
                    value={targetRto}
                    onChange={(e) => setTargetRto(parseInt(e.target.value))}
                    className="w-full bg-[#0B0F19] border border-slate-800 rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Scoring Weights Tuning */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-[#111827] border border-slate-800 rounded-xl p-6 shadow-lg space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Adaptive Parameter Weights (Σ = {sumWeights})
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Tune individual feature influences. The engine automatically normalizes values during scoring.
                </p>
              </div>
              <span className={`px-2.5 py-1 rounded-full text-xs font-mono font-bold ${
                sumWeights === '1.00'
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
              }`}>
                Σ w = {sumWeights}
              </span>
            </div>

            <div className="space-y-5">
              {/* w_p */}
              <div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-slate-200 font-semibold flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-400" />
                    Priority Tier Weight (w_p)
                  </span>
                  <span className="font-mono text-cyan-400 font-bold">{wp.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={wp}
                  onChange={(e) => setWp(parseFloat(e.target.value))}
                  className="w-full accent-cyan-500"
                />
                <p className="text-[11px] text-slate-500">
                  Impact of file criticality: CRITICAL (1.0), HIGH (0.75), MEDIUM (0.5), LOW (0.2).
                </p>
              </div>

              {/* w_a */}
              <div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-slate-200 font-semibold flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-blue-400" />
                    Access Frequency Weight (w_a)
                  </span>
                  <span className="font-mono text-cyan-400 font-bold">{wa.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={wa}
                  onChange={(e) => setWa(parseFloat(e.target.value))}
                  className="w-full accent-cyan-500"
                />
                <p className="text-[11px] text-slate-500">
                  Value placed on read frequency: FREQUENT (1.0), INFREQUENT (0.5), ARCHIVE (0.1).
                </p>
              </div>

              {/* w_r */}
              <div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-slate-200 font-semibold flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
                    RPO Recovery Requirement Weight (w_r)
                  </span>
                  <span className="font-mono text-cyan-400 font-bold">{wr.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={wr}
                  onChange={(e) => setWr(parseFloat(e.target.value))}
                  className="w-full accent-cyan-500"
                />
                <p className="text-[11px] text-slate-500">
                  Tolerable data loss objective: Stricter RPO demands higher replication priority.
                </p>
              </div>

              {/* w_s */}
              <div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-slate-200 font-semibold flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-purple-400" />
                    File Size Retention Weight (w_s)
                  </span>
                  <span className="font-mono text-cyan-400 font-bold">{ws.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={ws}
                  onChange={(e) => setWs(parseFloat(e.target.value))}
                  className="w-full accent-cyan-500"
                />
                <p className="text-[11px] text-slate-500">
                  Favors replicating high-value compact objects over massive single payloads.
                </p>
              </div>

              {/* w_c */}
              <div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-slate-200 font-semibold flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                    Cross-Cloud Cost Penalty Weight (w_c)
                  </span>
                  <span className="font-mono text-cyan-400 font-bold">{wc.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={wc}
                  onChange={(e) => setWc(parseFloat(e.target.value))}
                  className="w-full accent-cyan-500"
                />
                <p className="text-[11px] text-slate-500">
                  Negative penalty deducted from score based on estimated egress and secondary storage fee.
                </p>
              </div>
            </div>

            {saveSuccess && (
              <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" />
                <span>Policy parameters saved and applied to replication worker pipeline!</span>
              </div>
            )}

            <div className="pt-4 border-t border-slate-800 flex justify-end">
              <button
                type="submit"
                className="px-6 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-lg shadow-lg shadow-cyan-600/20 transition flex items-center gap-2"
              >
                <ShieldCheck className="w-4 h-4" />
                Save & Apply Policy
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
};

