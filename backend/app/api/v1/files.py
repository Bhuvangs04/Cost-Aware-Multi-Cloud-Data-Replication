import hashlib
import io
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, File as FastAPIFile, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ObjectNotFoundError, ProviderUnavailableError
from app.models.cloud_provider import CloudProvider
from app.models.file import File, FileVersion
from app.models.replication import FileReplica, ReplicationJob, ReplicationPolicy
from app.models.user import User
from app.schemas.file import FileListResponse, FileMetadataRead, FileUploadResponse
from app.storage.factory import get_aws_provider, get_gcp_provider, get_storage_provider

router = APIRouter(prefix="/files", tags=["File Management"])


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    priority: str = Form("MEDIUM"),
    access_frequency_tier: str = Form("FREQUENT"),
    tags: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Uploads a file to the Primary Cloud (AWS S3), registers the file version manifest,
    and enqueues an asynchronous cross-cloud replication job.
    """
    content = await file.read()
    file_size_bytes = len(content)

    # Compute SHA-256 Checksum
    hasher = hashlib.sha256()
    hasher.update(content)
    sha256_hash = hasher.hexdigest()

    storage_key = f"uploads/{current_user.id}/{int(time.time())}_{file.filename}"

    # 1. Upload to Primary Cloud (AWS S3)
    aws_provider = get_aws_provider()
    try:
        object_ref = await aws_provider.upload_file(
            key=storage_key,
            data=content,
            content_type=file.content_type or "application/octet-stream",
            metadata={"filename": file.filename, "priority": priority},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to persist file in Primary Cloud (AWS S3): {str(e)}",
        )

    # 2. Record File & FileVersion in PostgreSQL Manifest
    db_file = File(
        owner_id=current_user.id,
        filename=file.filename,
        storage_key=storage_key,
        file_size_bytes=file_size_bytes,
        content_type=file.content_type or "application/octet-stream",
        sha256_hash=sha256_hash,
        priority=priority.upper(),
        access_frequency_tier=access_frequency_tier.upper(),
        tags=tags,
    )
    db.add(db_file)
    await db.flush()

    file_version = FileVersion(
        file_id=db_file.id,
        version_num=1,
        aws_version_id=object_ref.version_id,
        size_bytes=file_size_bytes,
        sha256_hash=sha256_hash,
        is_current=True,
    )
    db.add(file_version)
    await db.flush()

    # 3. Create Replication Job record
    policy_res = await db.execute(
        select(ReplicationPolicy).where(ReplicationPolicy.is_active == True).limit(1)
    )
    active_policy = policy_res.scalars().first()
    policy_id = active_policy.id if active_policy else None
    strategy = active_policy.strategy_type if active_policy else "COST_AWARE_ADAPTIVE"

    idempotency_key = f"{db_file.id}_{file_version.id}_{strategy}"
    rep_job = ReplicationJob(
        file_id=db_file.id,
        version_id=file_version.id,
        policy_id=policy_id,
        strategy_used=strategy,
        status="PENDING",
        idempotency_key=idempotency_key,
    )
    db.add(rep_job)
    await db.commit()

    # 4. Enqueue asynchronous replication task via Celery
    try:
        from app.replication.engine import replicate_file_task
        replicate_file_task.delay(rep_job.id)
    except Exception as e:
        # If Redis/Celery worker is offline during local test, the job remains PENDING for subsequent execution
        pass

    return FileUploadResponse(
        file_id=db_file.id,
        version_id=file_version.id,
        filename=db_file.filename,
        storage_key=db_file.storage_key,
        file_size_bytes=db_file.file_size_bytes,
        sha256_hash=db_file.sha256_hash,
        priority=db_file.priority,
        access_frequency_tier=db_file.access_frequency_tier,
        upload_status="stored_aws",
        replication_job_id=rep_job.id,
        message="File securely ingested into AWS S3 primary storage. Replication queued.",
    )


@router.get("", response_model=FileListResponse)
@router.get("/", response_model=FileListResponse)
async def list_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    priority: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists files with their versions and cross-cloud replicas."""
    query = (
        select(File)
        .where(File.is_deleted == False)
        .options(selectinload(File.versions), selectinload(File.replicas))
        .offset(skip)
        .limit(limit)
        .order_by(File.created_at.desc())
    )
    if priority:
        query = query.where(File.priority == priority.upper())

    result = await db.execute(query)
    files = result.scalars().all()

    count_query = select(func.count(File.id)).where(File.is_deleted == False)
    if priority:
        count_query = count_query.where(File.priority == priority.upper())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    return {"total": total, "items": files}


@router.get("/{file_id}", response_model=FileMetadataRead)
async def get_file_metadata(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves detailed file metadata, versions, and multi-cloud replica locations."""
    query = (
        select(File)
        .where(File.id == file_id, File.is_deleted == False)
        .options(selectinload(File.versions), selectinload(File.replicas))
    )
    result = await db.execute(query)
    file_obj = result.scalars().first()
    if not file_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return file_obj


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    version_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Downloads a file. Automatically routes download request to GCP Storage if AWS S3 is degraded/down (DR failover).
    """
    res = await db.execute(
        select(File)
        .where(File.id == file_id, File.is_deleted == False)
        .options(selectinload(File.versions), selectinload(File.replicas))
    )
    file_obj = res.scalars().first()
    if not file_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Check primary cloud health / failover status
    aws_provider_res = await db.execute(select(CloudProvider).where(CloudProvider.name == "AWS_S3"))
    aws_provider = aws_provider_res.scalars().first()
    is_failover = (aws_provider and aws_provider.status in ("DEGRADED", "DOWN")) or settings.SIMULATE_AWS_OUTAGE

    if not is_failover:
        # Normal operation: Read from AWS S3
        provider = get_aws_provider()
        source_cloud = "AWS_S3"
        ver_id = version_id or (file_obj.versions[0].aws_version_id if file_obj.versions else None)
    else:
        # DR Failover operation: Read from GCP Storage replica
        provider = get_gcp_provider()
        source_cloud = "GCP_STORAGE"
        # Find verified GCP replica
        replica = next((r for r in file_obj.replicas if r.is_verified), None)
        if not replica:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AWS S3 is in outage and no verified GCP replica exists for this file.",
            )
        ver_id = version_id or (file_obj.versions[0].gcp_generation_id if file_obj.versions else None)

    try:
        payload, meta = await provider.download_file(file_obj.storage_key, version_id=ver_id)
    except ObjectNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found in storage.")
    except ProviderUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

    return Response(
        content=payload,
        media_type=file_obj.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_obj.filename}"',
            "X-Source-Cloud": source_cloud,
            "X-SHA256": meta.sha256_hash,
            "X-Failover-Active": str(is_failover).lower(),
        },
    )


@router.delete("/{file_id}", status_code=status.HTTP_200_OK)
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marks a file as deleted in the manifest and removes objects from storage."""
    result = await db.execute(select(File).where(File.id == file_id, File.is_deleted == False))
    file_obj = result.scalars().first()
    if not file_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Remove from primary storage
    aws = get_aws_provider()
    try:
        await aws.delete_file(file_obj.storage_key)
    except Exception:
        pass

    file_obj.is_deleted = True
    await db.commit()
    return {"message": f"File '{file_obj.filename}' marked as deleted.", "file_id": file_id}
