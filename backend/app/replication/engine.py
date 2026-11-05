import asyncio
from datetime import datetime, timezone
import json
import time
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import (
    ChecksumMismatchError,
    ObjectNotFoundError,
    ProviderUnavailableError,
    ReplicationError,
    StorageProviderError,
)
from app.core.logging import logger
from app.models.base import utc_now
from app.models.cloud_provider import CloudProvider
from app.models.cost import CostRecord
from app.models.file import File, FileVersion
from app.models.replication import FileReplica, ReplicationJob
from app.replication.verifier import CrossCloudVerifier
from app.storage.factory import get_aws_provider, get_gcp_provider
from app.workers.celery_app import celery_app


async def execute_replication_pipeline(job_id: str, session: Optional[AsyncSessionLocal] = None) -> dict:
    """
    Executes asynchronous cross-cloud stream replication from AWS S3 to GCP Storage,
    enforces cryptographic SHA-256 verification, and updates metadata & cost ledgers.
    """
    if session is not None:
        return await _execute_pipeline_with_session(job_id, session)
    else:
        async with AsyncSessionLocal() as new_session:
            return await _execute_pipeline_with_session(job_id, new_session)


async def _execute_pipeline_with_session(job_id: str, session) -> dict:
    # 1. Fetch ReplicationJob
    query = (
        select(ReplicationJob)
        .where(ReplicationJob.id == job_id)
        .options(
            selectinload(ReplicationJob.file).selectinload(File.versions),
            selectinload(ReplicationJob.policy),
        )
    )
    res = await session.execute(query)
    job = res.scalars().first()

    if not job:
        raise ReplicationError(f"ReplicationJob '{job_id}' not found.")

    # Idempotency check: avoid redundant replication if already completed
    if job.status == "COMPLETED":
        logger.info(f"ReplicationJob '{job_id}' already completed. Skipping redundant execution.")
        return {"status": "ALREADY_COMPLETED", "job_id": job_id}

    # Update status to IN_PROGRESS
    job.status = "IN_PROGRESS"
    job.started_at = utc_now()
    await session.commit()

    file_obj = job.file
    version_obj = next((v for v in file_obj.versions if v.id == job.version_id), None)
    if not version_obj:
        job.status = "FAILED"
        job.error_message = f"FileVersion '{job.version_id}' not associated with file."
        await session.commit()
        raise ReplicationError(job.error_message)

    # 2. Evaluate Replication Strategy using Decision Engine
    from app.replication.decision_engine import ReplicationDecisionEngine
    decision_engine = ReplicationDecisionEngine()
    decision = await decision_engine.evaluate_decision(session, file_obj=file_obj, policy=job.policy)

    job.decision_score = decision.decision_score
    job.decision_reason = json.dumps(decision.model_dump())

    if decision.action == "SKIP":
        job.status = "SKIPPED"
        job.completed_at = utc_now()
        await session.commit()
        logger.info(f"Replication skipped for '{file_obj.filename}': {decision.reason}")
        return {
            "status": "SKIPPED",
            "job_id": job.id,
            "file_id": file_obj.id,
            "decision_score": decision.decision_score,
            "reason": decision.reason,
        }

    if decision.action == "DEFER_BATCH":
        job.status = "QUEUED"
        await session.commit()
        logger.info(f"Replication deferred for '{file_obj.filename}': {decision.reason}")
        return {
            "status": "DEFERRED",
            "job_id": job.id,
            "file_id": file_obj.id,
            "decision_score": decision.decision_score,
            "reason": decision.reason,
        }

    # 3. Storage Providers (Proceed with REPLICATE_NOW)
    aws_provider = get_aws_provider()
    gcp_provider = get_gcp_provider()

    # Query GCP CloudProvider DB record
    gcp_db_res = await session.execute(
        select(CloudProvider).where(CloudProvider.name == "GCP_STORAGE")
    )
    gcp_cloud_provider = gcp_db_res.scalars().first()
    gcp_provider_id = gcp_cloud_provider.id if gcp_cloud_provider else "gcp-default"

    start_time = time.perf_counter()

    try:
        # 3. Read object payload from Primary Cloud (AWS S3)
        logger.info(
            f"Starting cross-cloud transfer for file '{file_obj.filename}' "
            f"(key: '{file_obj.storage_key}', version: '{version_obj.aws_version_id}')"
        )
        payload, source_meta = await aws_provider.download_file(
            file_obj.storage_key, version_id=version_obj.aws_version_id
        )

        # 4. Stream upload replica to Secondary Cloud (GCP Storage)
        replica_ref = await gcp_provider.upload_file(
            key=file_obj.storage_key,
            data=payload,
            content_type=file_obj.content_type,
            metadata={
                "original_filename": file_obj.filename,
                "aws_version_id": version_obj.aws_version_id or "",
                "file_id": file_obj.id,
                "version_id": version_obj.id,
            },
        )

        replication_latency_ms = (time.perf_counter() - start_time) * 1000.0

        # 5. Cryptographic SHA-256 Cross-Cloud Verification
        is_valid, aws_hash, gcp_hash, verify_msg = await CrossCloudVerifier.verify_replica_integrity(
            primary_provider=aws_provider,
            secondary_provider=gcp_provider,
            storage_key=file_obj.storage_key,
            expected_sha256=file_obj.sha256_hash,
            primary_version_id=version_obj.aws_version_id,
            secondary_version_id=replica_ref.generation_id,
        )

        if not is_valid:
            raise ChecksumMismatchError(verify_msg)

        # 6. Calculate Financial Metrics
        file_size_gb = file_obj.file_size_bytes / (1024 ** 3)
        transfer_cost = file_size_gb * settings.AWS_EGRESS_TO_GCP_PRICE_PER_GB
        storage_cost_monthly = file_size_gb * settings.GCP_STORAGE_PRICE_PER_GB_MONTH

        # Update FileVersion with GCP Generation number
        version_obj.gcp_generation_id = replica_ref.generation_id

        # 7. Record / Update FileReplica Manifest
        replica_uri = f"gs://{gcp_provider.bucket_name}/{file_obj.storage_key}"
        replica_res = await session.execute(
            select(FileReplica).where(
                FileReplica.version_id == version_obj.id,
                FileReplica.provider_id == gcp_provider_id,
            )
        )
        replica_record = replica_res.scalars().first()

        if not replica_record:
            replica_record = FileReplica(
                file_id=file_obj.id,
                version_id=version_obj.id,
                provider_id=gcp_provider_id,
                replica_uri=replica_uri,
                storage_tier="STANDARD",
                sha256_hash=file_obj.sha256_hash,
                is_verified=True,
                verification_timestamp=utc_now(),
                size_bytes=file_obj.file_size_bytes,
                replication_latency_ms=round(replication_latency_ms, 2),
                transfer_cost_usd=round(transfer_cost, 6),
                storage_cost_monthly_usd=round(storage_cost_monthly, 6),
            )
            session.add(replica_record)
        else:
            replica_record.replica_uri = replica_uri
            replica_record.is_verified = True
            replica_record.verification_timestamp = utc_now()
            replica_record.replication_latency_ms = round(replication_latency_ms, 2)
            replica_record.transfer_cost_usd = round(transfer_cost, 6)
            replica_record.storage_cost_monthly_usd = round(storage_cost_monthly, 6)

        # 8. Record Financial Ledger Entry (CostRecord)
        cost_rec = CostRecord(
            record_date=utc_now().date(),
            provider_id=gcp_provider_id,
            file_id=file_obj.id,
            storage_cost_usd=round(storage_cost_monthly, 6),
            egress_transfer_cost_usd=round(transfer_cost, 6),
            api_operation_cost_usd=settings.GCP_PUT_OPS_PRICE_PER_1K / 1000.0,
            cumulative_savings_vs_full_usd=0.0,
            is_simulated=settings.SIMULATION_MODE,
        )
        session.add(cost_rec)

        # 9. Mark Job Completed
        job.status = "COMPLETED"
        job.completed_at = utc_now()
        job.error_message = None

        await session.commit()

        logger.info(
            f"Successfully replicated '{file_obj.filename}' to GCS. "
            f"Latency: {round(replication_latency_ms, 2)}ms, Checksum: {file_obj.sha256_hash[:12]}..."
        )

        return {
            "status": "COMPLETED",
            "job_id": job.id,
            "file_id": file_obj.id,
            "version_id": version_obj.id,
            "gcp_generation_id": replica_ref.generation_id,
            "latency_ms": round(replication_latency_ms, 2),
            "transfer_cost_usd": round(transfer_cost, 6),
            "storage_cost_monthly_usd": round(storage_cost_monthly, 6),
        }

    except Exception as e:
        job.status = "FAILED"
        job.retry_count += 1
        job.error_message = str(e)
        await session.commit()
        logger.error(f"ReplicationJob '{job_id}' failed: {e}")
        raise


_worker_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_or_create_worker_loop() -> asyncio.AbstractEventLoop:
    global _worker_loop
    try:
        loop = asyncio.get_running_loop()
        return loop
    except RuntimeError:
        pass

    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop


def _run_coroutine_safely(coro):
    """Safely runs an async coroutine from synchronous worker threads or Celery tasks without closing the loop."""
    try:
        loop = asyncio.get_running_loop()
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                def run_in_thread():
                    t_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(t_loop)
                    try:
                        return t_loop.run_until_complete(coro)
                    finally:
                        t_loop.close()
                return pool.submit(run_in_thread).result()
    except RuntimeError:
        pass

    loop = _get_or_create_worker_loop()
    return loop.run_until_complete(coro)


@celery_app.task(
    bind=True,
    name="app.replication.engine.replicate_file_task",
    max_retries=3,
    default_retry_delay=5,
    autoretry_for=(StorageProviderError, ProviderUnavailableError),
    retry_backoff=True,
)
def replicate_file_task(self, job_id: str):
    """
    Celery task wrapper executing cross-cloud replication asynchronously
    with exponential backoff and dead-letter failure tracking.
    """
    logger.info(f"Executing Celery replication task for Job ID: {job_id} (Attempt {self.request.retries + 1})")
    try:
        return _run_coroutine_safely(execute_replication_pipeline(job_id))
    except Exception as exc:
        logger.error(f"Celery task execution failed for job {job_id}: {exc}")
        if self.request.retries >= self.max_retries:
            logger.critical(f"ReplicationJob {job_id} exhausted all {self.max_retries} retries. Moving to dead-letter.")
            raise
        raise self.retry(exc=exc)
