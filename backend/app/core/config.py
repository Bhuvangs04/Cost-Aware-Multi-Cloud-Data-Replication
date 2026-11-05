import os
from typing import List, Optional, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ENV_PATH = os.path.join(PROJECT_DIR, ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[ENV_PATH, ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )

    PROJECT_NAME: str = "Cost-Aware Multi-Cloud Data Replication"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "multicloud-research-project-super-secret-key-change-in-prod"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://multicloud_user:Bhuvan@localhost:5432/multicloud_dr"
    
    # Redis & Celery
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Cloud: AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_DEFAULT_REGION: str = "us-east-1"
    AWS_S3_BUCKET_NAME: str = "multicloud-dr-primary-aws"
    AWS_S3_ENDPOINT_URL: Optional[str] = None  # Custom endpoint for LocalStack/MinIO testing if needed

    # Cloud: GCP Storage
    GCP_PROJECT_ID: str = ""
    GCP_SERVICE_ACCOUNT_KEY_PATH: Optional[str] = None
    GCP_BUCKET_NAME: str = "multicloud-dr-replica-gcs"
    GCP_DEFAULT_LOCATION: str = "US"

    # Simulation Mode
    SIMULATION_MODE: bool = True
    SIMULATED_STORAGE_PATH: str = os.path.join(PROJECT_DIR, "local_simulated_cloud")
    SIMULATE_AWS_OUTAGE: bool = False
    SIMULATE_GCP_OUTAGE: bool = False
    SIMULATED_AWS_LATENCY_MS: float = 0.0
    SIMULATED_GCP_LATENCY_MS: float = 0.0
    SIMULATE_CORRUPT_CHECKSUM: bool = False

    # Pricing Models (USD)
    AWS_STORAGE_PRICE_PER_GB_MONTH: float = 0.023
    GCP_STORAGE_PRICE_PER_GB_MONTH: float = 0.020
    AWS_EGRESS_TO_GCP_PRICE_PER_GB: float = 0.090
    AWS_PUT_OPS_PRICE_PER_1K: float = 0.005
    GCP_PUT_OPS_PRICE_PER_1K: float = 0.005

    # DR and Health Probe Configuration
    HEALTH_PROBE_INTERVAL_SECONDS: int = 10
    CONSECUTIVE_FAILURE_THRESHOLD: int = 3
    HEALTH_RESTORE_THRESHOLD: int = 3

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
    ]

    @field_validator("SIMULATED_STORAGE_PATH", mode="after")
    @classmethod
    def ensure_absolute_storage_path(cls, v: str) -> str:
        if not os.path.isabs(v):
            return os.path.abspath(os.path.join(PROJECT_DIR, v))
        return v

    @field_validator("GCP_BUCKET_NAME", "AWS_S3_BUCKET_NAME", mode="after")
    @classmethod
    def strip_bucket_names(cls, v: str) -> str:
        return v.strip() if v else v


settings = Settings()

