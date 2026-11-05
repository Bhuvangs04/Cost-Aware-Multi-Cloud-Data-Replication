# Experimental Benchmarking Guide

This guide describes how to run and reproduce the multi-cloud disaster recovery benchmarks comparing **Strategy 1: Full Replication**, **Strategy 2: Priority-Based Tiering**, and **Strategy 3: Cost-Aware Adaptive Replication**.

---

## 1. Quick Benchmark Execution

From the project root directory, execute the automated benchmark suite:

```bash
# Using python directly
python experiments/scripts/run_benchmarks.py
```

### What Happens During the Benchmark Run:
1. **Workload Ingestion**: Synthesizes 100 enterprise test files across the 4 priority tiers (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) and 3 access frequencies (`FREQUENT`, `INFREQUENT`, `ARCHIVE`), totaling ~2.88 GB of test payloads.
2. **Multi-Strategy Evaluation**: Evaluates the identical workload sequentially against:
   - Full Replication Strategy (Baseline)
   - Priority-Based Strategy
   - Cost-Aware Adaptive Strategy
3. **Metrics Calculation**: Automatically calculates replicated data volume, cross-cloud egress fees, secondary cloud storage, net savings percentage, replication transfer latency, failover RTO, and critical asset zero-RPO compliance.
4. **Data Artifact Generation**: Saves raw output to CSV and generates a markdown thesis analysis.

---

## 2. Generated Benchmark Artifacts

The experiment suite outputs three files in `experiments/results/`:

| File | Purpose |
| :--- | :--- |
| `experiments/results/benchmark_results.csv` | High-level comparative summary table (1 row per strategy) capturing total cost, savings %, volume replicated, and RTO/RPO. |
| `experiments/results/detailed_file_decisions.csv` | Per-object audit trail (300 rows) recording file name, size, priority, tier, decision score $\Phi(i)$, action (`REPLICATE_NOW`, `DEFER_BATCH`, `SKIP`), and rationale. |
| `experiments/results/experimental_analysis.md` | Formal academic report containing mathematical formulations, empirical tables, and thesis conclusions. |

---

## 3. Running Benchmarks via the Web Dashboard

You can also run and visualize benchmarks interactively in the web UI:

1. Start the React dashboard:
   ```bash
   cd frontend
   npm run dev
   ```
2. Open your browser at `http://localhost:5173`.
3. In the sidebar, navigate to **Research Benchmarks**.
4. Click **Run Benchmark Suite**: The dashboard will execute the evaluation and update the live comparative charts and table.
5. Click **Export CSV** to download `multicloud_dr_experiment_benchmarks.csv` directly to your local workstation.

