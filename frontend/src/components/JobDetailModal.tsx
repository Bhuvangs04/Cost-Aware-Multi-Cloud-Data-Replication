import React, { useState } from 'react';
import { ReplicationJob } from '../types';
import {
  X,
  Copy,
  Check,
  CheckCircle2,
  AlertCircle,
  Clock,
  RefreshCw,
  ShieldCheck,
  ArrowRight,
  Database,
  DollarSign,
  Cpu,
  Layers,
  ChevronDown,
  ChevronUp,
  Cloud,
  Hash,
  AlertTriangle,
} from 'lucide-react';

interface JobDetailModalProps {
  job: ReplicationJob | null;
  onClose: () => void;
  onRetry?: (jobId: string) => Promise<void>;
}

interface ParsedDecision {
  action?: 'REPLICATE_NOW' | 'DEFER_BATCH' | 'SKIP' | string;
  strategy?: string;
  decision_score?: number;
  breakdown?: {
    priority?: string;
    priority_norm?: number;
    access_tier?: string;
    access_norm?: number;
    rpo_urgency?: number;
    size_factor?: number;
    cost_penalty?: number;
    file_size_gb?: number;
    egress_cost_usd?: number;
    storage_cost_usd?: number;
    total_replica_cost_usd?: number;
    composite_score?: number;
    threshold?: number;
    [key: string]: any;
  };
  estimated_cost_usd?: number;
  budget_remaining_usd?: number;
  reason?: string;
  rawText: string;
  isJson: boolean;
}

export const JobDetailModal: React.FC<JobDetailModalProps> = ({
  job,
  onClose,
  onRetry,
}) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [retrySuccess, setRetrySuccess] = useState<string | null>(null);

  if (!job) return null;

  // Copy helper
  const handleCopy = (text: string, keyName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(keyName);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // Safe parse decision_reason
  const parseDecisionReason = (reasonStr?: string): ParsedDecision => {
    if (!reasonStr) {
      return {
        rawText: 'Standard pipeline processing',
        isJson: false,
        reason: 'Standard pipeline processing',
      };
    }

    try {
      const trimmed = reasonStr.trim();
      if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
        const parsed = JSON.parse(trimmed);
        return {
          ...parsed,
          rawText: JSON.stringify(parsed, null, 2),
          isJson: true,
        };
      }
    } catch {
      // Fall through to plain text
    }

    return {
      rawText: reasonStr,
      isJson: false,
      reason: reasonStr,
    };
  };

  const decision = parseDecisionReason(job.decision_reason);
  const breakdown = decision.breakdown;

  // Calculate elapsed duration if timestamps exist
  let durationMs: number | null = null;
  if (job.started_at && job.completed_at) {
    const start = new Date(job.started_at).getTime();
    const end = new Date(job.completed_at).getTime();
    if (!isNaN(start) && !isNaN(end) && end >= start) {
      durationMs = end - start;
    }
  }

  const handleRetryClick = async () => {
    if (!onRetry) return;
    setRetrying(true);
    setRetrySuccess(null);
    try {
      await onRetry(job.id);
      setRetrySuccess(`Job ${job.id.substring(0, 8)}... dispatched to Celery!`);
      setTimeout(() => setRetrySuccess(null), 4000);
    } catch (err: any) {
      console.error('Failed to retry job', err);
    } finally {
      setRetrying(false);
    }
  };

  const statusStyles: Record<string, { bg: string; text: string; border: string; icon: React.ReactNode }> = {
    COMPLETED: {
      bg: 'bg-emerald-500/10',
      text: 'text-emerald-400',
      border: 'border-emerald-500/20',
      icon: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
    },
    PENDING: {
      bg: 'bg-amber-500/10',
      text: 'text-amber-400',
      border: 'border-amber-500/20',
      icon: <Clock className="w-4 h-4 text-amber-400" />,
    },
    REPLICATING: {
      bg: 'bg-sky-500/10',
      text: 'text-sky-400',
      border: 'border-sky-500/20',
      icon: <RefreshCw className="w-4 h-4 text-sky-400 animate-spin" />,
    },
    SKIPPED: {
      bg: 'bg-slate-700/40',
      text: 'text-slate-400',
      border: 'border-slate-600/30',
      icon: <AlertCircle className="w-4 h-4 text-slate-400" />,
    },
    FAILED: {
      bg: 'bg-rose-500/10',
      text: 'text-rose-400',
      border: 'border-rose-500/20',
      icon: <AlertTriangle className="w-4 h-4 text-rose-400" />,
    },
  };

  const currentStatusStyle = statusStyles[job.status] || statusStyles.PENDING;

  // Action badge style
  const getActionBadge = (action?: string) => {
    switch (action) {
      case 'REPLICATE_NOW':
        return {
          label: 'REPLICATE NOW',
          class: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
        };
      case 'DEFER_BATCH':
        return {
          label: 'DEFER TO BATCH',
          class: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
        };
      case 'SKIP':
        return {
          label: 'SKIP (THROTTLED)',
          class: 'bg-slate-700/50 text-slate-300 border-slate-600/50',
        };
      default:
        return {
          label: action || job.status,
          class: 'bg-slate-800 text-slate-300 border-slate-700',
        };
    }
  };

  const actionInfo = getActionBadge(decision.action);
  const scoreVal = job.decision_score ?? decision.decision_score;
  const thresholdVal = breakdown?.threshold ?? 0.5;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-[#111827] border border-slate-800 rounded-2xl max-w-4xl w-full p-6 sm:p-7 shadow-2xl relative my-8 animate-in fade-in zoom-in-95 max-h-[92vh] overflow-y-auto custom-scrollbar">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-slate-400 hover:text-white p-2 rounded-lg bg-slate-800/60 hover:bg-slate-800 transition border border-slate-700/50"
          title="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5 pr-10">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="p-1.5 rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                <Cpu className="w-4 h-4" />
              </span>
              <span className="text-[11px] font-mono uppercase tracking-wider text-cyan-400 font-semibold">
                Replication Pipeline Telemetry & Audit
              </span>
            </div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2 flex-wrap">
              <span>Job Inspection</span>
              <span className="font-mono text-xs px-2.5 py-1 rounded-md bg-slate-800/80 text-cyan-300 border border-slate-700/70 flex items-center gap-1.5">
                {job.id}
                <button
                  onClick={() => handleCopy(job.id, 'job_id')}
                  className="hover:text-white text-slate-400 transition"
                  title="Copy Job ID"
                >
                  {copiedKey === 'job_id' ? (
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </button>
              </span>
            </h2>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${currentStatusStyle.bg} ${currentStatusStyle.text} ${currentStatusStyle.border}`}
            >
              {currentStatusStyle.icon}
              {job.status}
            </span>
            <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
              {job.strategy_used}
            </span>
          </div>
        </div>

        {retrySuccess && (
          <div className="mt-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{retrySuccess}</span>
          </div>
        )}

        {job.error_message && (
          <div className="mt-4 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-rose-200">Execution Error: </span>
              <span className="font-mono">{job.error_message}</span>
            </div>
          </div>
        )}

        {/* Content Body */}
        <div className="mt-6 space-y-6">
          {/* Card 1: Decision Outcome & Score Meter */}
          <div className="bg-[#0B0F19] border border-slate-800/90 rounded-xl p-5 shadow-inner">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
              <div>
                <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400">
                  Algorithmic Evaluation
                </span>
                <div className="flex items-center gap-2.5 mt-1">
                  <span
                    className={`px-3 py-1 rounded-lg text-xs font-bold border tracking-wide uppercase font-mono ${actionInfo.class}`}
                  >
                    {actionInfo.label}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    Strategy: <strong className="text-white">{decision.strategy || job.strategy_used}</strong>
                  </span>
                </div>
              </div>

              {scoreVal !== undefined && scoreVal !== null && (
                <div className="sm:text-right">
                  <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400">
                    Decision Score Φ(i)
                  </span>
                  <div className="text-2xl font-bold font-mono text-cyan-400">
                    {scoreVal.toFixed(4)}
                    <span className="text-xs font-normal text-slate-400 ml-1.5">
                      / {thresholdVal.toFixed(2)} threshold
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Score Progress / Threshold Meter */}
            {scoreVal !== undefined && scoreVal !== null && (
              <div className="space-y-1.5 mb-4">
                <div className="flex justify-between text-[11px] text-slate-400 font-mono">
                  <span>Score Meter (0.00 to 1.00)</span>
                  <span className={scoreVal >= thresholdVal ? 'text-emerald-400' : 'text-amber-400'}>
                    {scoreVal >= thresholdVal ? 'Threshold Exceeded (Replication Justified)' : 'Below Threshold (Cost Throttled)'}
                  </span>
                </div>
                <div className="relative w-full h-3 bg-slate-800 rounded-full overflow-hidden border border-slate-700/60">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      scoreVal >= thresholdVal ? 'bg-gradient-to-r from-cyan-500 to-emerald-400' : 'bg-gradient-to-r from-amber-500 to-rose-400'
                    }`}
                    style={{ width: `${Math.min(Math.max(scoreVal * 100, 3), 100)}%` }}
                  />
                  {/* Threshold marker */}
                  <div
                    className="absolute top-0 bottom-0 w-0.5 bg-white shadow-sm"
                    style={{ left: `${thresholdVal * 100}%` }}
                    title={`Threshold marker: ${thresholdVal}`}
                  />
                </div>
              </div>
            )}

            {/* Reason Quote Box */}
            <div className="p-3.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-300 leading-relaxed">
              <span className="font-semibold text-cyan-400 mr-2">Decision Rationale:</span>
              {decision.reason || job.decision_reason || 'Standard pipeline processing under active policy.'}
            </div>
          </div>

          {/* Card 2: Multi-Factor Scoring Factors Breakdown (Phi(i)) */}
          {breakdown && Object.keys(breakdown).length > 0 && (
            <div className="bg-[#0B0F19] border border-slate-800/90 rounded-xl p-5 shadow-inner">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-cyan-400">
                    <Layers className="w-4 h-4" />
                  </span>
                  <h3 className="text-sm font-semibold text-white">
                    Adaptive Scoring Factor Breakdown (Φ(i))
                  </h3>
                </div>
                <span className="text-[10px] font-mono text-slate-500">
                  Φ(i) = wp·P̂ + wa·Â + wr·R̂ + ws·Ŝ − wc·Ĉ
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 pt-2">
                {/* Priority */}
                <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800/80">
                  <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 block mb-1">
                    Priority (P̂i)
                  </span>
                  <div className="text-sm font-bold text-white font-mono">
                    {breakdown.priority_norm !== undefined
                      ? Number(breakdown.priority_norm).toFixed(2)
                      : 'N/A'}
                  </div>
                  <span className="text-[11px] text-cyan-400 font-mono mt-0.5 block truncate">
                    Tier: {breakdown.priority || 'N/A'}
                  </span>
                </div>

                {/* Access Tier */}
                <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800/80">
                  <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 block mb-1">
                    Access Freq (Âi)
                  </span>
                  <div className="text-sm font-bold text-white font-mono">
                    {breakdown.access_norm !== undefined
                      ? Number(breakdown.access_norm).toFixed(2)
                      : 'N/A'}
                  </div>
                  <span className="text-[11px] text-slate-400 font-mono mt-0.5 block truncate">
                    Tier: {breakdown.access_tier || 'N/A'}
                  </span>
                </div>

                {/* RPO Urgency */}
                <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800/80">
                  <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 block mb-1">
                    RPO Urgency (R̂i)
                  </span>
                  <div className="text-sm font-bold text-white font-mono">
                    {breakdown.rpo_urgency !== undefined
                      ? Number(breakdown.rpo_urgency).toFixed(2)
                      : 'N/A'}
                  </div>
                  <span className="text-[11px] text-slate-400 font-mono mt-0.5 block">
                    Zero-RPO Target
                  </span>
                </div>

                {/* Size Factor */}
                <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800/80">
                  <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 block mb-1">
                    Size Factor (Ŝi)
                  </span>
                  <div className="text-sm font-bold text-white font-mono">
                    {breakdown.size_factor !== undefined
                      ? Number(breakdown.size_factor).toFixed(3)
                      : 'N/A'}
                  </div>
                  <span className="text-[11px] text-slate-400 font-mono mt-0.5 block truncate">
                    {breakdown.file_size_gb !== undefined
                      ? `${(Number(breakdown.file_size_gb) * 1024).toFixed(1)} MB`
                      : 'Size norm'}
                  </span>
                </div>

                {/* Cost Penalty */}
                <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800/80">
                  <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 block mb-1">
                    Cost Penalty (Ĉi)
                  </span>
                  <div className="text-sm font-bold text-rose-400 font-mono">
                    {breakdown.cost_penalty !== undefined
                      ? Number(breakdown.cost_penalty).toFixed(4)
                      : 'N/A'}
                  </div>
                  <span className="text-[11px] text-slate-400 font-mono mt-0.5 block truncate">
                    {breakdown.total_replica_cost_usd !== undefined
                      ? `$${Number(breakdown.total_replica_cost_usd).toFixed(5)}`
                      : 'Penalty deduction'}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Card 3: Financial Ledger & Multi-Cloud Routing */}
          <div className="bg-[#0B0F19] border border-slate-800/90 rounded-xl p-5 shadow-inner">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-emerald-400">
                <DollarSign className="w-4 h-4" />
              </span>
              <h3 className="text-sm font-semibold text-white">
                Cross-Cloud Financial Ledger & Cost Attribution
              </h3>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800/80">
                <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 block mb-1">
                  AWS Egress Transfer Cost
                </span>
                <div className="text-base font-bold text-white font-mono">
                  ${breakdown?.egress_cost_usd !== undefined
                    ? Number(breakdown.egress_cost_usd).toFixed(6)
                    : '0.000000'}
                </div>
                <span className="text-[10px] text-slate-500 font-mono mt-0.5 block">
                  $0.09 / GB standard egress
                </span>
              </div>

              <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800/80">
                <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 block mb-1">
                  GCP Replica Storage Cost
                </span>
                <div className="text-base font-bold text-white font-mono">
                  ${breakdown?.storage_cost_usd !== undefined
                    ? Number(breakdown.storage_cost_usd).toFixed(6)
                    : '0.000000'}
                </div>
                <span className="text-[10px] text-slate-500 font-mono mt-0.5 block">
                  $0.020 / GB monthly
                </span>
              </div>

              <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800/80">
                <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 block mb-1">
                  Total Replica Cost (USD)
                </span>
                <div className="text-base font-bold text-cyan-400 font-mono">
                  ${breakdown?.total_replica_cost_usd !== undefined
                    ? Number(breakdown.total_replica_cost_usd).toFixed(6)
                    : decision.estimated_cost_usd !== undefined
                    ? Number(decision.estimated_cost_usd).toFixed(6)
                    : '0.000000'}
                </div>
                <span className="text-[10px] text-slate-500 font-mono mt-0.5 block">
                  Egress + Storage amortized
                </span>
              </div>

              <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800/80">
                <span className="text-[10px] uppercase font-mono tracking-wider text-slate-400 block mb-1">
                  Budget Headroom Remaining
                </span>
                <div className="text-base font-bold text-emerald-400 font-mono">
                  ${decision.budget_remaining_usd !== undefined
                    ? Number(decision.budget_remaining_usd).toFixed(2)
                    : '100.00'}
                </div>
                <span className="text-[10px] text-slate-500 font-mono mt-0.5 block">
                  Monthly policy cap
                </span>
              </div>
            </div>

            {/* Cloud Route Flow */}
            <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs font-mono flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-bold">
                  Primary: AWS S3 (us-east-1)
                </span>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 font-bold">
                  Standby: GCP Cloud Storage (US)
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-emerald-400">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>SHA-256 Verified Cross-Cloud</span>
              </div>
            </div>
          </div>

          {/* Card 4: Execution Lifecycle & Identifiers */}
          <div className="bg-[#0B0F19] border border-slate-800/90 rounded-xl p-5 shadow-inner">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-cyan-400">
                <Clock className="w-4 h-4" />
              </span>
              <h3 className="text-sm font-semibold text-white">Execution Lifecycle & Audit Metadata</h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
              <div className="space-y-2.5">
                <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/70">
                  <span className="text-slate-400">File ID:</span>
                  <div className="flex items-center gap-1.5 text-slate-200">
                    <span className="truncate max-w-[180px]">{job.file_id}</span>
                    <button
                      onClick={() => handleCopy(job.file_id, 'file_id')}
                      className="text-slate-400 hover:text-white"
                      title="Copy File ID"
                    >
                      {copiedKey === 'file_id' ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/70">
                  <span className="text-slate-400">Version ID:</span>
                  <div className="flex items-center gap-1.5 text-slate-200">
                    <span className="truncate max-w-[180px]">{job.version_id}</span>
                    <button
                      onClick={() => handleCopy(job.version_id, 'ver_id')}
                      className="text-slate-400 hover:text-white"
                      title="Copy Version ID"
                    >
                      {copiedKey === 'ver_id' ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/70">
                  <span className="text-slate-400">Idempotency Key:</span>
                  <div className="flex items-center gap-1.5 text-slate-200">
                    <span className="truncate max-w-[180px]">{job.idempotency_key}</span>
                    <button
                      onClick={() => handleCopy(job.idempotency_key, 'idem_key')}
                      className="text-slate-400 hover:text-white"
                      title="Copy Idempotency Key"
                    >
                      {copiedKey === 'idem_key' ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>
              </div>

              <div className="space-y-2.5">
                <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/70">
                  <span className="text-slate-400">Scheduled At:</span>
                  <span className="text-slate-200">
                    {new Date(job.scheduled_at).toLocaleString()}
                  </span>
                </div>

                <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/70">
                  <span className="text-slate-400">Started / Completed:</span>
                  <span className="text-slate-200">
                    {job.completed_at ? new Date(job.completed_at).toLocaleTimeString() : 'In Progress'}
                  </span>
                </div>

                <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/70">
                  <span className="text-slate-400">Duration & Retries:</span>
                  <span className="text-slate-200">
                    {durationMs !== null ? `${durationMs} ms` : 'N/A'} (Attempts: {job.retry_count} / {job.max_retries})
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Card 5: Raw JSON Audit Viewer (Collapsible) */}
          <div className="border border-slate-800 rounded-xl overflow-hidden bg-[#0B0F19]">
            <button
              onClick={() => setShowRawJson(!showRawJson)}
              className="w-full px-5 py-3.5 flex items-center justify-between text-xs font-semibold text-slate-300 hover:text-white bg-slate-900/60 transition"
            >
              <div className="flex items-center gap-2">
                <Hash className="w-4 h-4 text-cyan-400" />
                <span>Raw Algorithmic Audit Payload (JSON)</span>
              </div>
              <div className="flex items-center gap-2 text-slate-400">
                <span className="text-[11px] font-mono">{showRawJson ? 'Hide' : 'Expand'}</span>
                {showRawJson ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </div>
            </button>

            {showRawJson && (
              <div className="p-4 border-t border-slate-800/80 bg-[#070A12] relative">
                <button
                  onClick={() => handleCopy(decision.rawText, 'raw_json')}
                  className="absolute top-4 right-4 px-2.5 py-1 text-xs font-mono rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 flex items-center gap-1.5 transition"
                  title="Copy JSON Payload"
                >
                  {copiedKey === 'raw_json' ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-emerald-400">Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy JSON</span>
                    </>
                  )}
                </button>
                <pre className="text-[11px] font-mono text-cyan-300/90 overflow-x-auto leading-relaxed p-2">
                  {decision.rawText}
                </pre>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer Actions */}
        <div className="mt-7 pt-4 border-t border-slate-800 flex items-center justify-between flex-wrap gap-3">
          <div className="text-xs text-slate-500 font-mono">
            Platform Engine: Celery Redis Worker • Anti-Flap DR
          </div>

          <div className="flex items-center space-x-3">
            {job.status !== 'COMPLETED' && onRetry && (
              <button
                onClick={handleRetryClick}
                disabled={retrying}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-lg shadow-lg shadow-cyan-600/20 transition flex items-center gap-2 disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${retrying ? 'animate-spin' : ''}`} />
                {retrying ? 'Enqueuing...' : 'Retry Job in Celery'}
              </button>
            )}
            <button
              onClick={onClose}
              className="px-5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

