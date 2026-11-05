import hashlib
import io
import time
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ObjectNotFoundError, ProviderUnavailableError
from app.models.file import File
from app.models.user import User
from app.storage.factory import get_aws_provider, get_gcp_provider
from app.storage.simulation_interceptor import SimulatedStorageInterceptor


@pytest.mark.asyncio
async def test_storage_adapter_crud_and_integrity(tmp_path):
    """
    Tests complete lifecycle across storage abstraction:
    Upload -> Metadata -> Download -> Integrity Verification -> Versioning -> Usage -> Deletion.
    """
    # Create isolated simulated provider instance
    provider = SimulatedStorageInterceptor(
        provider_name="AWS_S3",
        bucket_name="test-s3-bucket",
        base_dir=str(tmp_path),
    )

    test_content = b"Research dataset: Multi-cloud disaster recovery test payload #12345"
    hasher = hashlib.sha256()
    hasher.update(test_content)
    expected_sha256 = hasher.hexdigest()

    test_key = "experiments/dataset_001.bin"

    # 1. Upload File
    ref1 = await provider.upload_file(
        key=test_key,
        data=test_content,
        content_type="application/octet-stream",
        metadata={"research_lead": "distributed_systems_lab"},
    )
    assert ref1.key == test_key
    assert ref1.sha256_hash == expected_sha256
    assert ref1.size_bytes == len(test_content)
    assert ref1.version_id is not None

    # 2. Upload Second Version to Same Key
    version_2_content = test_content + b" -- Updated Version 2"
    ref2 = await provider.upload_file(key=test_key, data=version_2_content)
    assert ref2.version_id != ref1.version_id
    assert ref2.size_bytes == len(version_2_content)

    # 3. List Versions
    versions = await provider.list_versions(test_key)
    assert len(versions) == 2
    assert versions[0].version_id == ref2.version_id

    # 4. Get Metadata
    meta = await provider.get_metadata(test_key, version_id=ref1.version_id)
    assert meta.size_bytes == len(test_content)
    assert meta.sha256_hash == expected_sha256
    assert meta.custom_metadata.get("research_lead") == "distributed_systems_lab"

    # 5. Download Specific Version (Version 1)
    downloaded_bytes_v1, meta_v1 = await provider.download_file(test_key, version_id=ref1.version_id)
    assert downloaded_bytes_v1 == test_content
    assert meta_v1.sha256_hash == expected_sha256

    # 6. Download Latest Version (Version 2)
    downloaded_latest, meta_latest = await provider.download_file(test_key)
    assert downloaded_latest == version_2_content

    # 7. Cryptographic Integrity Verification
    integrity = await provider.verify_integrity(
        key=test_key,
        expected_sha256=expected_sha256,
        version_id=ref1.version_id,
    )
    assert integrity.is_valid is True
    assert integrity.actual_sha256 == expected_sha256

    # Verify failure on tampered hash
    bad_integrity = await provider.verify_integrity(
        key=test_key,
        expected_sha256="badhash0000000000000000000000000000000000000000000000000000000000",
        version_id=ref1.version_id,
    )
    assert bad_integrity.is_valid is False

    # 8. Calculate Storage Usage
    usage = await provider.calculate_storage_usage()
    assert usage.total_objects == 2
    assert usage.total_bytes == len(test_content) + len(version_2_content)
    assert usage.estimated_monthly_cost_usd >= 0.0

    # 9. Health Check
    health = await provider.check_health()
    assert health.is_healthy is True
    assert health.http_status == 200

    # 10. Delete specific version
    deleted = await provider.delete_file(test_key, version_id=ref1.version_id)
    assert deleted is True

    # 11. Delete entire object
    deleted_all = await provider.delete_file(test_key)
    assert deleted_all is True


@pytest.mark.asyncio
async def test_gcp_storage_adapter_simulation(tmp_path):
    """Verifies GCPStorageAdapter semantics and generation handling in simulated mode."""
    gcp_provider = SimulatedStorageInterceptor(
        provider_name="GCP_STORAGE",
        bucket_name="test-gcp-replica-bucket",
        base_dir=str(tmp_path),
    )

    data = b"GCP secondary replica stream test"
    ref = await gcp_provider.upload_file(key="replicas/data.csv", data=data)

    assert ref.provider == "GCP_STORAGE"
    assert ref.generation_id is not None

    payload, meta = await gcp_provider.download_file("replicas/data.csv")
    assert payload == data
    assert meta.provider == "GCP_STORAGE"


@pytest.mark.asyncio
async def test_fault_injections_and_tamper_detection(tmp_path):
    """Verifies simulated cloud outages, injected latency, and cryptographic corruption detection."""
    provider = SimulatedStorageInterceptor(
        provider_name="AWS_S3",
        bucket_name="test-fault-bucket",
        base_dir=str(tmp_path),
    )

    test_bytes = b"Tamper resilience test"
    hasher = hashlib.sha256(test_bytes)
    correct_hash = hasher.hexdigest()
    ref = await provider.upload_file("secure_file.txt", test_bytes)

    # 1. Test Injected Outage
    try:
        settings.SIMULATE_AWS_OUTAGE = True
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await provider.download_file("secure_file.txt")
        assert "Cloud Outage" in str(exc_info.value)

        health = await provider.check_health()
        assert health.is_healthy is False
        assert health.http_status == 503
    finally:
        settings.SIMULATE_AWS_OUTAGE = False

    # 2. Test Injected Network Latency
    try:
        settings.SIMULATED_AWS_LATENCY_MS = 120.0
        start = time.perf_counter()
        await provider.download_file("secure_file.txt")
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms >= 100.0  # Measured injected delay
    finally:
        settings.SIMULATED_AWS_LATENCY_MS = 0.0

    # 3. Test Injected Checksum Tampering
    try:
        settings.SIMULATE_CORRUPT_CHECKSUM = True
        integrity = await provider.verify_integrity("secure_file.txt", expected_sha256=correct_hash)
        assert integrity.is_valid is False
        assert "Integrity violation" in integrity.message
    finally:
        settings.SIMULATE_CORRUPT_CHECKSUM = False


@pytest.mark.asyncio
async def test_api_file_upload_and_download_flow(client: AsyncClient, db_session: AsyncSession):
    """Tests multipart file upload and download endpoints through FastAPI with real storage integration."""
    # 1. Register and login
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "upload_tester", "email": "uploader@test.edu", "password": "Password123!"},
    )
    assert reg_resp.status_code == 201

    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "upload_tester", "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload file via multipart/form-data
    test_file_content = b"Academic paper preprint: Efficient Multi-Cloud Data Replication Strategies."
    files = {"file": ("research_paper.pdf", io.BytesIO(test_file_content), "application/pdf")}
    data = {"priority": "HIGH", "access_frequency_tier": "FREQUENT", "tags": "disaster-recovery,research"}

    upload_resp = await client.post("/api/v1/files/upload", headers=headers, files=files, data=data)
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()

    assert upload_data["filename"] == "research_paper.pdf"
    assert upload_data["priority"] == "HIGH"
    assert upload_data["upload_status"] == "stored_aws"
    file_id = upload_data["file_id"]

    # 3. Retrieve metadata
    meta_resp = await client.get(f"/api/v1/files/{file_id}", headers=headers)
    assert meta_resp.status_code == 200
    meta_data = meta_resp.json()
    assert meta_data["file_size_bytes"] == len(test_file_content)
    assert len(meta_data["versions"]) == 1

    # 4. Download file
    download_resp = await client.get(f"/api/v1/files/{file_id}/download", headers=headers)
    assert download_resp.status_code == 200
    assert download_resp.content == test_file_content
    assert download_resp.headers["x-source-cloud"] == "AWS_S3"
    assert download_resp.headers["x-failover-active"] == "false"

    # 5. Soft Delete
    del_resp = await client.delete(f"/api/v1/files/{file_id}", headers=headers)
    assert del_resp.status_code == 200

