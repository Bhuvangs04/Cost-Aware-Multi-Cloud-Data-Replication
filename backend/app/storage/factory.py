import os
from typing import Dict, Optional
from app.core.config import settings
from app.core.logging import logger
from app.storage.aws_s3 import AWSS3StorageAdapter
from app.storage.base import ICloudStorageProvider
from app.storage.gcp_storage import GCPStorageAdapter
from app.storage.simulation_interceptor import SimulatedStorageInterceptor

_provider_registry: Dict[str, ICloudStorageProvider] = {}


def get_storage_provider(
    provider_name: str,
    force_simulation: Optional[bool] = None,
) -> ICloudStorageProvider:
    """
    Factory function providing access to ICloudStorageProvider implementations.
    Dynamically routes between Real Cloud SDKs and Local Simulation Interceptor.
    """
    cache_key = f"{provider_name}_{force_simulation}"
    if cache_key in _provider_registry:
        return _provider_registry[cache_key]

    is_sim_mode = settings.SIMULATION_MODE if force_simulation is None else force_simulation

    if provider_name == "AWS_S3":
        has_aws_creds = bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY)
        if has_aws_creds and not is_sim_mode:
            try:
                real_adapter = AWSS3StorageAdapter(bucket_name=settings.AWS_S3_BUCKET_NAME)
                logger.info(f"Connected to real AWS S3 Storage Adapter for bucket '{settings.AWS_S3_BUCKET_NAME}'.")
                _provider_registry[cache_key] = real_adapter
                return real_adapter
            except Exception as e:
                logger.warning(f"Could not initialize real AWS S3 adapter: {e}. Falling back to simulation.")

        provider = SimulatedStorageInterceptor(
            provider_name="AWS_S3",
            bucket_name=settings.AWS_S3_BUCKET_NAME,
        )

    elif provider_name == "GCP_STORAGE":
        has_gcp_creds = bool(
            settings.GCP_SERVICE_ACCOUNT_KEY_PATH
            or os.path.exists("serviceAccount.json")
            or settings.GCP_PROJECT_ID
        )
        if has_gcp_creds and not is_sim_mode:
            try:
                real_adapter = GCPStorageAdapter(bucket_name=settings.GCP_BUCKET_NAME)
                logger.info(f"Connected to real GCP Storage Adapter for bucket '{settings.GCP_BUCKET_NAME}'.")
                _provider_registry[cache_key] = real_adapter
                return real_adapter
            except Exception as e:
                logger.warning(f"Could not initialize real GCP adapter: {e}. Falling back to simulation.")

        provider = SimulatedStorageInterceptor(
            provider_name="GCP_STORAGE",
            bucket_name=settings.GCP_BUCKET_NAME,
        )

    else:
        raise ValueError(f"Unknown cloud storage provider: '{provider_name}'")

    _provider_registry[cache_key] = provider
    return provider


def get_aws_provider() -> ICloudStorageProvider:
    return get_storage_provider("AWS_S3")


def get_gcp_provider() -> ICloudStorageProvider:
    return get_storage_provider("GCP_STORAGE")

