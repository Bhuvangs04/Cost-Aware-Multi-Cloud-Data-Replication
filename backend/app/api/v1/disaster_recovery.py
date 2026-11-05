from datetime import datetime, timezone
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.disaster_recovery.failover_router import FailoverRouter
from app.disaster_recovery.health_monitor import CloudHealthMonitor
from app.disaster_recovery.metrics_tracker import DRMetricsTracker
from app.disaster_recovery.reconciliation import ReconciliationEngine
from app.models.cloud_provider import CloudProvider
from app.models.health import DisasterRecoveryEvent
from app.models.user import User
from app.schemas.disaster_recovery import (
    CloudProviderRead,
    DisasterRecoveryEventRead,
    HealthStatusReport,
    ReconciliationResponse,
    TriggerFailoverRequest,
)

router = APIRouter(prefix="/disaster-recovery", tags=["Disaster Recovery"])


@router.get("/status", response_model=HealthStatusReport)
@router.get("/health", response_model=HealthStatusReport)
async def get_dr_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves current health status of AWS S3 and GCP Storage and active read provider."""
    result = await db.execute(select(CloudProvider))
    providers = {p.name: p for p in result.scalars().all()}

    routing = await FailoverRouter.get_routing_status(db)

    aws_provider = providers.get("AWS_S3") or CloudProvider(
        id="aws-default",
        name="AWS_S3",
        is_active=True,
        is_primary=True,
        bucket_name=settings.AWS_S3_BUCKET_NAME,
        region=settings.AWS_DEFAULT_REGION,
        status=routing["aws_status"],
        current_latency_ms=settings.SIMULATED_AWS_LATENCY_MS,
    )

    gcp_provider = providers.get("GCP_STORAGE") or CloudProvider(
        id="gcp-default",
        name="GCP_STORAGE",
        is_active=True,
        is_primary=False,
        bucket_name=settings.GCP_BUCKET_NAME,
        region=settings.GCP_DEFAULT_LOCATION,
        status=routing["gcp_status"],
        current_latency_ms=settings.SIMULATED_GCP_LATENCY_MS,
    )

    return HealthStatusReport(
        timestamp=datetime.now(timezone.utc),
        primary_cloud=CloudProviderRead.model_validate(aws_provider),
        secondary_cloud=CloudProviderRead.model_validate(gcp_provider),
        active_read_provider=routing["active_read_provider"],
        failover_active=routing["failover_active"],
        simulation_mode=settings.SIMULATION_MODE,
        consecutive_failures=3 if routing["failover_active"] else 0,
    )


@router.post("/probe")
async def trigger_health_probe(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executes an immediate synthetic health probe cycle on both cloud providers."""
    monitor = CloudHealthMonitor()
    cycle_res = await monitor.execute_probe_cycle(session=db)
    return cycle_res


@router.post("/failover", response_model=DisasterRecoveryEventRead)
async def trigger_manual_failover(
    request: TriggerFailoverRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually triggers failover to secondary cloud (GCP) for disaster recovery drill."""
    event = await FailoverRouter.trigger_failover(
        session=db,
        reason=request.reason,
        target_provider_name=request.target_provider,
    )
    return event


@router.post("/reconcile", response_model=ReconciliationResponse)
async def trigger_reconciliation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Triggers bidirectional reconciliation from GCP to AWS after primary recovery."""
    res = await ReconciliationEngine.reconcile_after_recovery(session=db)
    return ReconciliationResponse(**res)


@router.get("/metrics")
async def get_rto_rpo_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves statistical RTO and RPO averages across disaster recovery scenarios."""
    metrics = await DRMetricsTracker.get_average_rto_rpo(db)
    return metrics


@router.get("/events", response_model=List[DisasterRecoveryEventRead])
async def list_dr_events(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves disaster recovery history, outage detections, failovers, and reconciliations."""
    result = await db.execute(
        select(DisasterRecoveryEvent).order_by(DisasterRecoveryEvent.created_at.desc()).limit(50)
    )
    return result.scalars().all()
