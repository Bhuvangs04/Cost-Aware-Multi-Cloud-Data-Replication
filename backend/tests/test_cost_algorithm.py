import hashlib
import json
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.cloud_provider import CloudProvider
from app.models.file import File, FileVersion
from app.models.replication import FileReplica, ReplicationJob, ReplicationPolicy
from app.models.user import User
from app.replication.decision_engine import ReplicationDecisionEngine
from app.replication.engine import execute_replication_pipeline
from app.replication.strategies import (
    CostAwareAdaptiveStrategy,
    FullReplicationStrategy,
    PriorityBasedStrategy,
)
from app.storage.factory import get_aws_provider


def test_full_replication_strategy():
    """Verifies Strategy 1: Full Replication unconditionally replicates all items."""
    strategy = FullReplicationStrategy()
    res = strategy.evaluate(
        file_size_bytes=1048576,  # 1 MB
        priority="LOW",
        access_frequency_tier="RARE",
        target_rpo_seconds=86400,
        target_rto_seconds=3600,
        budget_remaining_usd=100.0,
    )
    assert res.action == "REPLICATE_NOW"
    assert res.strategy == "FULL"
    assert res.decision_score == 1.0


def test_priority_based_strategy():
    """Verifies Strategy 2: Priority-Based static heuristic routing."""
    strategy = PriorityBasedStrategy()

    # Critical -> Immediate
    crit_res = strategy.evaluate(
        file_size_bytes=1048576,
        priority="CRITICAL",
        access_frequency_tier="FREQUENT",
        target_rpo_seconds=60,
        target_rto_seconds=30,
        budget_remaining_usd=100.0,
    )
    assert crit_res.action == "REPLICATE_NOW"
    assert crit_res.decision_score == 1.0

    # High -> Immediate
    high_res = strategy.evaluate(
        file_size_bytes=1048576,
        priority="HIGH",
        access_frequency_tier="FREQUENT",
        target_rpo_seconds=3600,
        target_rto_seconds=300,
        budget_remaining_usd=100.0,
    )
    assert high_res.action == "REPLICATE_NOW"

    # Medium -> Deferred batch
    med_res = strategy.evaluate(
        file_size_bytes=1048576,
        priority="MEDIUM",
        access_frequency_tier="INTERMITTENT",
        target_rpo_seconds=7200,
        target_rto_seconds=600,
        budget_remaining_usd=100.0,
    )
    assert med_res.action == "DEFER_BATCH"

    # Low -> Skip
    low_res = strategy.evaluate(
        file_size_bytes=1048576,
        priority="LOW",
        access_frequency_tier="RARE",
        target_rpo_seconds=86400,
        target_rto_seconds=3600,
        budget_remaining_usd=100.0,
    )
    assert low_res.action == "SKIP"


def test_cost_aware_adaptive_strategy_scoring():
    """
    Verifies Strategy 3: Cost-Aware Adaptive scoring behavior,
    critical bypass invariant, budget guardrail, and logarithmic dampening.
    """
    strategy = CostAwareAdaptiveStrategy()

    # Invariant 1: CRITICAL priority ALWAYS replicates immediately
    crit_res = strategy.evaluate(
        file_size_bytes=10737418240,  # 10 GB
        priority="CRITICAL",
        access_frequency_tier="RARE",
        target_rpo_seconds=300,
        target_rto_seconds=60,
        budget_remaining_usd=50.0,
        threshold_score=0.5,
    )
    assert crit_res.action == "REPLICATE_NOW"
    assert "Zero-RPO guarantee" in crit_res.reason

    # Invariant 2: Budget Guardrail triggers SKIP when cost exceeds budget
    budget_skip_res = strategy.evaluate(
        file_size_bytes=107374182400,  # 100 GB (~$9 egress + ~$2 storage = ~$11)
        priority="HIGH",
        access_frequency_tier="FREQUENT",
        target_rpo_seconds=3600,
        target_rto_seconds=300,
        budget_remaining_usd=5.0,  # Only $5 budget remaining!
        threshold_score=0.5,
    )
    assert budget_skip_res.action == "SKIP"
    assert "Budget Guardrail" in budget_skip_res.reason

    # High Value Candidate: High priority, frequent access, reasonable size -> REPLICATE_NOW
    high_val_res = strategy.evaluate(
        file_size_bytes=52428800,  # 50 MB
        priority="HIGH",
        access_frequency_tier="FREQUENT",
        target_rpo_seconds=1800,
        target_rto_seconds=120,
        budget_remaining_usd=100.0,
        threshold_score=0.5,
    )
    assert high_val_res.action == "REPLICATE_NOW"
    assert high_val_res.decision_score >= 0.5

    # Low Value Candidate: Low priority, rare access -> SKIP
    low_val_res = strategy.evaluate(
        file_size_bytes=21474836480,  # 20 GB
        priority="LOW",
        access_frequency_tier="RARE",
        target_rpo_seconds=86400,
        target_rto_seconds=3600,
        budget_remaining_usd=100.0,
        threshold_score=0.5,
    )
    assert low_val_res.action == "SKIP"
    assert low_val_res.decision_score < 0.35


@pytest.mark.asyncio
async def test_adaptive_decision_engine_end_to_end(db_session: AsyncSession):
    """
    Tests end-to-end integration:
    - Demonstrates that a LOW priority file is SKIPPED by the engine, saving egress cost.
    - Demonstrates that a CRITICAL file is REPLICATED, generating a verified replica.
    """
    user = User(
        username="research_director",
        email="director@lab.edu",
        hashed_password="pw",
        role="ADMIN",
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
    policy = ReplicationPolicy(
        name="Standard Research Policy",
        strategy_type="COST_AWARE_ADAPTIVE",
        target_rpo_seconds=3600,
        target_rto_seconds=300,
        max_budget_monthly_usd=100.0,
        weights_json='{"w_p": 0.35, "w_a": 0.25, "w_r": 0.15, "w_s": 0.15, "w_c": 0.10}',
        threshold_score=0.5,
    )
    db_session.add_all([user, aws_p, gcp_p, policy])
    await db_session.flush()

    aws_provider = get_aws_provider()

    # 1. LOW priority asset -> Expect SKIP
    low_content = b"Non-essential telemetry scratch logs"
    low_key = "telemetry/scratch_01.tmp"
    s3_ref_low = await aws_provider.upload_file(low_key, low_content)

    file_low = File(
        owner_id=user.id,
        filename="scratch_01.tmp",
        storage_key=low_key,
        file_size_bytes=len(low_content),
        sha256_hash="lowhash0000000000000000000000000000000000000000000000000000000000",
        priority="LOW",
        access_frequency_tier="RARE",
    )
    db_session.add(file_low)
    await db_session.flush()

    ver_low = FileVersion(
        file_id=file_low.id,
        version_num=1,
        aws_version_id=s3_ref_low.version_id,
        size_bytes=len(low_content),
        sha256_hash=file_low.sha256_hash,
        is_current=True,
    )
    db_session.add(ver_low)
    await db_session.flush()

    job_low = ReplicationJob(
        file_id=file_low.id,
        version_id=ver_low.id,
        policy_id=policy.id,
        strategy_used="COST_AWARE_ADAPTIVE",
        status="PENDING",
        idempotency_key=f"rep_low_{file_low.id}",
    )
    db_session.add(job_low)
    await db_session.commit()

    # Run replication pipeline on LOW priority file
    res_low = await execute_replication_pipeline(job_low.id, session=db_session)
    assert res_low["status"] in ("SKIPPED", "DEFERRED")

    # Verify no GCP replica was created for the low priority file
    replica_res = await db_session.execute(
        select(FileReplica).where(FileReplica.file_id == file_low.id)
    )
    assert replica_res.scalars().first() is None  # Saved egress cost!

    # 2. CRITICAL priority asset -> Expect REPLICATE_NOW
    crit_content = b"CRITICAL MISSION PARAMETERS: Mars Rover descent guidance algorithm v4"
    crit_hasher = hashlib.sha256()
    crit_hasher.update(crit_content)
    crit_sha256 = crit_hasher.hexdigest()

    crit_key = "missions/rover_guidance_v4.py"
    s3_ref_crit = await aws_provider.upload_file(crit_key, crit_content)

    file_crit = File(
        owner_id=user.id,
        filename="rover_guidance_v4.py",
        storage_key=crit_key,
        file_size_bytes=len(crit_content),
        sha256_hash=crit_sha256,
        priority="CRITICAL",
        access_frequency_tier="FREQUENT",
    )
    db_session.add(file_crit)
    await db_session.flush()

    ver_crit = FileVersion(
        file_id=file_crit.id,
        version_num=1,
        aws_version_id=s3_ref_crit.version_id,
        size_bytes=len(crit_content),
        sha256_hash=crit_sha256,
        is_current=True,
    )
    db_session.add(ver_crit)
    await db_session.flush()

    job_crit = ReplicationJob(
        file_id=file_crit.id,
        version_id=ver_crit.id,
        policy_id=policy.id,
        strategy_used="COST_AWARE_ADAPTIVE",
        status="PENDING",
        idempotency_key=f"rep_crit_{file_crit.id}",
    )
    db_session.add(job_crit)
    await db_session.commit()

    # Run replication pipeline on CRITICAL file
    res_crit = await execute_replication_pipeline(job_crit.id, session=db_session)
    assert res_crit["status"] == "COMPLETED"

    # Verify GCP replica WAS created for the critical file
    replica_crit_res = await db_session.execute(
        select(FileReplica).where(FileReplica.file_id == file_crit.id)
    )
    replica_crit = replica_crit_res.scalars().first()
    assert replica_crit is not None
    assert replica_crit.is_verified is True
