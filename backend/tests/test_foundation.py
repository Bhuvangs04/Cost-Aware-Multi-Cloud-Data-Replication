import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.models.cloud_provider import CloudProvider
from app.models.cost import CostRecord
from app.models.experiment import ExperimentResult, ExperimentRun
from app.models.file import File, FileVersion
from app.models.health import CloudHealthLog, DisasterRecoveryEvent
from app.models.replication import FileReplica, ReplicationJob, ReplicationPolicy
from app.models.user import User


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    """Verifies liveness, readiness, and Prometheus metrics endpoints."""
    # Liveness
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"

    # Readiness
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"

    # Prometheus Metrics
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text


@pytest.mark.asyncio
async def test_security_utilities():
    """Verifies password hashing, bcrypt verification, and JWT generation/decoding."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

    token = create_access_token(subject="research_user", role="RESEARCHER")
    assert isinstance(token, str)
    payload = decode_access_token(token)
    assert payload["sub"] == "research_user"
    assert payload["role"] == "RESEARCHER"


@pytest.mark.asyncio
async def test_all_normalized_models(db_session: AsyncSession):
    """Verifies table creation, integrity constraints, and relationships across all models."""
    # 1. User
    user = User(
        username="researcher1",
        email="researcher1@example.com",
        hashed_password=hash_password("password123"),
        role="RESEARCHER",
    )
    db_session.add(user)
    await db_session.flush()
    assert user.id is not None

    # 2. Cloud Providers
    aws_provider = CloudProvider(
        name="AWS_S3",
        is_active=True,
        is_primary=True,
        bucket_name="aws-primary-bucket",
        region="us-east-1",
        status="HEALTHY",
    )
    gcp_provider = CloudProvider(
        name="GCP_STORAGE",
        is_active=True,
        is_primary=False,
        bucket_name="gcp-replica-bucket",
        region="US",
        status="HEALTHY",
    )
    db_session.add_all([aws_provider, gcp_provider])
    await db_session.flush()
    assert aws_provider.id is not None
    assert gcp_provider.id is not None

    # 3. File & FileVersion
    file_obj = File(
        owner_id=user.id,
        filename="genomic_dataset_sample.h5",
        storage_key="uploads/genomic_dataset_sample.h5",
        file_size_bytes=104857600,  # 100 MB
        content_type="application/x-hdf5",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        priority="CRITICAL",
        access_frequency_tier="FREQUENT",
    )
    db_session.add(file_obj)
    await db_session.flush()

    file_ver = FileVersion(
        file_id=file_obj.id,
        version_num=1,
        aws_version_id="s3-v1-abc",
        size_bytes=104857600,
        sha256_hash=file_obj.sha256_hash,
        is_current=True,
    )
    db_session.add(file_ver)
    await db_session.flush()

    # 4. Replication Policy & Job
    policy = ReplicationPolicy(
        name="Test Adaptive Policy",
        strategy_type="COST_AWARE_ADAPTIVE",
        target_rpo_seconds=300,
        target_rto_seconds=60,
        max_budget_monthly_usd=150.0,
        weights_json='{"w_p": 0.4, "w_a": 0.2, "w_r": 0.2, "w_s": 0.1, "w_c": 0.1}',
        threshold_score=0.6,
    )
    db_session.add(policy)
    await db_session.flush()

    job = ReplicationJob(
        file_id=file_obj.id,
        version_id=file_ver.id,
        policy_id=policy.id,
        strategy_used="COST_AWARE_ADAPTIVE",
        status="COMPLETED",
        decision_score=0.88,
        decision_reason='{"action": "REPLICATE_IMMEDIATELY", "reason": "Critical priority bypass"}',
        idempotency_key=f"idem_{file_obj.id}_{file_ver.id}",
    )
    db_session.add(job)
    await db_session.flush()

    # 5. FileReplica
    replica = FileReplica(
        file_id=file_obj.id,
        version_id=file_ver.id,
        provider_id=gcp_provider.id,
        replica_uri="gs://gcp-replica-bucket/uploads/genomic_dataset_sample.h5",
        storage_tier="STANDARD",
        sha256_hash=file_obj.sha256_hash,
        is_verified=True,
        size_bytes=104857600,
        replication_latency_ms=184.2,
        transfer_cost_usd=0.009,
        storage_cost_monthly_usd=0.002,
    )
    db_session.add(replica)
    await db_session.flush()

    # 6. Disaster Recovery & Health Log
    health_log = CloudHealthLog(
        provider_id=aws_provider.id,
        check_type="SYNTHETIC_HEAD",
        status="HEALTHY",
        latency_ms=12.4,
        http_status_code=200,
        is_simulated=True,
    )
    dr_event = DisasterRecoveryEvent(
        event_type="OUTAGE_DETECTED",
        failed_provider_id=aws_provider.id,
        failover_provider_id=gcp_provider.id,
        rto_seconds=0.34,
        rpo_seconds=5.2,
        affected_files_count=1,
    )
    db_session.add_all([health_log, dr_event])
    await db_session.flush()

    # 7. Cost Records
    cost_rec = CostRecord(
        record_date=dr_event.created_at.date(),
        provider_id=gcp_provider.id,
        file_id=file_obj.id,
        storage_cost_usd=0.002,
        egress_transfer_cost_usd=0.009,
        api_operation_cost_usd=0.00001,
        cumulative_savings_vs_full_usd=0.0,
        is_simulated=True,
    )
    db_session.add(cost_rec)
    await db_session.flush()

    # 8. Experiment Run & Results
    run = ExperimentRun(
        name="Adaptive vs Full Replication Test",
        strategy="COST_AWARE_ADAPTIVE",
        workload_profile="UNIFORM",
        total_files=10,
        total_bytes=1048576000,
        status="COMPLETED",
    )
    db_session.add(run)
    await db_session.flush()

    exp_res = ExperimentResult(
        experiment_run_id=run.id,
        metric_name="total_replication_cost",
        metric_value=0.11,
        unit="USD",
    )
    db_session.add(exp_res)
    await db_session.commit()

    # Query verification
    res = await db_session.execute(select(File).where(File.id == file_obj.id))
    fetched_file = res.scalars().first()
    assert fetched_file is not None
    assert fetched_file.filename == "genomic_dataset_sample.h5"
    assert fetched_file.priority == "CRITICAL"


@pytest.mark.asyncio
async def test_auth_and_api_flow(client: AsyncClient, db_session: AsyncSession):
    """Tests registration, login token issuance, and protected route access."""
    # 1. Register User
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "dr_lead",
            "email": "dr_lead@university.edu",
            "password": "Password987!",
            "role": "ADMIN",
            "is_active": True,
        },
    )
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["username"] == "dr_lead"

    # 2. Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "dr_lead", "password": "Password987!"},
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    token = token_data["access_token"]
    assert token_data["role"] == "ADMIN"

    headers = {"Authorization": f"Bearer {token}"}

    # 3. Get /auth/me
    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "dr_lead@university.edu"

    # 4. Check DR Status
    dr_resp = await client.get("/api/v1/disaster-recovery/status", headers=headers)
    assert dr_resp.status_code == 200
    dr_data = dr_resp.json()
    assert dr_data["active_read_provider"] in ("AWS_S3", "GCP_STORAGE")

    # 5. Cost estimate
    cost_resp = await client.post(
        "/api/v1/costs/estimate",
        headers=headers,
        json={"file_size_bytes": 1073741824, "priority": "MEDIUM", "access_frequency_tier": "FREQUENT"},
    )
    assert cost_resp.status_code == 200
    cost_data = cost_resp.json()
    assert cost_data["file_size_gb"] == 1.0
    assert cost_data["estimated_savings_usd"] > 0

