from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.file import File
from app.models.replication import FileReplica, ReplicationJob, ReplicationPolicy
from app.models.user import User
from app.schemas.cost import CostEstimateRequest, CostEstimateResponse, CostSummaryResponse

router = APIRouter(tags=["Cost Analytics"])


@router.post("/estimate", response_model=CostEstimateResponse)
@router.post("/estimate/", response_model=CostEstimateResponse)
async def estimate_replication_cost(
    request: CostEstimateRequest,
    current_user: User = Depends(get_current_user),
):
    """Calculates cross-cloud egress and storage cost projections for a candidate file."""
    file_size_gb = request.file_size_bytes / (1024 ** 3)
    aws_storage = file_size_gb * settings.AWS_STORAGE_PRICE_PER_GB_MONTH * request.retention_months
    gcp_storage = file_size_gb * settings.GCP_STORAGE_PRICE_PER_GB_MONTH * request.retention_months
    egress_cost = file_size_gb * settings.AWS_EGRESS_TO_GCP_PRICE_PER_GB
    ops_cost = (settings.AWS_PUT_OPS_PRICE_PER_1K / 1000) * 2

    full_replication_cost = aws_storage + gcp_storage + egress_cost + ops_cost
    adaptive_factor = 0.45 if request.priority in ("MEDIUM", "LOW") else 1.0
    adaptive_cost = aws_storage + (gcp_storage + egress_cost + ops_cost) * adaptive_factor
    savings = full_replication_cost - adaptive_cost
    savings_pct = (savings / full_replication_cost * 100) if full_replication_cost > 0 else 0.0

    return CostEstimateResponse(
        file_size_gb=round(file_size_gb, 4),
        aws_storage_monthly_usd=round(aws_storage, 4),
        gcp_storage_monthly_usd=round(gcp_storage, 4),
        cross_cloud_egress_usd=round(egress_cost, 4),
        operations_cost_usd=round(ops_cost, 6),
        total_full_replication_usd=round(full_replication_cost, 4),
        total_adaptive_replication_usd=round(adaptive_cost, 4),
        estimated_savings_usd=round(savings, 4),
        savings_percentage=round(savings_pct, 2),
        pricing_assumptions={
            "aws_storage_per_gb_month": settings.AWS_STORAGE_PRICE_PER_GB_MONTH,
            "gcp_storage_per_gb_month": settings.GCP_STORAGE_PRICE_PER_GB_MONTH,
            "aws_egress_to_gcp_per_gb": settings.AWS_EGRESS_TO_GCP_PRICE_PER_GB,
        },
    )


@router.get("/summary", response_model=CostSummaryResponse)
@router.get("/summary/", response_model=CostSummaryResponse)
async def get_cost_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Provides platform-wide aggregated storage and egress cost breakdown with calculated savings."""
    # 1. Total Primary Storage (AWS S3)
    file_bytes_res = await db.execute(
        select(func.coalesce(func.sum(File.file_size_bytes), 0)).where(File.is_deleted == False)
    )
    total_primary_bytes = int(file_bytes_res.scalar_one())
    total_primary_gb = total_primary_bytes / (1024 ** 3)
    total_aws_storage_usd = total_primary_gb * settings.AWS_STORAGE_PRICE_PER_GB_MONTH

    # 2. Total Replicas in Secondary Cloud (GCP Storage)
    replica_stats_res = await db.execute(
        select(
            func.coalesce(func.sum(FileReplica.size_bytes), 0),
            func.coalesce(func.sum(FileReplica.transfer_cost_usd), 0.0),
            func.coalesce(func.sum(FileReplica.storage_cost_monthly_usd), 0.0),
        )
    )
    replica_bytes, total_egress_transfer_usd, total_gcp_storage_usd = replica_stats_res.one()
    replica_bytes = int(replica_bytes)
    total_egress_transfer_usd = float(total_egress_transfer_usd)
    total_gcp_storage_usd = float(total_gcp_storage_usd)

    replica_gb = replica_bytes / (1024 ** 3)
    if total_gcp_storage_usd == 0 and replica_gb > 0:
        total_gcp_storage_usd = replica_gb * settings.GCP_STORAGE_PRICE_PER_GB_MONTH
    if total_egress_transfer_usd == 0 and replica_gb > 0:
        total_egress_transfer_usd = replica_gb * settings.AWS_EGRESS_TO_GCP_PRICE_PER_GB

    # 3. Operations Cost
    jobs_count_res = await db.execute(
        select(func.count(ReplicationJob.id)).where(ReplicationJob.status == "COMPLETED")
    )
    completed_jobs_count = int(jobs_count_res.scalar_one())
    total_ops_usd = (completed_jobs_count * (settings.AWS_PUT_OPS_PRICE_PER_1K + settings.GCP_PUT_OPS_PRICE_PER_1K)) / 1000.0

    # 4. Active Policy & Budget
    policy_res = await db.execute(
        select(ReplicationPolicy).where(ReplicationPolicy.is_active == True).limit(1)
    )
    active_policy = policy_res.scalars().first()
    monthly_budget_usd = float(active_policy.max_budget_monthly_usd) if active_policy else 100.0
    active_strategy = active_policy.strategy_type if active_policy else "COST_AWARE_ADAPTIVE"

    # 5. Current Strategy Total Cost
    total_cost_current_strategy_usd = total_aws_storage_usd + total_gcp_storage_usd + total_egress_transfer_usd + total_ops_usd

    # 6. Baseline Full Replication Cost:
    # If 100% of files were replicated to GCP + egress
    baseline_full_gcp_storage = total_primary_gb * settings.GCP_STORAGE_PRICE_PER_GB_MONTH
    baseline_full_egress = total_primary_gb * settings.AWS_EGRESS_TO_GCP_PRICE_PER_GB
    files_count_res = await db.execute(select(func.count(File.id)).where(File.is_deleted == False))
    total_files_count = int(files_count_res.scalar_one())
    baseline_full_ops = (total_files_count * (settings.AWS_PUT_OPS_PRICE_PER_1K + settings.GCP_PUT_OPS_PRICE_PER_1K)) / 1000.0

    baseline_full_replication_cost_usd = total_aws_storage_usd + baseline_full_gcp_storage + baseline_full_egress + baseline_full_ops

    net_savings_usd = max(0.0, baseline_full_replication_cost_usd - total_cost_current_strategy_usd)
    net_savings_percentage = (
        (net_savings_usd / baseline_full_replication_cost_usd * 100.0)
        if baseline_full_replication_cost_usd > 0
        else 0.0
    )

    cost_per_replicated_gb = (
        (total_cost_current_strategy_usd / replica_gb)
        if replica_gb > 0
        else (settings.AWS_STORAGE_PRICE_PER_GB_MONTH + settings.GCP_STORAGE_PRICE_PER_GB_MONTH)
    )

    cross_cloud_spent = total_gcp_storage_usd + total_egress_transfer_usd + total_ops_usd
    budget_utilized_percent = (cross_cloud_spent / monthly_budget_usd * 100.0) if monthly_budget_usd > 0 else 0.0

    return CostSummaryResponse(
        total_aws_storage_usd=round(total_aws_storage_usd, 6),
        total_gcp_storage_usd=round(total_gcp_storage_usd, 6),
        total_egress_transfer_usd=round(total_egress_transfer_usd, 6),
        total_replication_ops_usd=round(total_ops_usd, 6),
        total_cost_current_strategy_usd=round(total_cost_current_strategy_usd, 6),
        baseline_full_replication_cost_usd=round(baseline_full_replication_cost_usd, 6),
        net_savings_usd=round(net_savings_usd, 6),
        net_savings_percentage=round(net_savings_percentage, 2),
        cost_per_replicated_gb_usd=round(cost_per_replicated_gb, 4),
        active_strategy=active_strategy,
        monthly_budget_usd=round(monthly_budget_usd, 2),
        budget_utilized_percent=round(budget_utilized_percent, 2),
        is_simulated=settings.SIMULATION_MODE,
    )

