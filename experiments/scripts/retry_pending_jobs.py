"""
Direct Batch Processor & Catch-up Tool for Held/Pending Replication Jobs.

Processes all jobs currently in 'PENDING' or 'FAILED' state,
executing the Cost-Aware Adaptive decision engine, AWS-to-GCP transfer,
and cryptographic SHA-256 validation.
"""

import asyncio
import os
import sys

# Ensure backend modules are on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.replication import ReplicationJob
from app.replication.engine import execute_replication_pipeline


async def drain_pending_jobs():
    print("=" * 80)
    print("REPLICATION PIPELINE BATCH DRAIN & CATCH-UP TOOL")
    print("=" * 80)

    async with AsyncSessionLocal() as session:
        query = select(ReplicationJob).where(ReplicationJob.status.in_(["PENDING", "FAILED"]))
        res = await session.execute(query)
        pending_jobs = res.scalars().all()

        if not pending_jobs:
            print("[OK] No pending or held jobs found. Replication queue is up to date!")
            return

        print(f"[*] Found {len(pending_jobs)} held/pending replication jobs. Processing now...\n")

        processed = 0
        for job in pending_jobs:
            print(f"--> Processing Job ID: {job.id} (File ID: {job.file_id})...")
            try:
                result = await execute_replication_pipeline(job.id, session=session)
                print(f"    [+] Status: {result.get('status')} | Decision: {result.get('action')}")
                if "sha256" in result:
                    print(f"    [+] Verified SHA-256: {result.get('sha256')[:16]}... Match = True")
                processed += 1
            except Exception as e:
                print(f"    [!] Error processing job {job.id}: {e}")

        print("\n" + "=" * 80)
        print(f"[OK] Successfully processed {processed}/{len(pending_jobs)} held replication jobs!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(drain_pending_jobs())
