export interface User {
  id: string;
  email: string;
  username: string;
  full_name?: string;
  role: 'admin' | 'operator' | 'viewer';
  is_active: boolean;
}

export interface FileVersion {
  id: string;
  version_num: number;
  aws_version_id?: string;
  gcp_generation_id?: string;
  size_bytes: number;
  sha256_hash: string;
  is_current: boolean;
  created_at: string;
}

export interface FileReplica {
  id: string;
  provider_id: string;
  replica_uri: string;
  storage_tier: string;
  sha256_hash: string;
  is_verified: boolean;
  verification_timestamp?: string;
  size_bytes: number;
  replication_latency_ms: number;
  transfer_cost_usd: number;
  storage_cost_monthly_usd: number;
  created_at: string;
}

export interface FileMetadata {
  id: string;
  owner_id: string;
  filename: string;
  storage_key: string;
  file_size_bytes: number;
  content_type: string;
  sha256_hash: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  access_frequency_tier: 'FREQUENT' | 'INFREQUENT' | 'ARCHIVE';
  tags?: string;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  versions: FileVersion[];
  replicas: FileReplica[];
}

export interface CloudProvider {
  id: string;
  name: string;
  is_active: boolean;
  is_primary: boolean;
  bucket_name: string;
  region: string;
  endpoint_url?: string;
  status: 'HEALTHY' | 'DEGRADED' | 'OUTAGE';
  current_latency_ms: number;
  last_health_check_at?: string;
}

export interface HealthStatusReport {
  timestamp: string;
  primary_cloud: CloudProvider;
  secondary_cloud: CloudProvider;
  active_read_provider: string;
  failover_active: boolean;
  simulation_mode: boolean;
  consecutive_failures: number;
}

export interface ReplicationPolicy {
  id: string;
  name: string;
  strategy_type: 'FULL' | 'PRIORITY' | 'COST_AWARE_ADAPTIVE';
  target_rpo_seconds: number;
  target_rto_seconds: number;
  max_budget_monthly_usd: number;
  weights_json: string;
  threshold_score: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReplicationJob {
  id: string;
  file_id: string;
  version_id: string;
  policy_id?: string;
  strategy_used: string;
  status: 'PENDING' | 'REPLICATING' | 'VERIFYING' | 'COMPLETED' | 'SKIPPED' | 'FAILED' | 'RETRYING';
  decision_score?: number;
  decision_reason?: string;
  scheduled_at: string;
  started_at?: string;
  completed_at?: string;
  retry_count: number;
  max_retries: number;
  error_message?: string;
  idempotency_key: string;
  created_at: string;
}

export interface DisasterRecoveryEvent {
  id: string;
  event_type: 'OUTAGE_DETECTED' | 'FAILOVER_INITIATED' | 'FAILOVER_COMPLETED' | 'FAILBACK_INITIATED' | 'RECONCILIATION_COMPLETED';
  failed_provider_id?: string;
  failover_provider_id?: string;
  rto_seconds?: number;
  rpo_seconds?: number;
  affected_files_count: number;
  reconciled_files_count: number;
  details_json?: string;
  created_at: string;
}

export interface CostSummary {
  total_aws_storage_usd: number;
  total_gcp_storage_usd: number;
  total_egress_transfer_usd: number;
  total_replication_ops_usd: number;
  total_cost_current_strategy_usd: number;
  baseline_full_replication_cost_usd: number;
  net_savings_usd: number;
  net_savings_percentage: number;
  cost_per_replicated_gb_usd: number;
  active_strategy: string;
  monthly_budget_usd: number;
  budget_utilized_percent: number;
  is_simulated: boolean;
}

export interface DecisionExplanation {
  file_id: string;
  action: 'REPLICATE_NOW' | 'DEFER_BATCH' | 'SKIP';
  strategy: string;
  score?: number;
  breakdown: Record<string, number | string>;
  estimated_cost_usd: number;
  budget_remaining_usd: number;
  decision_reason: string;
}

export interface BenchmarkResult {
  strategy: 'Full Replication' | 'Priority-Based' | 'Cost-Aware Adaptive';
  totalFiles: number;
  replicatedCount: number;
  replicationRatePercent: number;
  totalDataReplicatedMB: number;
  totalCostUSD: number;
  costSavingsPercent: number;
  avgReplicationLatencyMs: number;
  rtoSeconds: number;
  rpoSeconds: number;
  zeroRpoCriticalCompliance: number;
}

