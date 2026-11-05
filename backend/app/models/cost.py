from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import generate_uuid, utc_now


class CostRecord(Base):
    __tablename__ = "cost_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    record_date = Column(Date, nullable=False, index=True)
    provider_id = Column(String(36), ForeignKey("cloud_providers.id"), nullable=False, index=True)
    file_id = Column(String(36), ForeignKey("files.id"), nullable=True, index=True)
    storage_cost_usd = Column(Numeric(10, 6), default=0.0, nullable=False)
    egress_transfer_cost_usd = Column(Numeric(10, 6), default=0.0, nullable=False)
    api_operation_cost_usd = Column(Numeric(10, 6), default=0.0, nullable=False)
    cumulative_savings_vs_full_usd = Column(Numeric(10, 6), default=0.0, nullable=False)
    is_simulated = Column(Boolean, default=True, nullable=False)
    recorded_at = Column(DateTime, default=utc_now, nullable=False)

    provider = relationship("CloudProvider")
    file = relationship("File")

