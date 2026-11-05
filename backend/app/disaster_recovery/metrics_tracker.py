from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File, FileVersion
from app.models.health import DisasterRecoveryEvent
from app.models.replication import FileReplica


class DRMetricsTracker:
    """Calculates real Recovery Time Objective (RTO) and Recovery Point Objective (RPO) metrics."""

    @staticmethod
    def calculate_rto(outage_detected_at: datetime, failover_completed_at: datetime) -> float:
        """
        RTO = Time difference between failure detection and failover routing completion (in seconds).
        """
        delta = (failover_completed_at - outage_detected_at).total_seconds()
        return max(0.01, round(delta, 3))

    @staticmethod
    async def calculate_rpo(session: AsyncSession, outage_timestamp: datetime) -> float:
        """
        RPO = Data lag window (in seconds) between the time of outage and the latest verified replica.
        RPO = T_outage - max(T_replica_verified). If all files are up to date, RPO ~ 0.
        """
        query = select(func.max(FileReplica.verification_timestamp)).where(FileReplica.is_verified == True)
        res = await session.execute(query)
        latest_replica_time = res.scalar_one_or_none()

        if not latest_replica_time:
            return 0.0

        # Ensure timezone-aware comparison
        if latest_replica_time.tzinfo is None:
            latest_replica_time = latest_replica_time.replace(tzinfo=timezone.utc)
        if outage_timestamp.tzinfo is None:
            outage_timestamp = outage_timestamp.replace(tzinfo=timezone.utc)

        lag_seconds = (outage_timestamp - latest_replica_time).total_seconds()
        return max(0.0, round(lag_seconds, 2))

    @staticmethod
    async def get_average_rto_rpo(session: AsyncSession) -> Dict[str, float]:
        """Calculates historical average RTO and RPO across recorded failover events."""
        query = select(
            func.avg(DisasterRecoveryEvent.rto_seconds),
            func.avg(DisasterRecoveryEvent.rpo_seconds),
            func.count(DisasterRecoveryEvent.id),
        ).where(DisasterRecoveryEvent.event_type.in_(["FAILOVER_COMPLETED", "OUTAGE_DETECTED"]))

        res = await session.execute(query)
        avg_rto, avg_rpo, total_events = res.first()

        return {
            "avg_rto_seconds": round(float(avg_rto or 0.0), 2),
            "avg_rpo_seconds": round(float(avg_rpo or 0.0), 2),
            "total_failover_events": int(total_events or 0),
        }

