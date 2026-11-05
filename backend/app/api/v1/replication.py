from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.replication import ReplicationJob, ReplicationPolicy
from app.models.user import User
from app.schemas.replication import (
    ReplicationJobRead,
    ReplicationPolicyCreate,
    ReplicationPolicyRead,
    ReplicationPolicyUpdate,
)

router = APIRouter(prefix="/replication", tags=["Replication Engine"])


@router.get("/policies", response_model=List[ReplicationPolicyRead])
@router.get("/policies/", response_model=List[ReplicationPolicyRead])
async def list_policies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves all active replication policies."""
    result = await db.execute(select(ReplicationPolicy).order_by(ReplicationPolicy.created_at.desc()))
    return result.scalars().all()


@router.post("/policies", response_model=ReplicationPolicyRead, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy_in: ReplicationPolicyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates or updates a replication policy."""
    policy = ReplicationPolicy(
        name=policy_in.name,
        strategy_type=policy_in.strategy_type,
        target_rpo_seconds=policy_in.target_rpo_seconds,
        target_rto_seconds=policy_in.target_rto_seconds,
        max_budget_monthly_usd=policy_in.max_budget_monthly_usd,
        weights_json=policy_in.weights_json,
        threshold_score=policy_in.threshold_score,
        is_active=policy_in.is_active,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.put("/policies/{policy_id}", response_model=ReplicationPolicyRead)
async def update_policy(
    policy_id: str,
    policy_in: ReplicationPolicyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates an existing replication policy parameters, budget, and weights."""
    result = await db.execute(select(ReplicationPolicy).where(ReplicationPolicy.id == policy_id))
    policy = result.scalars().first()
    if not policy:
        raise HTTPException(status_code=404, detail="Replication policy not found")
    if policy_in.name is not None:
        policy.name = policy_in.name
    if policy_in.strategy_type is not None:
        policy.strategy_type = policy_in.strategy_type
    if policy_in.target_rpo_seconds is not None:
        policy.target_rpo_seconds = policy_in.target_rpo_seconds
    if policy_in.target_rto_seconds is not None:
        policy.target_rto_seconds = policy_in.target_rto_seconds
    if policy_in.max_budget_monthly_usd is not None:
        policy.max_budget_monthly_usd = policy_in.max_budget_monthly_usd
    if policy_in.weights_json is not None:
        policy.weights_json = policy_in.weights_json
    if policy_in.threshold_score is not None:
        policy.threshold_score = policy_in.threshold_score
    if policy_in.is_active is not None:
        policy.is_active = policy_in.is_active
    await db.commit()
    await db.refresh(policy)
    return policy


@router.get("/jobs", response_model=List[ReplicationJobRead])
async def list_replication_jobs(
    status_filter: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves asynchronous replication jobs and their decision explanations."""
    query = select(ReplicationJob).order_by(ReplicationJob.created_at.desc()).limit(limit)
    if status_filter:
        query = query.where(ReplicationJob.status == status_filter)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/jobs/{job_id}", response_model=ReplicationJobRead)
async def get_replication_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves full details and decision metrics for a single replication job."""
    query = select(ReplicationJob).where(ReplicationJob.id == job_id)
    res = await db.execute(query)
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Replication job not found")
    return job


@router.post("/retry-pending")
async def retry_pending_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Finds all held or pending replication jobs and dispatches them to Celery queue."""
    from app.replication.engine import replicate_file_task

    query = select(ReplicationJob).where(ReplicationJob.status.in_(["PENDING", "FAILED"]))
    res = await db.execute(query)
    jobs = res.scalars().all()

    enqueued_count = 0
    for job in jobs:
        try:
            replicate_file_task.delay(job.id)
            enqueued_count += 1
        except Exception as e:
            # If Redis or Celery encounters an issue with a specific job
            pass

    return {
        "total_held": len(jobs),
        "enqueued": enqueued_count,
        "message": f"Successfully dispatched {enqueued_count} held jobs to Celery Redis queue.",
    }


@router.post("/jobs/{job_id}/retry")
async def retry_single_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dispatches a specific replication job to Celery for re-evaluation."""
    from app.replication.engine import replicate_file_task

    query = select(ReplicationJob).where(ReplicationJob.id == job_id)
    res = await db.execute(query)
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Replication job not found")

    job.status = "PENDING"
    await db.commit()

    replicate_file_task.delay(job.id)
    return {"job_id": job.id, "status": "QUEUED", "message": f"Job {job.id} enqueued to Celery."}

