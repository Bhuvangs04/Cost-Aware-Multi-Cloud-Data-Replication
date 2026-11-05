from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import BinaryIO, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field


class StorageObjectRef(BaseModel):
    provider: str
    bucket: str
    key: str
    version_id: Optional[str] = None
    generation_id: Optional[str] = None
    sha256_hash: str
    size_bytes: int
    etag: Optional[str] = None
    last_modified: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    custom_metadata: Dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class ObjectMetadata(BaseModel):
    provider: str
    bucket: str
    key: str
    version_id: Optional[str] = None
    size_bytes: int
    content_type: str = "application/octet-stream"
    sha256_hash: str
    last_modified: datetime
    etag: Optional[str] = None
    custom_metadata: Dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class HealthStatus(BaseModel):
    provider: str
    is_healthy: bool
    latency_ms: float
    http_status: int
    details: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class StorageMetrics(BaseModel):
    provider: str
    bucket: str
    total_objects: int
    total_bytes: int
    estimated_monthly_cost_usd: float

    model_config = ConfigDict(from_attributes=True)


class IntegrityResult(BaseModel):
    provider: str
    key: str
    version_id: Optional[str] = None
    expected_sha256: str
    actual_sha256: str
    is_valid: bool
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str

    model_config = ConfigDict(from_attributes=True)


class ICloudStorageProvider(ABC):
    """Abstract Base Class defining the cloud-agnostic storage provider interface."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the identifier of the cloud provider (e.g. AWS_S3, GCP_STORAGE)."""
        pass

    @property
    @abstractmethod
    def bucket_name(self) -> str:
        """Returns the primary target bucket name."""
        pass

    @abstractmethod
    async def upload_file(
        self,
        key: str,
        data: Union[bytes, BinaryIO],
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> StorageObjectRef:
        """Uploads a file/stream to the cloud provider, computing SHA-256 and capturing versioning."""
        pass

    @abstractmethod
    async def download_file(
        self,
        key: str,
        version_id: Optional[str] = None,
    ) -> Tuple[bytes, ObjectMetadata]:
        """Downloads a specific version of a file and returns its payload and metadata."""
        pass

    @abstractmethod
    async def delete_file(
        self,
        key: str,
        version_id: Optional[str] = None,
    ) -> bool:
        """Deletes an object or specific object version."""
        pass

    @abstractmethod
    async def get_metadata(
        self,
        key: str,
        version_id: Optional[str] = None,
    ) -> ObjectMetadata:
        """Retrieves object metadata without downloading full payload."""
        pass

    @abstractmethod
    async def check_health(self) -> HealthStatus:
        """Performs a lightweight synthetic probe to ascertain provider latency and availability."""
        pass

    @abstractmethod
    async def list_versions(self, key: str) -> List[StorageObjectRef]:
        """Lists all immutable versions of a given key."""
        pass

    @abstractmethod
    async def calculate_storage_usage(self) -> StorageMetrics:
        """Aggregates total stored volume and computes projected monthly storage cost."""
        pass

    @abstractmethod
    async def verify_integrity(
        self,
        key: str,
        expected_sha256: str,
        version_id: Optional[str] = None,
    ) -> IntegrityResult:
        """Verifies cryptographic hash of the stored object against expected SHA-256."""
        pass

