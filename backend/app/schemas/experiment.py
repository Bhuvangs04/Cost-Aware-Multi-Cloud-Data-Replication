from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExperimentRunCreate(BaseModel):
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    strategy: str = "COST_AWARE_ADAPTIVE"  # FULL, PRIORITY, COST_AWARE_ADAPTIVE
    workload_profile: str = "UNIFORM"  # UNIFORM, BURST, SKEWED_CRITICAL
    num_files: int = 50
    min_size_kb: int = 100
    max_size_kb: int = 10240  # 10 MB
    monthly_budget_usd: float = 50.0


class ExperimentResultRead(BaseModel):
    metric_name: str
    metric_value: float
    unit: str
    dimension: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExperimentRunRead(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    strategy: str
    workload_profile: str
    total_files: int
    total_bytes: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    parameters_json: Optional[str] = None
    results: List[ExperimentResultRead] = []

    model_config = ConfigDict(from_attributes=True)



class SimulationControlRequest(BaseModel):
    simulate_aws_outage: Optional[bool] = None
    simulate_gcp_outage: Optional[bool] = None
    simulated_aws_latency_ms: Optional[float] = None
    simulated_gcp_latency_ms: Optional[float] = None
    simulate_corrupt_checksum: Optional[bool] = None


class SimulationControlResponse(BaseModel):
    simulation_mode: bool
    simulate_aws_outage: bool
    simulate_gcp_outage: bool
    simulated_aws_latency_ms: float
    simulated_gcp_latency_ms: float
    simulate_corrupt_checksum: bool
    message: str
