from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ReplicationPolicyBase(BaseModel):
    name: str
    strategy_type: str = "COST_AWARE_ADAPTIVE"  # FULL, PRIORITY, COST_AWARE_ADAPTIVE
    target_rpo_seconds: int = 3600
    target_rto_seconds: int = 300
    max_budget_monthly_usd: float = 100.0
    weights_json: str = '{"w_priority": 0.35, "w_access": 0.25, "w_rpo": 0.15, "w_size": 0.15, "w_cost": 0.10}'
    threshold_score: float = 0.5
    is_active: bool = True


class ReplicationPolicyCreate(ReplicationPolicyBase):
    pass


class ReplicationPolicyUpdate(BaseModel):
    name: Optional[str] = None
    strategy_type: Optional[str] = None
    target_rpo_seconds: Optional[int] = None
    target_rto_seconds: Optional[int] = None
    max_budget_monthly_usd: Optional[float] = None
    weights_json: Optional[str] = None
    threshold_score: Optional[float] = None
    is_active: Optional[bool] = None


class ReplicationPolicyRead(ReplicationPolicyBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReplicationJobRead(BaseModel):
    id: str
    file_id: str
    version_id: str
    policy_id: Optional[str] = None
    strategy_used: str
    status: str
    decision_score: Optional[float] = None
    decision_reason: Optional[str] = None
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int
    max_retries: int
    error_message: Optional[str] = None
    idempotency_key: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)



class DecisionExplanation(BaseModel):
    file_id: str
    action: str  # REPLICATE_NOW, DEFER_BATCH, SKIP
    strategy: str
    score: Optional[float] = None
    breakdown: Dict[str, Any] = {}
    estimated_cost_usd: float
    budget_remaining_usd: float
    decision_reason: str
