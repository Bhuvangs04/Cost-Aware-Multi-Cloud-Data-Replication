from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class CloudProviderRead(BaseModel):
    id: str
    name: str
    is_active: bool
    is_primary: bool
    bucket_name: str
    region: str
    endpoint_url: Optional[str] = None
    status: str
    current_latency_ms: float
    last_health_check_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class HealthStatusReport(BaseModel):
    timestamp: datetime
    primary_cloud: CloudProviderRead
    secondary_cloud: CloudProviderRead
    active_read_provider: str
    failover_active: bool
    simulation_mode: bool
    consecutive_failures: int


class TriggerFailoverRequest(BaseModel):
    reason: str = "Manual disaster recovery simulation"
    target_provider: str = "GCP_STORAGE"


class DisasterRecoveryEventRead(BaseModel):
    id: str
    event_type: str
    failed_provider_id: Optional[str] = None
    failover_provider_id: Optional[str] = None
    rto_seconds: Optional[float] = None
    rpo_seconds: Optional[float] = None
    affected_files_count: int
    reconciled_files_count: int
    details_json: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)



class ReconciliationResponse(BaseModel):
    reconciliation_id: str
    files_reconciled: int
    conflicts_detected: int
    duration_seconds: float
    status: str
    message: str
