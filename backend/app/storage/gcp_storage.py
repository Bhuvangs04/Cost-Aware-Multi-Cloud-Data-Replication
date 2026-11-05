import asyncio
from datetime import datetime, timezone
import hashlib
import os
import time
from typing import BinaryIO, Dict, List, Optional, Tuple, Union
from google.api_core.exceptions import GoogleAPIError, NotFound
from google.cloud import storage

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


class GCPStorageAdapter(ICloudStorageProvider):
    """Google Cloud Storage (GCS) Adapter using the official google-cloud-storage SDK."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        project_id: Optional[str] = None,
        service_account_path: Optional[str] = None,
    ):
        self._bucket_name = bucket_name or settings.GCP_BUCKET_NAME
        self._project_id = project_id or settings.GCP_PROJECT_ID

        # Resolve credentials path
        cred_path = (
            service_account_path
            or settings.GCP_SERVICE_ACCOUNT_KEY_PATH
            or ("serviceAccount.json" if os.path.exists("serviceAccount.json") else None)
        )

        try:
            if cred_path and os.path.exists(cred_path):
                self.client = storage.Client.from_service_account_json(cred_path)
            elif self._project_id:
                self.client = storage.Client(project=self._project_id)
            else:
                self.client = storage.Client.create_anonymous_client()
        except Exception as e:
            logger.warning(f"GCP Storage Client initialized in fallback mode: {e}")
            self.client = None

    @property
    def provider_name(self) -> str:
        return "GCP_STORAGE"

    @property
    def bucket_name(self) -> str:
        return self._bucket_name

    def _compute_sha256(self, data: bytes) -> str:
        hasher = hashlib.sha256()
        hasher.update(data)
        return hasher.hexdigest()

    def _get_bucket(self):
        if not self.client:
            raise ProviderUnavailableError("GCP client is not configured with valid credentials.")
        return self.client.bucket(self._bucket_name)

    async def upload_file(
        self,
        key: str,
        data: Union[bytes, BinaryIO],
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> StorageObjectRef:
        """Uploads an object to GCS and captures the object generation number."""
        raw_bytes = data if isinstance(data, bytes) else data.read()
        sha256_hash = self._compute_sha256(raw_bytes)
        size_bytes = len(raw_bytes)

        req_metadata = metadata.copy() if metadata else {}
        req_metadata["sha256"] = sha256_hash

        def _sync_upload():
            try:
                bucket = self._get_bucket()
                blob = bucket.blob(key)
                blob.metadata = req_metadata
                blob.upload_from_string(raw_bytes, content_type=content_type, timeout=10)
                try:
                    blob.reload(timeout=10)
                except Exception:
                    pass

                return (
                    str(blob.generation) if blob.generation else None,
                    blob.crc32c,
                    blob.updated or datetime.now(timezone.utc),
                )
            except Exception as e:
                logger.error(f"GCS upload failed for '{key}': {e}")
                raise ProviderUnavailableError(f"GCP Storage upload failed: {str(e)}")

        generation_id, crc32c, updated = await asyncio.to_thread(_sync_upload)

        return StorageObjectRef(
            provider=self.provider_name,
            bucket=self._bucket_name,
            key=key,
            generation_id=generation_id,
            sha256_hash=sha256_hash,
            size_bytes=size_bytes,
            etag=crc32c,
            last_modified=updated,
            custom_metadata=req_metadata,
        )

    async def download_file(
        self,
        key: str,
        version_id: Optional[str] = None,
    ) -> Tuple[bytes, ObjectMetadata]:
        """Downloads an object generation from GCS."""
        def _sync_download():
            try:
                bucket = self._get_bucket()
                generation = int(version_id) if version_id else None
                blob = bucket.blob(key, generation=generation)
                payload = blob.download_as_bytes()
                blob.reload()

                gcs_meta = blob.metadata or {}
                sha256_hash = gcs_meta.get("sha256") or self._compute_sha256(payload)

                meta = ObjectMetadata(
                    provider=self.provider_name,
                    bucket=self._bucket_name,
                    key=key,
                    version_id=str(blob.generation) if blob.generation else None,
                    size_bytes=len(payload),
                    content_type=blob.content_type or "application/octet-stream",
                    sha256_hash=sha256_hash,
                    last_modified=blob.updated or datetime.now(timezone.utc),
                    etag=blob.crc32c,
                    custom_metadata=gcs_meta,
                )
                return payload, meta
            except NotFound:
                raise ObjectNotFoundError(f"Key '{key}' not found in GCP bucket '{self._bucket_name}'.")
            except GoogleAPIError as e:
                raise ProviderUnavailableError(f"GCP Storage download failed: {str(e)}")

        return await asyncio.to_thread(_sync_download)

    async def delete_file(
        self,
        key: str,
        version_id: Optional[str] = None,
    ) -> bool:
        """Deletes a generation from GCS."""
        def _sync_delete():
            try:
                bucket = self._get_bucket()
                generation = int(version_id) if version_id else None
                blob = bucket.blob(key, generation=generation)
                blob.delete()
                return True
            except NotFound:
                return True
            except GoogleAPIError as e:
                raise StorageProviderError(f"GCP Storage delete error: {str(e)}")

        return await asyncio.to_thread(_sync_delete)

    async def get_metadata(
        self,
        key: str,
        version_id: Optional[str] = None,
    ) -> ObjectMetadata:
        """Retrieves blob metadata from GCS."""
        def _sync_meta():
            try:
                bucket = self._get_bucket()
                generation = int(version_id) if version_id else None
                blob = bucket.blob(key, generation=generation)
                blob.reload()
                gcs_meta = blob.metadata or {}

                return ObjectMetadata(
                    provider=self.provider_name,
                    bucket=self._bucket_name,
                    key=key,
                    version_id=str(blob.generation) if blob.generation else None,
                    size_bytes=blob.size or 0,
                    content_type=blob.content_type or "application/octet-stream",
                    sha256_hash=gcs_meta.get("sha256", ""),
                    last_modified=blob.updated or datetime.now(timezone.utc),
                    etag=blob.crc32c,
                    custom_metadata=gcs_meta,
                )
            except NotFound:
                raise ObjectNotFoundError(f"Key '{key}' not found in GCP Storage.")
            except GoogleAPIError as e:
                raise ProviderUnavailableError(f"GCP Storage metadata check failed: {str(e)}")

        return await asyncio.to_thread(_sync_meta)

    async def check_health(self) -> HealthStatus:
        """Performs a synthetic health check against the GCP bucket."""
        start_time = time.perf_counter()

        def _sync_health():
            try:
                bucket = self._get_bucket()
                bucket.reload()
                latency = (time.perf_counter() - start_time) * 1000.0
                return HealthStatus(
                    provider=self.provider_name,
                    is_healthy=True,
                    latency_ms=round(latency, 2),
                    http_status=200,
                    details="GCS bucket health probe succeeded.",
                )
            except Exception as e:
                latency = (time.perf_counter() - start_time) * 1000.0
                return HealthStatus(
                    provider=self.provider_name,
                    is_healthy=False,
                    latency_ms=round(latency, 2),
                    http_status=503,
                    details=f"GCP Storage probe failed: {str(e)}",
                )

        return await asyncio.to_thread(_sync_health)

    async def list_versions(self, key: str) -> List[StorageObjectRef]:
        """Lists all generations of an object in GCS."""
        def _sync_versions():
            try:
                bucket = self._get_bucket()
                blobs = bucket.list_blobs(prefix=key, versions=True)
                results = []
                for b in blobs:
                    if b.name == key:
                        results.append(
                            StorageObjectRef(
                                provider=self.provider_name,
                                bucket=self._bucket_name,
                                key=key,
                                generation_id=str(b.generation) if b.generation else None,
                                sha256_hash=b.metadata.get("sha256", "") if b.metadata else "",
                                size_bytes=b.size or 0,
                                etag=b.crc32c,
                                last_modified=b.updated or datetime.now(timezone.utc),
                            )
                        )
                return results
            except GoogleAPIError as e:
                raise StorageProviderError(f"GCP list versions error: {str(e)}")

        return await asyncio.to_thread(_sync_versions)

    async def calculate_storage_usage(self) -> StorageMetrics:
        """Aggregates all stored bytes and calculates projected monthly cost."""
        def _sync_calc():
            try:
                bucket = self._get_bucket()
                blobs = bucket.list_blobs()
                total_bytes = 0
                total_objects = 0
                for b in blobs:
                    total_bytes += b.size or 0
                    total_objects += 1

                total_gb = total_bytes / (1024 ** 3)
                cost = total_gb * settings.GCP_STORAGE_PRICE_PER_GB_MONTH
                return StorageMetrics(
                    provider=self.provider_name,
                    bucket=self._bucket_name,
                    total_objects=total_objects,
                    total_bytes=total_bytes,
                    estimated_monthly_cost_usd=round(cost, 4),
                )
            except GoogleAPIError as e:
                raise StorageProviderError(f"Failed to calculate GCS usage: {str(e)}")

        return await asyncio.to_thread(_sync_calc)

    async def verify_integrity(
        self,
        key: str,
        expected_sha256: str,
        version_id: Optional[str] = None,
    ) -> IntegrityResult:
        """Verifies cryptographic hash of the object downloaded from GCS."""
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

