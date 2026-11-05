from datetime import date, datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


class CostEstimateRequest(BaseModel):
    file_size_bytes: int
    priority: str = "MEDIUM"
    access_frequency_tier: str = "FREQUENT"
    retention_months: int = 1


class CostEstimateResponse(BaseModel):
    file_size_gb: float
    aws_storage_monthly_usd: float
    gcp_storage_monthly_usd: float
    cross_cloud_egress_usd: float
    operations_cost_usd: float
    total_full_replication_usd: float
    total_adaptive_replication_usd: float
    estimated_savings_usd: float
    savings_percentage: float
    pricing_assumptions: Dict[str, float]


class CostSummaryResponse(BaseModel):
    total_aws_storage_usd: float
    total_gcp_storage_usd: float
    total_egress_transfer_usd: float
    total_replication_ops_usd: float
    total_cost_current_strategy_usd: float
    baseline_full_replication_cost_usd: float
    net_savings_usd: float
    net_savings_percentage: float
    cost_per_replicated_gb_usd: float
    active_strategy: str
    monthly_budget_usd: float
    budget_utilized_percent: float
    is_simulated: bool

