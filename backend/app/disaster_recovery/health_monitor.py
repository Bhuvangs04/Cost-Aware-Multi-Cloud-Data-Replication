import asyncio
from datetime import datetime, timezone
import sys
import time
from typing import Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import logger
from app.disaster_recovery.failover_router import FailoverRouter
from app.disaster_recovery.reconciliation import ReconciliationEngine
from app.models.base import utc_now
from app.models.cloud_provider import CloudProvider
from app.models.health import CloudHealthLog
from app.storage.factory import get_aws_provider, get_gcp_provider


class CloudHealthMonitor:
    """
    Synthetic health monitoring daemon for AWS S3 and GCP Storage.
    Implements sliding-window failure counters to prevent flapping,
    and automatically triggers failover and post-recovery reconciliation.
    """

    def __init__(
        self,
        failure_threshold: int = settings.CONSECUTIVE_FAILURE_THRESHOLD,
        restore_threshold: int = settings.HEALTH_RESTORE_THRESHOLD,
    ):
        self.failure_threshold = failure_threshold
        self.restore_threshold = restore_threshold
        self._consecutive_failures = {"AWS_S3": 0, "GCP_STORAGE": 0}
        self._consecutive_successes = {"AWS_S3": 0, "GCP_STORAGE": 0}

    async def probe_provider(
        self,
        session: AsyncSession,
        provider_name: str,
    ) -> Tuple[bool, float, int, str]:
        """Performs a synthetic probe on a cloud provider and logs results to the database."""
        provider = get_aws_provider() if provider_name == "AWS_S3" else get_gcp_provider()
        health = await provider.check_health()

        # Fetch provider DB record
        res = await session.execute(
            select(CloudProvider).where(CloudProvider.name == provider_name)
        )
        db_provider = res.scalars().first()

        if db_provider:
            db_provider.current_latency_ms = health.latency_ms
            db_provider.last_health_check_at = utc_now()

        # Record health log
        health_log = CloudHealthLog(
            provider_id=db_provider.id if db_provider else f"{provider_name.lower()}-default",
            check_type="SYNTHETIC_HEAD",
            status="HEALTHY" if health.is_healthy else "DOWN",
            latency_ms=health.latency_ms,
            http_status_code=health.http_status,
            error_detail=health.details if not health.is_healthy else None,
            is_simulated=settings.SIMULATION_MODE,
        )
        session.add(health_log)

        return health.is_healthy, health.latency_ms, health.http_status, health.details

    async def execute_probe_cycle(self, session: Optional[AsyncSession] = None) -> dict:
        """
        Executes one full probe cycle across AWS S3 and GCP Storage,
        applies flap detection thresholds, and triggers failover / recovery if thresholds are crossed.
        """
        if session is not None:
            return await self._run_probe_with_session(session)
        else:
            async with AsyncSessionLocal() as new_session:
                return await self._run_probe_with_session(new_session)

    async def _run_probe_with_session(self, session: AsyncSession) -> dict:
        cycle_results = {}

        for provider_name in ["AWS_S3", "GCP_STORAGE"]:
            is_healthy, latency, status_code, details = await self.probe_provider(session, provider_name)
            cycle_results[provider_name] = {
                "healthy": is_healthy,
                "latency_ms": latency,
                "status_code": status_code,
            }

            if is_healthy:
                self._consecutive_successes[provider_name] += 1
                self._consecutive_failures[provider_name] = 0
            else:
                self._consecutive_failures[provider_name] += 1
                self._consecutive_successes[provider_name] = 0

        # Flap Detection & Automatic Failover Trigger for AWS S3
        aws_failures = self._consecutive_failures["AWS_S3"]
        aws_successes = self._consecutive_successes["AWS_S3"]

        # Fetch current DB status
        res_aws = await session.execute(select(CloudProvider).where(CloudProvider.name == "AWS_S3"))
        aws_db = res_aws.scalars().first()
        is_currently_down = aws_db and aws_db.status in ("DOWN", "DEGRADED")

        failover_event = None
        reconciliation_event = None

        # 1. Condition for Failover: AWS failed >= K times, and not already marked down
        if aws_failures >= self.failure_threshold and not is_currently_down:
            logger.warning(
                f"AWS S3 reached failure threshold ({aws_failures}/{self.failure_threshold}). "
                "Triggering automated disaster recovery failover to GCP Storage!"
            )
            failover_event = await FailoverRouter.trigger_failover(
                session=session,
                reason=f"Automated failure detector: {aws_failures} consecutive synthetic probe failures on AWS S3.",
            )

        # 2. Condition for Recovery: AWS succeeded >= M times after being down
        elif aws_successes >= self.restore_threshold and is_currently_down:
            logger.info(
                f"AWS S3 restored ({aws_successes}/{self.restore_threshold} consecutive healthy probes). "
                "Triggering post-outage reconciliation..."
            )
            reconciliation_event = await ReconciliationEngine.reconcile_after_recovery(session=session)

        await session.commit()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "probes": cycle_results,
            "consecutive_failures": self._consecutive_failures,
            "consecutive_successes": self._consecutive_successes,
            "failover_triggered": failover_event is not None,
            "reconciliation_triggered": reconciliation_event is not None,
        }

    async def run_forever(self, interval_seconds: int = settings.HEALTH_PROBE_INTERVAL_SECONDS):
        """Continuously runs the health prober daemon."""
        logger.info(f"Starting Disaster Recovery Health Prober (interval: {interval_seconds}s)...")
        while True:
            try:
                await self.execute_probe_cycle()
            except Exception as e:
                logger.error(f"Error in health probe cycle: {e}")
            await asyncio.sleep(interval_seconds)


# Entry point for docker container command: python -m app.disaster_recovery.health_monitor
if __name__ == "__main__":
    monitor = CloudHealthMonitor()
    asyncio.run(monitor.run_forever())
