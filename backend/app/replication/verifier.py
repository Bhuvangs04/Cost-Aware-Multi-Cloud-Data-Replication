from datetime import datetime, timezone
import hashlib
from typing import Optional, Tuple
from app.core.exceptions import ChecksumMismatchError
from app.core.logging import logger
from app.storage.base import ICloudStorageProvider


class CrossCloudVerifier:
    """Cryptographic integrity verifier for cross-cloud replicated objects."""

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        hasher = hashlib.sha256()
        hasher.update(data)
        return hasher.hexdigest()

    @classmethod
    async def verify_replica_integrity(
        cls,
        primary_provider: ICloudStorageProvider,
        secondary_provider: ICloudStorageProvider,
        storage_key: str,
        expected_sha256: str,
        primary_version_id: Optional[str] = None,
        secondary_version_id: Optional[str] = None,
    ) -> Tuple[bool, str, str, str]:
        """
        Downloads and verifies byte-for-byte SHA-256 equivalence across primary (AWS) and replica (GCP).
        Returns: (is_valid, primary_sha256, replica_sha256, message)
        """
        # Download primary
        primary_bytes, primary_meta = await primary_provider.download_file(
            storage_key, version_id=primary_version_id
        )
        primary_sha256 = cls.compute_sha256(primary_bytes)

        if primary_sha256.lower() != expected_sha256.lower():
            msg = f"Primary source (AWS S3) checksum mismatch: {primary_sha256} != expected {expected_sha256}"
            logger.error(msg)
            return False, primary_sha256, "", msg

        # Download replica
        replica_bytes, replica_meta = await secondary_provider.download_file(
            storage_key, version_id=secondary_version_id
        )
        replica_sha256 = cls.compute_sha256(replica_bytes)

        if replica_sha256.lower() != expected_sha256.lower():
            msg = f"Replica destination (GCP Storage) checksum mismatch: {replica_sha256} != expected {expected_sha256}"
            logger.error(msg)
            return False, primary_sha256, replica_sha256, msg

        msg = f"Cryptographic verification succeeded: SHA-256 matches across AWS and GCP ({expected_sha256[:16]}...)."
        logger.info(msg)
        return True, primary_sha256, replica_sha256, msg

