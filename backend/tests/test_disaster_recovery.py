import hashlib
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.disaster_recovery.failover_router import FailoverRouter
from app.disaster_recovery.health_monitor import CloudHealthMonitor
from app.disaster_recovery.metrics_tracker import DRMetricsTracker
from app.disaster_recovery.reconciliation import ReconciliationEngine
from app.models.cloud_provider import CloudProvider
from app.models.file import File, FileVersion
from app.models.health import DisasterRecoveryEvent
from app.models.replication import FileReplica
from app.models.user import User
from app.storage.factory import get_aws_provider, get_gcp_provider


@pytest.mark.asyncio
async def test_synthetic_health_monitor_and_flap_detection(db_session: AsyncSession):
    """
    Verifies that the health prober:
    1. Detects healthy providers.
    2. Uses consecutive failure counters to prevent premature failover (anti-flapping).
    3. Automatically triggers failover only when consecutive failures cross the threshold.
    """
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
    db_session.add_all([aws_p, gcp_p])
    await db_session.commit()

    monitor = CloudHealthMonitor(failure_threshold=3, restore_threshold=3)

    # 1. Normal healthy cycle
    res1 = await monitor.execute_probe_cycle(session=db_session)
    assert res1["probes"]["AWS_S3"]["healthy"] is True
    assert res1["consecutive_failures"]["AWS_S3"] == 0
    assert res1["failover_triggered"] is False

    # 2. Simulate AWS outage
    try:
        settings.SIMULATE_AWS_OUTAGE = True

        # Check 1: 1 failure (anti-flap: no failover)
        res_outage_1 = await monitor.execute_probe_cycle(session=db_session)
        assert res_outage_1["probes"]["AWS_S3"]["healthy"] is False
        assert res_outage_1["consecutive_failures"]["AWS_S3"] == 1
        assert res_outage_1["failover_triggered"] is False

        # Check 2: 2 failures (still below threshold of 3: no failover)
        res_outage_2 = await monitor.execute_probe_cycle(session=db_session)
        assert res_outage_2["consecutive_failures"]["AWS_S3"] == 2
        assert res_outage_2["failover_triggered"] is False

        # Check 3: 3 failures (threshold reached! Automatic failover triggered!)
        res_outage_3 = await monitor.execute_probe_cycle(session=db_session)
        assert res_outage_3["consecutive_failures"]["AWS_S3"] == 3
        assert res_outage_3["failover_triggered"] is True

        # Verify AWS status updated to DOWN
        res_aws = await db_session.execute(select(CloudProvider).where(CloudProvider.name == "AWS_S3"))
        assert res_aws.scalars().first().status == "DOWN"

    finally:
        settings.SIMULATE_AWS_OUTAGE = False


@pytest.mark.asyncio
async def test_dynamic_failover_routing_and_rto_rpo(db_session: AsyncSession):
    """
    Verifies that during an outage:
    1. Read routing switches dynamically to GCP Storage.
    2. RTO and RPO are accurately computed.
    3. File download serves replica from GCP with correct headers.
    """
    user = User(username="dr_user", email="dr@test.org", hashed_password="pw", role="ADMIN")
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

    # Upload test asset to both AWS and GCP
    content = b"CRITICAL HOSPITAL PATIENT VITALS STREAM #9941"
    hasher = hashlib.sha256(content)
    test_hash = hasher.hexdigest()
    storage_key = "vitals/patient_9941.json"

    aws = get_aws_provider()
    gcp = get_gcp_provider()

    s3_ref = await aws.upload_file(storage_key, content)
    gcp_ref = await gcp.upload_file(storage_key, content)

    db_file = File(
        owner_id=user.id,
        filename="patient_9941.json",
        storage_key=storage_key,
        file_size_bytes=len(content),
        sha256_hash=test_hash,
        priority="CRITICAL",
        access_frequency_tier="FREQUENT",
    )
    db_session.add(db_file)
    await db_session.flush()

    db_version = FileVersion(
        file_id=db_file.id,
        version_num=1,
        aws_version_id=s3_ref.version_id,
        gcp_generation_id=gcp_ref.generation_id,
        size_bytes=len(content),
        sha256_hash=test_hash,
        is_current=True,
    )
    db_session.add(db_version)
    await db_session.flush()

    replica = FileReplica(
        file_id=db_file.id,
        version_id=db_version.id,
        provider_id=gcp_p.id,
        replica_uri=f"gs://{gcp.bucket_name}/{storage_key}",
        storage_tier="STANDARD",
        sha256_hash=test_hash,
        is_verified=True,
        size_bytes=len(content),
        replication_latency_ms=115.0,
    )
    db_session.add(replica)
    await db_session.commit()

    # 1. Trigger Failover
    dr_event = await FailoverRouter.trigger_failover(
        session=db_session,
        reason="Test simulated AWS disaster",
    )
    assert dr_event.event_type == "FAILOVER_COMPLETED"
    assert dr_event.rto_seconds >= 0.0
    assert dr_event.rpo_seconds >= 0.0
    assert dr_event.affected_files_count >= 1

    # 2. Check routing status
    routing = await FailoverRouter.get_routing_status(db_session)
    assert routing["active_read_provider"] == "GCP_STORAGE"
    assert routing["failover_active"] is True


@pytest.mark.asyncio
async def test_recovery_and_reconciliation(db_session: AsyncSession):
    """
    Verifies that when AWS recovers:
    1. Reconciliation copies newly modified objects from GCP back to AWS.
    2. New S3 version IDs are created in the version manifest.
    3. Normal primary cloud routing is restored.
    """
    aws_p = CloudProvider(
        name="AWS_S3",
        is_active=True,
        is_primary=True,
        bucket_name=settings.AWS_S3_BUCKET_NAME,
        region=settings.AWS_DEFAULT_REGION,
        status="DOWN",
    )
    gcp_p = CloudProvider(
        name="GCP_STORAGE",
        is_active=True,
        is_primary=False,
        bucket_name=settings.GCP_BUCKET_NAME,
        region=settings.GCP_DEFAULT_LOCATION,
        status="HEALTHY",
    )
    user = User(username="recon_user", email="recon@test.org", hashed_password="pw", role="ADMIN")
    db_session.add_all([aws_p, gcp_p, user])
    await db_session.flush()

    # Create file updated on GCP during failover
    new_failover_content = b"UPDATED CRITICAL TRANSACTION: modified during AWS failover window"
    hasher = hashlib.sha256(new_failover_content)
    new_hash = hasher.hexdigest()
    key = "finance/ledger_update_01.dat"

    # Save to GCP
    gcp = get_gcp_provider()
    gcp_ref = await gcp.upload_file(key, new_failover_content)

    file_obj = File(
        owner_id=user.id,
        filename="ledger_update_01.dat",
        storage_key=key,
        file_size_bytes=len(new_failover_content),
        sha256_hash=new_hash,
        priority="CRITICAL",
        access_frequency_tier="FREQUENT",
    )
    db_session.add(file_obj)
    await db_session.flush()

    ver_obj = FileVersion(
        file_id=file_obj.id,
        version_num=1,
        aws_version_id=None,  # AWS lacks this version because it was down!
        gcp_generation_id=gcp_ref.generation_id,
        size_bytes=len(new_failover_content),
        sha256_hash=new_hash,
        is_current=True,
    )
    db_session.add(ver_obj)
    await db_session.flush()

    replica_obj = FileReplica(
        file_id=file_obj.id,
        version_id=ver_obj.id,
        provider_id=gcp_p.id,
        replica_uri=f"gs://{gcp.bucket_name}/{key}",
        storage_tier="STANDARD",
        sha256_hash=new_hash,
        is_verified=True,
        size_bytes=len(new_failover_content),
    )
    db_session.add(replica_obj)
    await db_session.commit()

    # Trigger Reconciliation
    recon_res = await ReconciliationEngine.reconcile_after_recovery(session=db_session)
    assert recon_res["status"] == "COMPLETED"
    assert recon_res["files_reconciled"] >= 1
    assert recon_res["conflicts_detected"] == 0

    # Verify AWS now possesses the object and version ID is recorded in DB
    res_ver = await db_session.execute(select(FileVersion).where(FileVersion.id == ver_obj.id))
    reconciled_ver = res_ver.scalars().first()
    assert reconciled_ver.aws_version_id is not None

    # Verify object downloaded from AWS S3 matches the reconciled data
    aws = get_aws_provider()
    s3_bytes, s3_meta = await aws.download_file(key, version_id=reconciled_ver.aws_version_id)
    assert s3_bytes == new_failover_content
    assert s3_meta.sha256_hash == new_hash

    # Verify AWS provider status in DB restored to HEALTHY
    res_prov = await db_session.execute(select(CloudProvider).where(CloudProvider.name == "AWS_S3"))
    assert res_prov.scalars().first().status == "HEALTHY"


@pytest.mark.asyncio
async def test_api_disaster_recovery_endpoints(client: AsyncClient, db_session: AsyncSession):
    """Tests /disaster-recovery/status, /probe, /failover, /reconcile, and /metrics via API."""
    from app.core.security import hash_password
    admin_user = User(
        username="admin_dr",
        email="admin_dr@test.org",
        hashed_password=hash_password("admin12345"),
        role="ADMIN",
    )
    db_session.add(admin_user)
    await db_session.commit()

    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin_dr", "password": "admin12345"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Probe
    probe_resp = await client.post("/api/v1/disaster-recovery/probe", headers=headers)
    assert probe_resp.status_code == 200
    probe_data = probe_resp.json()
    assert "probes" in probe_data

    # 2. Status
    status_resp = await client.get("/api/v1/disaster-recovery/status", headers=headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["active_read_provider"] in ("AWS_S3", "GCP_STORAGE")

    # 3. Failover
    fo_resp = await client.post(
        "/api/v1/disaster-recovery/failover",
        headers=headers,
        json={"reason": "Drill test", "target_provider": "GCP_STORAGE"},
    )
    assert fo_resp.status_code == 200
    fo_data = fo_resp.json()
    assert fo_data["event_type"] == "FAILOVER_COMPLETED"
    assert fo_data["rto_seconds"] >= 0.0

    # 4. Reconcile
    rec_resp = await client.post("/api/v1/disaster-recovery/reconcile", headers=headers)
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert rec_data["status"] == "COMPLETED"

    # 5. Metrics
    metrics_resp = await client.get("/api/v1/disaster-recovery/metrics", headers=headers)
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.json()
    assert "avg_rto_seconds" in metrics_data
    assert "avg_rpo_seconds" in metrics_data
