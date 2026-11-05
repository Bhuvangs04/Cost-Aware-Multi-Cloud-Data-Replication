from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import math
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import logger


class DecisionResult(BaseModel):
    action: str  # REPLICATE_NOW, DEFER_BATCH, SKIP
    strategy: str
    decision_score: Optional[float] = None
    breakdown: Dict[str, Any] = Field(default_factory=dict)
    estimated_cost_usd: float
    budget_remaining_usd: float
    reason: str


class BaseReplicationStrategy(ABC):
    """Abstract base strategy defining the contract for replication decision evaluation."""

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        pass

    @abstractmethod
    def evaluate(
        self,
        file_size_bytes: int,
        priority: str,
        access_frequency_tier: str,
        target_rpo_seconds: int,
        target_rto_seconds: int,
        budget_remaining_usd: float,
        weights_config: Optional[Dict[str, float]] = None,
        threshold_score: float = 0.5,
    ) -> DecisionResult:
        """Evaluates file metadata and yields a deterministic replication decision."""
        pass


class FullReplicationStrategy(BaseReplicationStrategy):
    """
    Strategy 1: Full Replication (Baseline).
    Unconditionally replicates every uploaded object from AWS S3 to GCP Storage.
    Used as the control benchmark for measuring egress and storage overhead.
    """

    @property
    def strategy_name(self) -> str:
        return "FULL"

    def evaluate(
        self,
        file_size_bytes: int,
        priority: str,
        access_frequency_tier: str,
        target_rpo_seconds: int,
        target_rto_seconds: int,
        budget_remaining_usd: float,
        weights_config: Optional[Dict[str, float]] = None,
        threshold_score: float = 0.5,
    ) -> DecisionResult:
        file_size_gb = file_size_bytes / (1024 ** 3)
        egress_cost = file_size_gb * settings.AWS_EGRESS_TO_GCP_PRICE_PER_GB
        storage_cost = file_size_gb * settings.GCP_STORAGE_PRICE_PER_GB_MONTH
        ops_cost = settings.GCP_PUT_OPS_PRICE_PER_1K / 1000.0
        est_cost = egress_cost + storage_cost + ops_cost

        return DecisionResult(
            action="REPLICATE_NOW",
            strategy=self.strategy_name,
            decision_score=1.0,
            breakdown={
                "file_size_gb": round(file_size_gb, 6),
                "egress_cost_usd": round(egress_cost, 6),
                "storage_cost_usd": round(storage_cost, 6),
                "policy_mode": "unconditional_full_replication",
            },
            estimated_cost_usd=round(est_cost, 6),
            budget_remaining_usd=round(budget_remaining_usd, 4),
            reason="Full Replication baseline policy mandates replication of all objects.",
        )


class PriorityBasedStrategy(BaseReplicationStrategy):
    """
    Strategy 2: Priority-Based Replication.
    Static tiered heuristics:
    - CRITICAL: Immediate replication (RPO target ~0).
    - HIGH: Replicate immediately.
    - MEDIUM: Deferred / batched replication.
    - LOW: Skipped (no disaster recovery replica created).
    """

    @property
    def strategy_name(self) -> str:
        return "PRIORITY"

    def evaluate(
        self,
        file_size_bytes: int,
        priority: str,
        access_frequency_tier: str,
        target_rpo_seconds: int,
        target_rto_seconds: int,
        budget_remaining_usd: float,
        weights_config: Optional[Dict[str, float]] = None,
        threshold_score: float = 0.5,
    ) -> DecisionResult:
        file_size_gb = file_size_bytes / (1024 ** 3)
        egress_cost = file_size_gb * settings.AWS_EGRESS_TO_GCP_PRICE_PER_GB
        storage_cost = file_size_gb * settings.GCP_STORAGE_PRICE_PER_GB_MONTH
        est_cost = egress_cost + storage_cost + (settings.GCP_PUT_OPS_PRICE_PER_1K / 1000.0)

        p = priority.upper()
        if p == "CRITICAL":
            action = "REPLICATE_NOW"
            score = 1.0
            reason = "Critical tier: zero-RPO loss tolerance requires immediate cross-cloud replica."
        elif p == "HIGH":
            action = "REPLICATE_NOW"
            score = 0.75
            reason = "High tier: asset replication approved under priority schedule."
        elif p == "MEDIUM":
            action = "DEFER_BATCH"
            score = 0.50
            reason = "Medium tier: deferred for aggregated batch replication."
        else:
            action = "SKIP"
            score = 0.25
            reason = "Low tier: non-essential asset omitted to conserve cloud egress budget."

        return DecisionResult(
            action=action,
            strategy=self.strategy_name,
            decision_score=score,
            breakdown={"priority": p, "file_size_gb": round(file_size_gb, 6)},
            estimated_cost_usd=round(est_cost, 6) if action != "SKIP" else 0.0,
            budget_remaining_usd=round(budget_remaining_usd, 4),
            reason=reason,
        )


class CostAwareAdaptiveStrategy(BaseReplicationStrategy):
    """
    Strategy 3: Cost-Aware Adaptive Replication (Core Research Contribution).
    Dynamically balances Disaster Recovery Value against Cross-Cloud Egress & Storage Costs.
    
    Mathematical Formulation:
      Phi(i) = w_p * P_hat + w_a * A_hat + w_r * R_hat + w_s * S_hat - w_c * C_hat
    
    Where:
      - P_hat: Normalized Priority [0.25, 1.0] (Low=0.25, Med=0.5, High=0.75, Critical=1.0)
      - A_hat: Access Frequency [0.1, 1.0] (Rare=0.1, Intermittent=0.5, Frequent=1.0)
      - R_hat: Normalized RPO urgency = 1 / max(1.0, RPO_hours)
      - S_hat: Size penalty dampener = 1 / (1 + ln(1 + Size_GB))
      - C_hat: Normalized total replication cost = Cost_rep / C_reference ($1.00)
    
    Hard Invariants:
      1. CRITICAL priority ALWAYS replicates immediately (RPO=0 guarantee).
      2. If Estimated Cost > Remaining Monthly Budget, action is strictly SKIP.
      3. Phi(i) >= Theta_high (0.50) -> REPLICATE_NOW
      4. Theta_low (0.35) <= Phi(i) < Theta_high -> DEFER_BATCH
      5. Phi(i) < Theta_low -> SKIP
    """

    @property
    def strategy_name(self) -> str:
        return "COST_AWARE_ADAPTIVE"

    def evaluate(
        self,
        file_size_bytes: int,
        priority: str,
        access_frequency_tier: str,
        target_rpo_seconds: int,
        target_rto_seconds: int,
        budget_remaining_usd: float,
        weights_config: Optional[Dict[str, float]] = None,
        threshold_score: float = 0.5,
    ) -> DecisionResult:
        file_size_gb = file_size_bytes / (1024 ** 3)
        egress_cost = file_size_gb * settings.AWS_EGRESS_TO_GCP_PRICE_PER_GB
        storage_cost = file_size_gb * settings.GCP_STORAGE_PRICE_PER_GB_MONTH
        ops_cost = settings.GCP_PUT_OPS_PRICE_PER_1K / 1000.0
        total_rep_cost = egress_cost + storage_cost + ops_cost

        p_norm = {"CRITICAL": 1.0, "HIGH": 0.75, "MEDIUM": 0.50, "LOW": 0.25}.get(
            priority.upper(), 0.50
        )
        a_norm = {
            "FREQUENT": 1.0,
            "INFREQUENT": 0.50,
            "INTERMITTENT": 0.50,
            "ARCHIVE": 0.10,
            "RARE": 0.10,
        }.get(access_frequency_tier.upper(), 0.50)

        rpo_hours = max(0.01, target_rpo_seconds / 3600.0)
        rpo_urgency = 1.0 / max(1.0, rpo_hours)

        # Logarithmic size dampening: small files receive high score, massive files penalized
        size_factor = 1.0 / (1.0 + math.log(1.0 + max(0.0, file_size_gb)))

        # Normalized cost relative to $1.00 USD reference benchmark
        c_reference = 1.00
        cost_penalty = min(2.0, total_rep_cost / c_reference)

        # Default weights if not specified in policy
        weights = {
            "w_p": 0.35,  # Weight on file priority
            "w_a": 0.25,  # Weight on access frequency
            "w_r": 0.15,  # Weight on RPO target urgency
            "w_s": 0.15,  # Weight on size dampener
            "w_c": 0.10,  # Penalty weight on cross-cloud financial cost
        }
        if weights_config:
            weights.update(weights_config)

        # Compute Composite Adaptive Score
        raw_score = (
            weights["w_p"] * p_norm
            + weights["w_a"] * a_norm
            + weights["w_r"] * rpo_urgency
            + weights["w_s"] * size_factor
            - weights["w_c"] * cost_penalty
        )
        score = max(0.0, min(1.0, raw_score))

        breakdown = {
            "priority": priority.upper(),
            "priority_norm": p_norm,
            "access_tier": access_frequency_tier.upper(),
            "access_norm": a_norm,
            "rpo_urgency": round(rpo_urgency, 4),
            "size_factor": round(size_factor, 4),
            "cost_penalty": round(cost_penalty, 4),
            "file_size_gb": round(file_size_gb, 6),
            "egress_cost_usd": round(egress_cost, 6),
            "storage_cost_usd": round(storage_cost, 6),
            "total_replica_cost_usd": round(total_rep_cost, 6),
            "composite_score": round(score, 4),
            "threshold": threshold_score,
        }

        # Invariant 1: CRITICAL priority ALWAYS replicates immediately (Zero RPO compromise)
        if priority.upper() == "CRITICAL":
            return DecisionResult(
                action="REPLICATE_NOW",
                strategy=self.strategy_name,
                decision_score=round(score, 4),
                breakdown=breakdown,
                estimated_cost_usd=round(total_rep_cost, 6),
                budget_remaining_usd=round(budget_remaining_usd, 4),
                reason="Mandatory Zero-RPO guarantee for CRITICAL assets: bypasses cost throttling.",
            )

        # Invariant 2: Budget Guardrail Enforcement
        if total_rep_cost > budget_remaining_usd:
            return DecisionResult(
                action="SKIP",
                strategy=self.strategy_name,
                decision_score=round(score, 4),
                breakdown=breakdown,
                estimated_cost_usd=0.0,
                budget_remaining_usd=round(budget_remaining_usd, 4),
                reason=f"Budget Guardrail: Replica cost (${round(total_rep_cost, 4)}) exceeds remaining monthly budget (${round(budget_remaining_usd, 4)}).",
            )

        # Threshold Decision Logic
        theta_high = threshold_score
        theta_low = threshold_score * 0.70

        if score >= theta_high:
            action = "REPLICATE_NOW"
            reason = f"Adaptive score ({round(score, 3)}) meets high replication threshold ({theta_high}). Disaster recovery utility justifies cross-cloud replication."
        elif score >= theta_low:
            action = "DEFER_BATCH"
            reason = f"Adaptive score ({round(score, 3)}) qualifies for deferred off-peak batch replication ({theta_low} <= score < {theta_high})."
        else:
            action = "SKIP"
            reason = f"Adaptive score ({round(score, 3)}) falls below replication threshold ({theta_low}). Cross-cloud egress cost exceeds disaster risk benefit."

        return DecisionResult(
            action=action,
            strategy=self.strategy_name,
            decision_score=round(score, 4),
            breakdown=breakdown,
            estimated_cost_usd=round(total_rep_cost, 6) if action != "SKIP" else 0.0,
            budget_remaining_usd=round(budget_remaining_usd, 4),
            reason=reason,
        )

