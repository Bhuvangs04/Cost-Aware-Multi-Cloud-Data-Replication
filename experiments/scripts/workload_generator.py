"""
Standardized Multi-Cloud Disaster Recovery Workload Generator.

Generates a deterministic synthetic enterprise dataset of objects
distributed across 4 priority tiers and 3 access frequencies to provide
a rigorous, fair baseline for benchmarking the three replication strategies.
"""

from dataclasses import dataclass
import hashlib
import random
from typing import List


@dataclass
class SyntheticFile:
    file_id: str
    filename: str
    size_bytes: int
    content: bytes
    sha256_hash: str
    priority: str
    access_frequency_tier: str
    content_type: str


def generate_benchmark_workload(count: int = 100, seed: int = 42) -> List[SyntheticFile]:
    """Generate a reproducible workload with realistic enterprise distributions:

    - CRITICAL: ~20% (Financial transactions, database journals, encryption keys)
    - HIGH:     ~30% (Audit logs, legal documents, user authentication archives)
    - MEDIUM:   ~30% (Application metrics, aggregated daily reports, user avatars)
    - LOW:      ~20% (Temporary cache dumps, worker crash dumps, raw debug traces)
    """
    random.seed(seed)
    workload: List[SyntheticFile] = []

    distribution = (
        [("CRITICAL", "FREQUENT", "db_journal", 2 * 1024 * 1024, 15 * 1024 * 1024)] * 20
        + [("HIGH", "INFREQUENT", "audit_log", 5 * 1024 * 1024, 25 * 1024 * 1024)] * 30
        + [("MEDIUM", "FREQUENT", "metric_report", 10 * 1024 * 1024, 50 * 1024 * 1024)] * 30
        + [("LOW", "ARCHIVE", "crash_dump", 20 * 1024 * 1024, 100 * 1024 * 1024)] * 20
    )

    random.shuffle(distribution)

    for i in range(count):
        priority, access_tier, prefix, min_size, max_size = distribution[i]
        file_size = random.randint(min_size, max_size)

        # Generate deterministic synthetic data pattern
        seed_token = f"benchmark-file-{i:03d}-{priority}-{file_size}".encode("utf-8")
        # Generate reproducible byte content using repetition
        content = (seed_token * (file_size // len(seed_token) + 1))[:file_size]
        sha256 = hashlib.sha256(content).hexdigest()

        ext = "parquet" if priority == "CRITICAL" else ("json.gz" if priority == "HIGH" else "bin")
        filename = f"{prefix}_{i:03d}.{ext}"

        workload.append(
            SyntheticFile(
                file_id=f"bench-obj-{i:03d}",
                filename=filename,
                size_bytes=file_size,
                content=content,
                sha256_hash=sha256,
                priority=priority,
                access_frequency_tier=access_tier,
                content_type="application/octet-stream",
            )
        )

    return workload


if __name__ == "__main__":
    workload = generate_benchmark_workload(100)
    print(f"Generated {len(workload)} synthetic benchmark files.")
    total_bytes = sum(f.size_bytes for f in workload)
    print(f"Total workload size: {total_bytes / (1024 * 1024):.2f} MB")

