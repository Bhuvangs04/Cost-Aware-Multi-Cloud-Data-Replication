from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid, utc_now


class ReplicationPolicy(Base, TimestampMixin):
    __tablename__ = "replication_policies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(64), unique=True, index=True, nullable=False)
    strategy_type = Column(String(32), default="COST_AWARE_ADAPTIVE", nullable=False)  # FULL, PRIORITY, COST_AWARE_ADAPTIVE
    target_rpo_seconds = Column(Integer, default=3600, nullable=False)
    target_rto_seconds = Column(Integer, default=300, nullable=False)
    max_budget_monthly_usd = Column(Numeric(10, 4), default=100.0, nullable=False)
    weights_json = Column(Text, nullable=False)  # JSON weights for scoring algorithm
    threshold_score = Column(Float, default=0.5, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    jobs = relationship("ReplicationJob", back_populates="policy")


class ReplicationJob(Base):
    __tablename__ = "replication_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id = Column(String(36), ForeignKey("file_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_id = Column(String(36), ForeignKey("replication_policies.id"), nullable=True)
    strategy_used = Column(String(32), nullable=False)
    status = Column(
        String(32), default="PENDING", nullable=False, index=True
    )  # PENDING, EVALUATING, SKIPPED, QUEUED, IN_PROGRESS, COMPLETED, FAILED, RETRYING
    decision_score = Column(Float, nullable=True)
    decision_reason = Column(Text, nullable=True)  # JSON explanation of decision
    scheduled_at = Column(DateTime, default=utc_now, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    error_message = Column(Text, nullable=True)
    idempotency_key = Column(String(128), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    file = relationship("File", back_populates="jobs")
    policy = relationship("ReplicationPolicy", back_populates="jobs")


class FileReplica(Base):
    __tablename__ = "file_replicas"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id = Column(String(36), ForeignKey("file_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(String(36), ForeignKey("cloud_providers.id"), nullable=False, index=True)
    replica_uri = Column(String(512), nullable=False)
    storage_tier = Column(String(32), default="STANDARD", nullable=False)
    sha256_hash = Column(String(64), nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_timestamp = Column(DateTime, nullable=True)
    size_bytes = Column(BigInteger, nullable=False)
    replication_latency_ms = Column(Float, default=0.0, nullable=False)
    transfer_cost_usd = Column(Numeric(10, 6), default=0.0, nullable=False)
    storage_cost_monthly_usd = Column(Numeric(10, 6), default=0.0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    file = relationship("File", back_populates="replicas")
    version = relationship("FileVersion", back_populates="replicas")
    provider = relationship("CloudProvider")

