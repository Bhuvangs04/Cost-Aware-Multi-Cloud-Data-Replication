import asyncio
from datetime import datetime, timezone
import hashlib
import io
import time
from typing import BinaryIO, Dict, List, Optional, Tuple, Union
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.config import settings
from app.core.exceptions import ObjectNotFoundError, ProviderUnavailableError, StorageProviderError
from app.core.logging import logger
from app.storage.base import (
    HealthStatus,
    ICloudStorageProvider,
    IntegrityResult,
    ObjectMetadata,
    StorageMetrics,
    StorageObjectRef,
)


class AWSS3StorageAdapter(ICloudStorageProvider):
    """Production AWS S3 Storage Adapter using boto3 with asynchronous offloading and versioning."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        self._bucket_name = bucket_name or settings.AWS_S3_BUCKET_NAME
        self._region_name = region_name or settings.AWS_DEFAULT_REGION
        self._endpoint_url = endpoint_url or settings.AWS_S3_ENDPOINT_URL

        client_kwargs = {
            "service_name": "s3",
            "region_name": self._region_name,
            "config": Config(
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=15,
            ),
        }
        if aws_access_key_id and aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = aws_access_key_id
            client_kwargs["aws_secret_access_key"] = aws_secret_access_key
        elif settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

        if self._endpoint_url:
            client_kwargs["endpoint_url"] = self._endpoint_url

        self.s3_client = boto3.client(**client_kwargs)

    @property
    def provider_name(self) -> str:
        return "AWS_S3"

    @property
    def bucket_name(self) -> str:
        return self._bucket_name

    def _compute_sha256(self, data: bytes) -> str:
        hasher = hashlib.sha256()
        hasher.update(data)
        return hasher.hexdigest()

    async def upload_file(
        self,
        key: str,
        data: Union[bytes, BinaryIO],
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> StorageObjectRef:
        """Uploads an object to AWS S3 and extracts VersionId and Checksum."""
        raw_bytes = data if isinstance(data, bytes) else data.read()
        sha256_hash = self._compute_sha256(raw_bytes)
        size_bytes = len(raw_bytes)

        req_metadata = metadata.copy() if metadata else {}
        req_metadata["sha256"] = sha256_hash

        def _sync_upload():
            try:
                response = self.s3_client.put_object(
                    Bucket=self._bucket_name,
                    Key=key,
                    Body=raw_bytes,
                    ContentType=content_type,
                    Metadata=req_metadata,
                )
                version_id = response.get("VersionId")
                etag = response.get("ETag", "").strip('"')
                return version_id, etag
            except (EndpointConnectionError, ClientError) as e:
                logger.error(f"S3 PutObject failed for key '{key}': {e}")
                raise ProviderUnavailableError(f"AWS S3 upload failed: {str(e)}")

        version_id, etag = await asyncio.to_thread(_sync_upload)

        return StorageObjectRef(
            provider=self.provider_name,
            bucket=self._bucket_name,
            key=key,
            version_id=version_id,
            sha256_hash=sha256_hash,
            size_bytes=size_bytes,
            etag=etag,
            last_modified=datetime.now(timezone.utc),
            custom_metadata=req_metadata,
        )

    async def download_file(
        self,
        key: str,
        version_id: Optional[str] = None,
    ) -> Tuple[bytes, ObjectMetadata]:
        """Downloads an object version from S3."""
        def _sync_download():
            kwargs = {"Bucket": self._bucket_name, "Key": key}
            if version_id:
                kwargs["VersionId"] = version_id
            try:
                response = self.s3_client.get_object(**kwargs)
                payload = response["Body"].read()
                s3_meta = response.get("Metadata", {})
                etag = response.get("ETag", "").strip('"')
                content_type = response.get("ContentType", "application/octet-stream")
                last_modified = response.get("LastModified", datetime.now(timezone.utc))
                sha256_hash = s3_meta.get("sha256") or self._compute_sha256(payload)

                meta = ObjectMetadata(
                    provider=self.provider_name,
                    bucket=self._bucket_name,
                    key=key,
                    version_id=response.get("VersionId"),
                    size_bytes=len(payload),
                    content_type=content_type,
                    sha256_hash=sha256_hash,
                    last_modified=last_modified,
                    etag=etag,
                    custom_metadata=s3_meta,
                )
                return payload, meta
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code in ("NoSuchKey", "404"):
                    raise ObjectNotFoundError(f"Key '{key}' not found in S3 bucket '{self._bucket_name}'.")
                raise ProviderUnavailableError(f"AWS S3 download error: {str(e)}")
            except EndpointConnectionError as e:
                raise ProviderUnavailableError(f"AWS S3 unreachable: {str(e)}")

        return await asyncio.to_thread(_sync_download)

    async def delete_file(
        self,
        key: str,
        version_id: Optional[str] = None,
    ) -> bool:
        """Deletes an object version in S3."""
        def _sync_delete():
            kwargs = {"Bucket": self._bucket_name, "Key": key}
            if version_id:
                kwargs["VersionId"] = version_id
            try:
                self.s3_client.delete_object(**kwargs)
                return True
            except ClientError as e:
                logger.error(f"S3 DeleteObject failed: {e}")
                raise StorageProviderError(f"AWS S3 delete failed: {str(e)}")

        return await asyncio.to_thread(_sync_delete)

    async def get_metadata(
        self,
        key: str,
        version_id: Optional[str] = None,
    ) -> ObjectMetadata:
        """Retrieves HeadObject metadata from S3."""
        def _sync_head():
            kwargs = {"Bucket": self._bucket_name, "Key": key}
            if version_id:
                kwargs["VersionId"] = version_id
            try:
                response = self.s3_client.head_object(**kwargs)
                s3_meta = response.get("Metadata", {})
                return ObjectMetadata(
                    provider=self.provider_name,
                    bucket=self._bucket_name,
                    key=key,
                    version_id=response.get("VersionId"),
                    size_bytes=response.get("ContentLength", 0),
                    content_type=response.get("ContentType", "application/octet-stream"),
                    sha256_hash=s3_meta.get("sha256", ""),
                    last_modified=response.get("LastModified", datetime.now(timezone.utc)),
                    etag=response.get("ETag", "").strip('"'),
                    custom_metadata=s3_meta,
                )
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code in ("404", "NoSuchKey"):
                    raise ObjectNotFoundError(f"Key '{key}' not found in S3.")
                raise ProviderUnavailableError(f"AWS S3 HeadObject failed: {str(e)}")

        return await asyncio.to_thread(_sync_head)

    async def check_health(self) -> HealthStatus:
        """Executes a lightweight synthetic probe against AWS S3."""
        start_time = time.perf_counter()

        def _sync_check():
            try:
                self.s3_client.head_bucket(Bucket=self._bucket_name)
                latency = (time.perf_counter() - start_time) * 1000.0
                return HealthStatus(
                    provider=self.provider_name,
                    is_healthy=True,
                    latency_ms=round(latency, 2),
                    http_status=200,
                    details="S3 head_bucket probe succeeded.",
                )
            except ClientError as e:
                latency = (time.perf_counter() - start_time) * 1000.0
                status_code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 500)
                return HealthStatus(
                    provider=self.provider_name,
                    is_healthy=False,
                    latency_ms=round(latency, 2),
                    http_status=status_code,
                    details=f"AWS S3 ClientError: {str(e)}",
                )
            except Exception as e:
                latency = (time.perf_counter() - start_time) * 1000.0
                return HealthStatus(
                    provider=self.provider_name,
                    is_healthy=False,
                    latency_ms=round(latency, 2),
                    http_status=503,
                    details=f"AWS S3 Connection Error: {str(e)}",
                )

        return await asyncio.to_thread(_sync_check)

    async def list_versions(self, key: str) -> List[StorageObjectRef]:
        """Lists object versions in S3."""
        def _sync_list():
            try:
                response = self.s3_client.list_object_versions(Bucket=self._bucket_name, Prefix=key)
                versions = []
                for v in response.get("Versions", []):
                    if v["Key"] == key:
                        versions.append(
                            StorageObjectRef(
                                provider=self.provider_name,
                                bucket=self._bucket_name,
                                key=key,
                                version_id=v.get("VersionId"),
                                sha256_hash="",
                                size_bytes=v.get("Size", 0),
                                etag=v.get("ETag", "").strip('"'),
                                last_modified=v.get("LastModified", datetime.now(timezone.utc)),
                            )
                        )
                return versions
            except ClientError as e:
                raise StorageProviderError(f"Error listing S3 versions: {str(e)}")

        return await asyncio.to_thread(_sync_list)

    async def calculate_storage_usage(self) -> StorageMetrics:
        """Aggregates bucket size and calculates monthly storage cost."""
        def _sync_calc():
            try:
                paginator = self.s3_client.get_paginator("list_objects_v2")
                total_bytes = 0
                total_objects = 0
                for page in paginator.paginate(Bucket=self._bucket_name):
                    for obj in page.get("Contents", []):
                        total_bytes += obj.get("Size", 0)
                        total_objects += 1

                total_gb = total_bytes / (1024 ** 3)
                cost = total_gb * settings.AWS_STORAGE_PRICE_PER_GB_MONTH
                return StorageMetrics(
                    provider=self.provider_name,
                    bucket=self._bucket_name,
                    total_objects=total_objects,
                    total_bytes=total_bytes,
                    estimated_monthly_cost_usd=round(cost, 4),
                )
            except ClientError as e:
                raise StorageProviderError(f"Failed to calculate S3 usage: {str(e)}")

        return await asyncio.to_thread(_sync_calc)

    async def verify_integrity(
        self,
        key: str,
        expected_sha256: str,
        version_id: Optional[str] = None,
    ) -> IntegrityResult:
        """Verifies cryptographic integrity using stored metadata or full SHA-256 computation."""
        payload, meta = await self.download_file(key, version_id=version_id)
        actual_sha256 = self._compute_sha256(payload)
        is_valid = actual_sha256.lower() == expected_sha256.lower()

        return IntegrityResult(
            provider=self.provider_name,
            key=key,
            version_id=version_id,
            expected_sha256=expected_sha256,
            actual_sha256=actual_sha256,
            is_valid=is_valid,
            message="Checksum matches" if is_valid else f"Integrity violation: {actual_sha256} != {expected_sha256}",
        )

