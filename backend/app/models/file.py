from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid, utc_now
from sqlalchemy import DateTime


class File(Base, TimestampMixin):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    storage_key = Column(String(512), unique=True, index=True, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    content_type = Column(String(128), default="application/octet-stream", nullable=False)
    sha256_hash = Column(String(64), index=True, nullable=False)
    priority = Column(String(32), default="MEDIUM", nullable=False)  # CRITICAL, HIGH, MEDIUM, LOW
    access_frequency_tier = Column(String(32), default="FREQUENT", nullable=False)  # FREQUENT, INTERMITTENT, RARE
    tags = Column(Text, nullable=True)  # JSON-encoded tags string
    is_deleted = Column(Boolean, default=False, nullable=False)

    versions = relationship("FileVersion", back_populates="file", cascade="all, delete-orphan")
    replicas = relationship("FileReplica", back_populates="file", cascade="all, delete-orphan")
    jobs = relationship("ReplicationJob", back_populates="file", cascade="all, delete-orphan")


class FileVersion(Base):
    __tablename__ = "file_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    version_num = Column(Integer, default=1, nullable=False)
    aws_version_id = Column(String(128), nullable=True)
    gcp_generation_id = Column(String(128), nullable=True)
    size_bytes = Column(BigInteger, nullable=False)
    sha256_hash = Column(String(64), nullable=False)
    is_current = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    file = relationship("File", back_populates="versions")
    replicas = relationship("FileReplica", back_populates="version", cascade="all, delete-orphan")

