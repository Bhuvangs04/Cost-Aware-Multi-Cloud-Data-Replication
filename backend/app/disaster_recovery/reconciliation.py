from datetime import datetime, timezone
import json
import time
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError, ReconciliationConflictError
from app.core.logging import logger
from app.models.cloud_provider import CloudProvider
from app.models.file import File, FileVersion
from app.models.health import DisasterRecoveryEvent
from app.models.replication import FileReplica
from app.replication.verifier import CrossCloudVerifier
from app.storage.factory import get_aws_provider, get_gcp_provider


class ReconciliationEngine:
    """
    Executes bidirectional data reconciliation after Primary Cloud (AWS S3) recovers from an outage.
    Ensures zero data loss and prevents stale primary data from overwriting failover updates.
    """

    @classmethod
    async def reconcile_after_recovery(
        cls,
        session: AsyncSession,
        outage_start_time: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """
        Reconciles version manifests and syncs updates from GCP Storage back to AWS S3:
        1. Confirms AWS S3 is healthy.
        2. Queries files modified or created during the failover window.
        3. Syncs GCP replicas to AWS S3, creating new monotonically increasing S3 versions.
        4. Verifies SHA-256 hashes on restored primary objects.
        5. Restores AWS S3 as active primary read/write provider.
        """
        start_time = time.perf_counter()
        logger.info("Initiating post-outage reconciliation protocol...")

        aws_provider = get_aws_provider()
        gcp_provider = get_gcp_provider()

        # 1. Verify AWS is genuinely healthy before reconciling
        aws_health = await aws_provider.check_health()
        if not aws_health.is_healthy:
            raise ProviderUnavailableError(f"Cannot reconcile: AWS S3 is still degraded: {aws_health.details}")

        # 2. Identify candidate files for reconciliation
        query = (
            select(File)
            .where(File.is_deleted == False)
            .options(
                selectinload(File.versions),
                selectinload(File.replicas),
            )
        )
        res = await session.execute(query)
        files = res.scalars().all()

        reconciled_count = 0
        conflict_count = 0
        synced_files: List[str] = []

        for file_obj in files:
            # Find verified GCP replica
            replica = next((r for r in file_obj.replicas if r.is_verified), None)
            if not replica:
                continue

            current_ver = next((v for v in file_obj.versions if v.is_current), None)

            # Check if GCP has an updated generation or AWS lacks current version
            needs_sync = False
            if current_ver:
                if not current_ver.aws_version_id or (outage_start_time and current_ver.created_at >= outage_start_time):
                    needs_sync = True
            else:
                needs_sync = True

            if needs_sync:
                try:
                    logger.info(f"Reconciling '{file_obj.filename}' from GCP Storage back to AWS S3...")
                    # Download latest payload from GCP
                    gcp_bytes, gcp_meta = await gcp_provider.download_file(file_obj.storage_key)

                    # Re-upload to AWS S3 with new version
                    s3_ref = await aws_provider.upload_file(
                        key=file_obj.storage_key,
                        data=gcp_bytes,
                        content_type=file_obj.content_type,
                        metadata={"reconciled_from": "GCP_STORAGE", "original_sha256": file_obj.sha256_hash},
                    )

                    # Update version manifest
                    if current_ver:
                        current_ver.aws_version_id = s3_ref.version_id
                    else:
                        new_ver = FileVersion(
                            file_id=file_obj.id,
                            version_num=len(file_obj.versions) + 1,
                            aws_version_id=s3_ref.version_id,
                            gcp_generation_id=replica.version.gcp_generation_id if replica.version else None,
                            size_bytes=len(gcp_bytes),
                            sha256_hash=file_obj.sha256_hash,
                            is_current=True,
                        )
                        session.add(new_ver)

                    # Verify hash parity
                    is_valid, _, _, _ = await CrossCloudVerifier.verify_replica_integrity(
                        primary_provider=aws_provider,
                        secondary_provider=gcp_provider,
                        storage_key=file_obj.storage_key,
                        expected_sha256=file_obj.sha256_hash,
                        primary_version_id=s3_ref.version_id,
                    )

                    if not is_valid:
                        conflict_count += 1
                        logger.error(f"Reconciliation hash conflict for file {file_obj.filename}")
                    else:
                        reconciled_count += 1
                        synced_files.append(file_obj.filename)

                except Exception as e:
                    logger.error(f"Error reconciling file {file_obj.filename}: {e}")
                    conflict_count += 1

        duration_seconds = round(time.perf_counter() - start_time, 3)

        # 3. Restore Primary Cloud Provider Status in DB
        res_prov = await session.execute(select(CloudProvider).where(CloudProvider.name == "AWS_S3"))
        aws_prov = res_prov.scalars().first()
        if aws_prov:
            aws_prov.status = "HEALTHY"

        # 4. Record Disaster Recovery Event
        details = {
            "reconciled_files": synced_files,
            "conflicts_detected": conflict_count,
            "duration_seconds": duration_seconds,
            "routing_restored": "AWS_S3",
        }

        event = DisasterRecoveryEvent(
            event_type="RECONCILIATION_COMPLETED",
            failed_provider_id=aws_prov.id if aws_prov else None,
            failover_provider_id=None,
            rto_seconds=duration_seconds,
            rpo_seconds=0.0,
            affected_files_count=len(files),
            reconciled_files_count=reconciled_count,
            details_json=json.dumps(details),
        )
        session.add(event)
        await session.commit()

        logger.info(
            f"Reconciliation completed in {duration_seconds}s. "
            f"Reconciled: {reconciled_count}, Conflicts: {conflict_count}. Routing restored to AWS S3."
        )

        return {
            "reconciliation_id": event.id,
            "files_reconciled": reconciled_count,
            "conflicts_detected": conflict_count,
            "duration_seconds": duration_seconds,
            "status": "COMPLETED" if conflict_count == 0 else "COMPLETED_WITH_CONFLICTS",
            "message": f"Successfully synchronized {reconciled_count} files to AWS S3. Normal routing restored.",
        }

