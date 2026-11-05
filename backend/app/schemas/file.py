from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class FileVersionRead(BaseModel):
    id: str
    version_num: int
    aws_version_id: Optional[str] = None
    gcp_generation_id: Optional[str] = None
    size_bytes: int
    sha256_hash: str
    is_current: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileReplicaRead(BaseModel):
    id: str
    provider_id: str
    replica_uri: str
    storage_tier: str
    sha256_hash: str
    is_verified: bool
    verification_timestamp: Optional[datetime] = None
    size_bytes: int
    replication_latency_ms: float
    transfer_cost_usd: float
    storage_cost_monthly_usd: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileUploadResponse(BaseModel):
    file_id: str
    version_id: str
    filename: str
    storage_key: str
    file_size_bytes: int
    sha256_hash: str
    priority: str
    access_frequency_tier: str
    upload_status: str
    replication_job_id: Optional[str] = None
    message: str


class FileMetadataRead(BaseModel):
    id: str
    owner_id: str
    filename: str
    storage_key: str
    file_size_bytes: int
    content_type: str
    sha256_hash: str
    priority: str
    access_frequency_tier: str
    tags: Optional[str] = None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    versions: List[FileVersionRead] = []
    replicas: List[FileReplicaRead] = []

    model_config = ConfigDict(from_attributes=True)



class FileListResponse(BaseModel):
    total: int
    items: List[FileMetadataRead]
