from datetime import datetime, timezone
import json
from typing import Dict, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.cost import CostRecord
from app.models.file import File, FileVersion
from app.models.replication import ReplicationPolicy
from app.replication.strategies import (
    BaseReplicationStrategy,
    CostAwareAdaptiveStrategy,
    DecisionResult,
    FullReplicationStrategy,
    PriorityBasedStrategy,
)


class ReplicationDecisionEngine:
    """
    Orchestrates policy loading, dynamic budget calculation, and algorithmic strategy selection.
    """

    def __init__(self):
        self._strategies: Dict[str, BaseReplicationStrategy] = {
            "FULL": FullReplicationStrategy(),
            "PRIORITY": PriorityBasedStrategy(),
            "COST_AWARE_ADAPTIVE": CostAwareAdaptiveStrategy(),
        }

    async def get_monthly_spent_usd(self, session: AsyncSession) -> float:
        """Calculates total cross-cloud egress and replica storage charges accrued in the current month."""
        now = datetime.now(timezone.utc)
        first_of_month = now.replace(day=1).date()

        query = select(
            func.coalesce(
                func.sum(CostRecord.egress_transfer_cost_usd + CostRecord.storage_cost_usd), 0.0
            )
        ).where(CostRecord.record_date >= first_of_month)

        res = await session.execute(query)
        spent = float(res.scalar_one())
        return spent

    async def evaluate_decision(
        self,
        session: AsyncSession,
        file_obj: File,
        policy: Optional[ReplicationPolicy] = None,
    ) -> DecisionResult:
        """
        Loads policy rules, calculates budget headroom, and evaluates the file
        against the active replication strategy.
        """
        # 1. Resolve Active Policy
        if not policy:
            res = await session.execute(
                select(ReplicationPolicy).where(ReplicationPolicy.is_active == True).limit(1)
            )
            policy = res.scalars().first()

        strategy_type = policy.strategy_type if policy else "COST_AWARE_ADAPTIVE"
        strategy = self._strategies.get(strategy_type, self._strategies["COST_AWARE_ADAPTIVE"])

        # 2. Compute Budget Headroom
        max_budget = float(policy.max_budget_monthly_usd) if policy else 100.0
        spent_so_far = await self.get_monthly_spent_usd(session)
        budget_remaining = max(0.0, max_budget - spent_so_far)

        # 3. Parse Configured Algorithm Weights
        weights = None
        if policy and policy.weights_json:
            try:
                weights = json.loads(policy.weights_json)
            except Exception as e:
                logger.warning(f"Error parsing weights_json from policy '{policy.name}': {e}")

        threshold = float(policy.threshold_score) if policy else 0.50
        target_rpo = int(policy.target_rpo_seconds) if policy else 3600
        target_rto = int(policy.target_rto_seconds) if policy else 300

        # 4. Execute Algorithmic Evaluation
        decision = strategy.evaluate(
            file_size_bytes=file_obj.file_size_bytes,
            priority=file_obj.priority,
            access_frequency_tier=file_obj.access_frequency_tier,
            target_rpo_seconds=target_rpo,
            target_rto_seconds=target_rto,
            budget_remaining_usd=budget_remaining,
            weights_config=weights,
            threshold_score=threshold,
        )

        logger.info(
            f"Decision for '{file_obj.filename}' [{strategy_type}]: "
            f"Action={decision.action}, Score={decision.decision_score}, EstCost=${decision.estimated_cost_usd}"
        )

        return decision

