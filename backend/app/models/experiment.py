from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import generate_uuid, utc_now


class ExperimentRun(Base):
    __tablename__ = "experiment_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    strategy = Column(String(64), nullable=False)  # FULL, PRIORITY, COST_AWARE_ADAPTIVE
    workload_profile = Column(String(64), nullable=False)  # UNIFORM, BURST, SKEWED_CRITICAL
    total_files = Column(Integer, default=0, nullable=False)
    total_bytes = Column(BigInteger, default=0, nullable=False)
    started_at = Column(DateTime, default=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="RUNNING", nullable=False)  # RUNNING, COMPLETED, FAILED
    parameters_json = Column(Text, nullable=True)

    results = relationship("ExperimentResult", back_populates="run", cascade="all, delete-orphan")


class ExperimentResult(Base):
    __tablename__ = "experiment_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    experiment_run_id = Column(String(36), ForeignKey("experiment_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_name = Column(String(64), nullable=False, index=True)
    metric_value = Column(Numeric(12, 6), nullable=False)
    unit = Column(String(32), nullable=False)  # USD, ms, bytes, count, percent
    dimension = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    run = relationship("ExperimentRun", back_populates="results")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(64), nullable=True)
    metadata_json = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)

    user = relationship("User")

