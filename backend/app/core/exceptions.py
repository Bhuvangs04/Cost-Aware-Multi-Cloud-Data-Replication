from typing import Any, Dict, Optional


class MultiCloudDRException(Exception):
    """Base exception for all domain errors within the Multi-Cloud DR platform."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class StorageProviderError(MultiCloudDRException):
    """Raised when an underlying cloud storage operation fails."""
    pass


class ProviderUnavailableError(StorageProviderError):
    """Raised when a cloud provider (AWS S3 or GCP Storage) is unreachable or in outage."""
    pass


class ObjectNotFoundError(StorageProviderError):
    """Raised when a requested file or object version does not exist in the storage provider."""
    pass


class ChecksumMismatchError(StorageProviderError):
    """Raised when SHA-256 verification fails during replication or integrity check."""
    pass


class ReplicationError(MultiCloudDRException):
    """Raised when the replication engine encounters an unrecoverable processing error."""
    pass


class PolicyEvaluationError(MultiCloudDRException):
    """Raised when a replication policy cannot be evaluated."""
    pass


class BudgetExceededError(ReplicationError):
    """Raised when a replication job is rejected due to strict monthly budget limits."""
    pass


class FailoverActiveError(MultiCloudDRException):
    """Raised when an operation cannot be performed because disaster recovery failover is active."""
    pass


class ReconciliationConflictError(MultiCloudDRException):
    """Raised when conflict resolution during primary recovery cannot be resolved automatically."""
    pass


class AuthenticationError(MultiCloudDRException):
    """Raised for authentication failures."""
    pass


class PermissionDeniedError(MultiCloudDRException):
    """Raised when a user lacks required permissions."""
    pass

