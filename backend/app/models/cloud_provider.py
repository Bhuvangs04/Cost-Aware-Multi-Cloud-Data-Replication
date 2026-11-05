from sqlalchemy import Boolean, Column, DateTime, Float, String
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid


class CloudProvider(Base, TimestampMixin):
    __tablename__ = "cloud_providers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(32), unique=True, index=True, nullable=False)  # AWS_S3, GCP_STORAGE
    is_active = Column(Boolean, default=True, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    bucket_name = Column(String(128), nullable=False)
    region = Column(String(64), nullable=False)
    endpoint_url = Column(String(255), nullable=True)
    status = Column(String(32), default="HEALTHY", nullable=False)  # HEALTHY, DEGRADED, DOWN
    current_latency_ms = Column(Float, default=0.0, nullable=False)
    last_health_check_at = Column(DateTime, nullable=True)

