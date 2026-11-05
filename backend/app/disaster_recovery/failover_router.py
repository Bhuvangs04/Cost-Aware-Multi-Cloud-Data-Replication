from datetime import datetime, timezone
import json
import time
from typing import Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import FailoverActiveError, ProviderUnavailableError
from app.core.logging import logger
from app.disaster_recovery.metrics_tracker import DRMetricsTracker
from app.models.cloud_provider import CloudProvider
from app.models.file import File
from app.models.health import DisasterRecoveryEvent
from app.models.replication import FileReplica
from app.storage.factory import get_aws_provider, get_gcp_provider


class FailoverRouter:
    """
    Manages active storage routing during cloud outages and disaster recovery failover.
    """

    @classmethod
    async def get_routing_status(cls, session: AsyncSession) -> dict:
        """Determines active read and write provider states."""
        res = await session.execute(select(CloudProvider))
        providers = {p.name: p for p in res.scalars().all()}

        aws_p = providers.get("AWS_S3")
        gcp_p = providers.get("GCP_STORAGE")

        aws_down = (
            (aws_p and aws_p.status in ("DEGRADED", "DOWN"))
            or settings.SIMULATE_AWS_OUTAGE
        )
        failover_active = aws_down

        active_read = "GCP_STORAGE" if failover_active else "AWS_S3"

        return {
            "active_read_provider": active_read,
            "failover_active": failover_active,
            "aws_status": "DOWN" if aws_down else (aws_p.status if aws_p else "HEALTHY"),
            "gcp_status": "DOWN" if settings.SIMULATE_GCP_OUTAGE else (gcp_p.status if gcp_p else "HEALTHY"),
        }

    @classmethod
    async def trigger_failover(
        cls,
        session: AsyncSession,
        reason: str = "Outage detected on primary cloud (AWS S3)",
        failed_provider_name: str = "AWS_S3",
        target_provider_name: str = "GCP_STORAGE",
    ) -> DisasterRecoveryEvent:
        """
        Executes automatic or manual failover:
        1. Verifies Secondary Cloud (GCP) health to avoid failing over to a broken cloud.
        2. Measures RTO and RPO.
        3. Updates provider status in PostgreSQL.
        4. Redirects all read queries to verified GCP replicas.
        5. Logs DisasterRecoveryEvent.
        """
        t_detect = datetime.now(timezone.utc)
        logger.warning(f"DISASTER RECOVERY TRIGGERED: {reason}. Switching routing from {failed_provider_name} to {target_provider_name}")

        # 1. Verify Secondary Cloud health before completing failover
        gcp_provider = get_gcp_provider()
        gcp_health = await gcp_provider.check_health()
        if not gcp_health.is_healthy:
            msg = f"Secondary provider {target_provider_name} is also unhealthy! Cannot complete failover: {gcp_health.details}"
            logger.critical(msg)
            raise ProviderUnavailableError(msg)

        # 2. Update Provider DB Records
        res_providers = await session.execute(select(CloudProvider))
        providers = {p.name: p for p in res_providers.scalars().all()}

        failed_p = providers.get(failed_provider_name)
        target_p = providers.get(target_provider_name)

        if failed_p:
            failed_p.status = "DOWN"
        if target_p:
            target_p.status = "HEALTHY"

        # 3. Calculate RPO and count accessible replicas
        rpo_seconds = await DRMetricsTracker.calculate_rpo(session, t_detect)

        count_query = select(func.count(FileReplica.id)).where(FileReplica.is_verified == True)
        count_res = await session.execute(count_query)
        affected_files = int(count_res.scalar_one() or 0)

        t_complete = datetime.now(timezone.utc)
        rto_seconds = DRMetricsTracker.calculate_rto(t_detect, t_complete)

        # 4. Record Disaster Recovery Event
        details = {
            "reason": reason,
            "failed_provider": failed_provider_name,
            "target_provider": target_provider_name,
            "gcp_latency_ms": gcp_health.latency_ms,
            "routing_action": "READS_DIVERTED_TO_GCP",
        }

        event = DisasterRecoveryEvent(
            event_type="FAILOVER_COMPLETED",
            failed_provider_id=failed_p.id if failed_p else None,
            failover_provider_id=target_p.id if target_p else None,
            rto_seconds=rto_seconds,
            rpo_seconds=rpo_seconds,
            affected_files_count=affected_files,
            reconciled_files_count=0,
            details_json=json.dumps(details),
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)

        logger.info(
            f"Failover completed successfully. RTO: {rto_seconds}s, RPO: {rpo_seconds}s, "
            f"Eligible Verified Replicas: {affected_files}"
        )
        return event

