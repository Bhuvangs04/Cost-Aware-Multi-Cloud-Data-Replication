from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import generate_uuid, utc_now


class CloudHealthLog(Base):
    __tablename__ = "cloud_health_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    provider_id = Column(String(36), ForeignKey("cloud_providers.id"), nullable=False, index=True)
    check_type = Column(String(32), default="SYNTHETIC_HEAD", nullable=False)
    status = Column(String(32), nullable=False)  # HEALTHY, DEGRADED, DOWN
    latency_ms = Column(Float, default=0.0, nullable=False)
    http_status_code = Column(Integer, nullable=True)
    error_detail = Column(Text, nullable=True)
    is_simulated = Column(Boolean, default=False, nullable=False)
    checked_at = Column(DateTime, default=utc_now, nullable=False, index=True)

    provider = relationship("CloudProvider")


class DisasterRecoveryEvent(Base):
    __tablename__ = "disaster_recovery_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_type = Column(
        String(64), nullable=False, index=True
    )  # OUTAGE_DETECTED, FAILOVER_TRIGGERED, FAILOVER_COMPLETED, PRIMARY_RECOVERED, RECONCILIATION_COMPLETED
    failed_provider_id = Column(String(36), ForeignKey("cloud_providers.id"), nullable=True)
    failover_provider_id = Column(String(36), ForeignKey("cloud_providers.id"), nullable=True)
    rto_seconds = Column(Float, nullable=True)
    rpo_seconds = Column(Float, nullable=True)
    affected_files_count = Column(Integer, default=0, nullable=False)
    reconciled_files_count = Column(Integer, default=0, nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False, index=True)

    failed_provider = relationship("CloudProvider", foreign_keys=[failed_provider_id])
    failover_provider = relationship("CloudProvider", foreign_keys=[failover_provider_id])

