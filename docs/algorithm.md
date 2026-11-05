# Mathematical Specification: Cost-Aware Adaptive Replication Algorithm

## 1. Problem Formulation & Research Objective

In distributed multi-cloud architectures, maintaining high data availability across heterogeneous cloud storage providers (AWS S3 and GCP GCS) incurs significant operational expenditure:
1. **Cross-Cloud Data Egress**: AWS charges \\$0.09 per GB transferred out to the public internet or external cloud networks.
2. **Duplicate Storage Fees**: Storing cold, non-essential, or ephemeral files redundantly in secondary clouds inflates monthly infrastructure budgets without providing proportional disaster recovery utility.

The objective of the **Cost-Aware Adaptive Replication Engine** is to determine whether and when an uploaded object $i$ should be replicated from AWS S3 to Google Cloud Storage by evaluating its recovery benefit against its financial replication cost.

---

## 2. Mathematical Decision Model

Each candidate object $i$ submitted to the replication pipeline is evaluated by a composite scoring function $\Phi(i) \in [0.0, 1.0]$:

$$\Phi(i) = w_p \hat{P}_i + w_a \hat{A}_i + w_r \hat{R}_i + w_s \hat{S}_i - w_c \hat{C}_i$$

Subject to normalized parameter weights:

$$\sum \{w_p, w_a, w_r, w_s, w_c\} = 1.00$$

### Normalized Component Definitions

#### 1. File Priority Factor ($\hat{P}_i \in [0.25, 1.00]$)
Captures business criticality and disaster recovery value:
$$\hat{P}_i = \begin{cases} 
1.00, & \text{if Priority} = \text{CRITICAL} \\
0.75, & \text{if Priority} = \text{HIGH} \\
0.50, & \text{if Priority} = \text{MEDIUM} \\
0.25, & \text{if Priority} = \text{LOW}
\end{cases}$$

#### 2. Access Frequency Factor ($\hat{A}_i \in [0.10, 1.00]$)
Reflects operational utility and read demand:
$$\hat{A}_i = \begin{cases} 
1.00, & \text{if Tier} = \text{FREQUENT (Hot data)} \\
0.50, & \text{if Tier} \in \{\text{INFREQUENT}, \text{INTERMITTENT}\} \\
0.10, & \text{if Tier} \in \{\text{ARCHIVE}, \text{RARE}\}
\end{cases}$$

#### 3. Recovery Urgency Factor ($\hat{R}_i \in (0.00, 1.00]$)
Derived from the target Recovery Point Objective (RPO) configured in the active policy:
$$\hat{R}_i = \frac{1}{\max(1.0, \text{RPO}_{\text{hours}})} = \frac{3600}{\max(3600, \text{Target RPO in seconds})}$$
Stricter RPO targets (e.g. 60 seconds) produce $\hat{R}_i \to 1.00$, increasing replication priority.

#### 4. Size Retention Dampener ($\hat{S}_i \in (0.00, 1.00]$)
Prevents large low-utility objects from consuming disproportional replication resources while rewarding compact, high-value payloads:
$$\hat{S}_i = \frac{1}{1 + \ln(1 + \text{Size in GB})}$$

#### 5. Cross-Cloud Cost Penalty ($\hat{C}_i \ge 0.00$)
Normalizes total replication cost (egress transfer + secondary storage + API operations) against a reference unit cost $C_{\text{ref}} = \$1.00$:
$$\text{Cost}_{\text{rep}}(i) = (\text{Size}_{\text{GB}} \times \text{Price}_{\text{egress}}) + (\text{Size}_{\text{GB}} \times \text{Price}_{\text{gcp\_storage}}) + \text{Price}_{\text{put\_op}}$$
$$\hat{C}_i = \min\left(2.0, \frac{\text{Cost}_{\text{rep}}(i)}{C_{\text{ref}}}\right)$$

---

## 3. Hard Operational Invariants & Guardrails

To ensure safety and reliability in production, the engine enforces three non-negotiable operational invariants:

```mermaid
flowchart TD
    Start["Evaluate Candidate Object i"] --> CheckCritical{"Priority == CRITICAL?"}
    CheckCritical -->|Yes| Bypass["Action: REPLICATE_NOW\n(Score = 1.0, Zero-RPO Invariant)"]
    CheckCritical -->|No| CheckBudget{"Spend + Cost > Budget_Max?"}
    CheckBudget -->|Yes| BudgetExceeded["Action: SKIP\n(Budget Guardrail Enforced)"]
    CheckBudget -->|No| ComputeScore["Compute Composite Score Phi(i)"]
    
    ComputeScore --> ScoreBranch{"Evaluate Phi(i) against Thresholds"}
    ScoreBranch -->|Phi >= Theta_High (0.50)| ReplicateNow["Action: REPLICATE_NOW\n(High DR Utility)"]
    ScoreBranch -->|Theta_Low <= Phi < Theta_High| DeferBatch["Action: DEFER_BATCH\n(Off-Peak Batch Replication)"]
    ScoreBranch -->|Phi < Theta_Low (0.35)| SkipObject["Action: SKIP\n(Omitted to Conserve Budget)"]
```

### Invariant 1: Critical Asset Zero-RPO Invariant
If $\text{Priority}_i = \text{CRITICAL}$, the scoring evaluation and cost penalty are explicitly bypassed:
$$\Phi(i) \leftarrow 1.00, \quad \text{Action} \leftarrow \text{REPLICATE\_NOW}$$
**Guarantee**: 100% of critical objects are replicated immediately to GCS, ensuring zero data loss ($\text{RPO} = 0.00\text{s}$) upon primary cloud failure.

### Invariant 2: Hard Monthly Budget Ceiling
If the projected cumulative monthly replication spend exceeds the administrator's configured budget cap:
$$\text{Spend}_{\text{current}} + \text{Cost}_{\text{rep}}(i) > \text{Budget}_{\text{max}} \implies \text{Action} \leftarrow \text{SKIP}$$
Prevents unexpected cross-cloud egress billing shocks.

### Invariant 3: Tri-State Action Gating
For non-critical objects within budget:
- **$\Phi(i) \ge \theta_{\text{high}} = 0.50$**: $\implies \text{REPLICATE\_NOW}$ (Immediate asynchronous dispatch).
- **$\theta_{\text{low}} \le \Phi(i) < \theta_{\text{high}}$ ($0.35 \le \Phi < 0.50$)**: $\implies \text{DEFER\_BATCH}$ (Scheduled for off-peak synchronization).
- **$\Phi(i) < \theta_{\text{low}} = 0.35$**: $\implies \text{SKIP}$ (Replication omitted; object maintained solely in AWS S3).

---

## 4. Complexity & Performance Analysis

- **Time Complexity**: $\mathcal{O}(1)$ constant-time calculation per object. The scoring formula requires only basic arithmetic and a single natural logarithm operation ($\ln$).
- **Space Complexity**: $\mathcal{O}(1)$ auxiliary space. The decision metadata and explanation dictionary require $< 512$ bytes in memory.
- **Explainability**: Every decision produces a transparent JSON audit trace containing all normalized factors ($\hat{P}_i, \hat{A}_i, \hat{R}_i, \hat{S}_i, \hat{C}_i$) and the explicit business rationale displayed in the management dashboard.

---

## 5. Assumptions & Limitations

1. **Pricing Stability Assumption**: Cloud pricing matrices (AWS egress at \\$0.09/GB, GCP storage at \\$0.02/GB) are treated as configurable configuration constants rather than dynamic real-time spot market prices.
2. **Deterministic Classification**: Object priority tiers (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) are assigned at ingestion by application clients or metadata policies.
3. **No Distributed Transactions**: Replication is strictly asynchronous. Distributed cross-cloud 2-phase commit (2PC) is neither assumed nor implemented, aligning with standard cloud eventual-consistency models.

