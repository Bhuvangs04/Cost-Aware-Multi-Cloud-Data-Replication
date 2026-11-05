import hashlib
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import ChecksumMismatchError, ProviderUnavailableError
from app.models.cloud_provider import CloudProvider
from app.models.cost import CostRecord
from app.models.file import File, FileVersion
from app.models.replication import FileReplica, ReplicationJob, ReplicationPolicy
from app.models.user import User
from app.replication.engine import execute_replication_pipeline
from app.replication.verifier import CrossCloudVerifier
from app.storage.factory import get_aws_provider, get_gcp_provider


@pytest.mark.asyncio
async def test_cross_cloud_replication_pipeline(db_session: AsyncSession):
    """
    Verifies that the asynchronous replication engine transfers files from AWS to GCP,
    executes cryptographic SHA-256 verification, and records cost and replica metadata.
    """
    # 1. Setup User & Providers
    user = User(
        username="replication_researcher",
        email="rep@research.org",
        hashed_password="hashed_pw",
        role="RESEARCHER",
    )
    aws_p = CloudProvider(
        name="AWS_S3",
        is_active=True,
        is_primary=True,
        bucket_name=settings.AWS_S3_BUCKET_NAME,
        region=settings.AWS_DEFAULT_REGION,
        status="HEALTHY",
    )
    gcp_p = CloudProvider(
        name="GCP_STORAGE",
        is_active=True,
        is_primary=False,
        bucket_name=settings.GCP_BUCKET_NAME,
        region=settings.GCP_DEFAULT_LOCATION,
        status="HEALTHY",
    )
    db_session.add_all([user, aws_p, gcp_p])
    await db_session.flush()

    # 2. Upload file to Primary Storage (AWS S3)
    test_content = b"CRITICAL RESEARCH PAYLOAD: Seismic activity sensor log batch #8829"
    hasher = hashlib.sha256()
    hasher.update(test_content)
    expected_sha256 = hasher.hexdigest()
    storage_key = "sensors/seismic_batch_8829.dat"

    aws_provider = get_aws_provider()
    s3_ref = await aws_provider.upload_file(storage_key, test_content)

    # 3. Create File, Version, Policy, and Job in DB
    policy = ReplicationPolicy(
        name="Adaptive Priority Policy",
        strategy_type="COST_AWARE_ADAPTIVE",
        target_rpo_seconds=300,
        target_rto_seconds=60,
        max_budget_monthly_usd=100.0,
        weights_json="{}",
        threshold_score=0.5,
    )
    db_session.add(policy)
    await db_session.flush()

    db_file = File(
        owner_id=user.id,
        filename="seismic_batch_8829.dat",
        storage_key=storage_key,
        file_size_bytes=len(test_content),
        content_type="application/octet-stream",
        sha256_hash=expected_sha256,
        priority="CRITICAL",
        access_frequency_tier="FREQUENT",
    )
    db_session.add(db_file)
    await db_session.flush()

    db_version = FileVersion(
        file_id=db_file.id,
        version_num=1,
        aws_version_id=s3_ref.version_id,
        size_bytes=len(test_content),
        sha256_hash=expected_sha256,
        is_current=True,
    )
    db_session.add(db_version)
    await db_session.flush()

    job = ReplicationJob(
        file_id=db_file.id,
        version_id=db_version.id,
        policy_id=policy.id,
        strategy_used="COST_AWARE_ADAPTIVE",
        status="PENDING",
        idempotency_key=f"rep_{db_file.id}_{db_version.id}",
    )
    db_session.add(job)
    await db_session.commit()

    # 4. Execute Replication Pipeline
    result = await execute_replication_pipeline(job.id, session=db_session)

    assert result["status"] == "COMPLETED"
    assert result["job_id"] == job.id
    assert result["gcp_generation_id"] is not None
    assert result["latency_ms"] >= 0.0

    # 5. Verify Database Records
    res_job = await db_session.execute(select(ReplicationJob).where(ReplicationJob.id == job.id))
    completed_job = res_job.scalars().first()
    assert completed_job.status == "COMPLETED"
    assert completed_job.completed_at is not None

    res_replica = await db_session.execute(
        select(FileReplica).where(FileReplica.file_id == db_file.id)
    )
    replica = res_replica.scalars().first()
    assert replica is not None
    assert replica.is_verified is True
    assert replica.sha256_hash == expected_sha256
    assert replica.size_bytes == len(test_content)
    assert replica.replication_latency_ms > 0
    assert replica.transfer_cost_usd >= 0.0

    # Verify GCP object exists
    gcp_provider = get_gcp_provider()
    gcp_bytes, gcp_meta = await gcp_provider.download_file(
        storage_key, version_id=result["gcp_generation_id"]
    )
    assert gcp_bytes == test_content
    assert gcp_meta.sha256_hash == expected_sha256


@pytest.mark.asyncio
async def test_replication_idempotency(db_session: AsyncSession):
    """Verifies that calling the pipeline on an already completed job is a no-op."""
    user = User(
        username="idem_user",
        email="idem@test.org",
        hashed_password="pw",
        role="RESEARCHER",
    )
    db_session.add(user)
    await db_session.flush()

    file_obj = File(
        owner_id=user.id,
        filename="idem_sample.txt",
        storage_key="test/idem_sample.txt",
        file_size_bytes=100,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        priority="LOW",
        access_frequency_tier="RARE",
    )
    db_session.add(file_obj)
    await db_session.flush()

    ver_obj = FileVersion(
        file_id=file_obj.id,
        version_num=1,
        aws_version_id="s3-v1",
        size_bytes=100,
        sha256_hash=file_obj.sha256_hash,
        is_current=True,
    )
    db_session.add(ver_obj)
    await db_session.flush()

    job = ReplicationJob(
        file_id=file_obj.id,
        version_id=ver_obj.id,
        strategy_used="FULL",
        status="COMPLETED",
        idempotency_key="idempotent_test_key_001",
    )
    db_session.add(job)
    await db_session.commit()

    res = await execute_replication_pipeline(job.id, session=db_session)
    assert res["status"] == "ALREADY_COMPLETED"


@pytest.mark.asyncio
async def test_replication_failure_handling(db_session: AsyncSession):
    """Verifies that cloud failures during replication are captured and job status updated to FAILED."""
    user = User(
        username="failure_tester",
        email="fail@test.edu",
        hashed_password="pw",
        role="OPERATOR",
    )
    db_session.add(user)
    await db_session.flush()

    storage_key = "logs/fail_test.log"
    aws_provider = get_aws_provider()
    s3_ref = await aws_provider.upload_file(storage_key, b"Failure test data")

    db_file = File(
        owner_id=user.id,
        filename="fail_test.log",
        storage_key=storage_key,
        file_size_bytes=17,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        priority="CRITICAL",
        access_frequency_tier="FREQUENT",
    )
    db_session.add(db_file)
    await db_session.flush()

    db_version = FileVersion(
        file_id=db_file.id,
        version_num=1,
        aws_version_id=s3_ref.version_id,
        size_bytes=17,
        sha256_hash=db_file.sha256_hash,
        is_current=True,
    )
    db_session.add(db_version)
    await db_session.flush()

    job = ReplicationJob(
        file_id=db_file.id,
        version_id=db_version.id,
        strategy_used="PRIORITY",
        status="PENDING",
        idempotency_key="fail_job_idem_001",
    )
    db_session.add(job)
    await db_session.commit()

    # Simulate GCP Outage
    try:
        settings.SIMULATE_GCP_OUTAGE = True
        with pytest.raises(ProviderUnavailableError):
            await execute_replication_pipeline(job.id, session=db_session)

        # Re-fetch job to verify error state
        res_job = await db_session.execute(select(ReplicationJob).where(ReplicationJob.id == job.id))
        failed_job = res_job.scalars().first()
        assert failed_job.status == "FAILED"
        assert failed_job.retry_count == 1
        assert "Cloud Outage" in failed_job.error_message
    finally:
        settings.SIMULATE_GCP_OUTAGE = False
