import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import select

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_db
from app.core.exceptions import MultiCloudDRException, StorageProviderError
from app.core.logging import logger, setup_logging
from app.core.security import hash_password
from app.models.cloud_provider import CloudProvider
from app.models.replication import ReplicationPolicy
from app.models.user import User

# Setup Structured Logging
setup_logging("DEBUG" if settings.DEBUG else "INFO")

# Prometheus Metrics Definitions
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["endpoint"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown procedures."""
    logger.info("Initializing Multi-Cloud Data Replication Platform...")
    # Initialize database schema
    await init_db()

    # Seed default Admin user, Replication Policy, and Cloud Providers if not present
    async with AsyncSessionLocal() as session:
        try:
            # Seed User
            res_user = await session.execute(select(User).where(User.username == "admin"))
            if not res_user.scalars().first():
                admin_user = User(
                    username="admin",
                    email="admin@multicloud-dr.local",
                    hashed_password=hash_password("admin12345"),
                    role="ADMIN",
                    is_active=True,
                )
                session.add(admin_user)
                logger.info("Default administrator account seeded (admin / admin12345).")

            # Seed or Update Cloud Providers from active settings
            res_aws = await session.execute(select(CloudProvider).where(CloudProvider.name == "AWS_S3"))
            aws_p = res_aws.scalars().first()
            if not aws_p:
                aws_p = CloudProvider(
                    name="AWS_S3",
                    is_active=True,
                    is_primary=True,
                    bucket_name=settings.AWS_S3_BUCKET_NAME,
                    region=settings.AWS_DEFAULT_REGION,
                    status="HEALTHY",
                    current_latency_ms=18.5,
                )
                session.add(aws_p)
            else:
                aws_p.bucket_name = settings.AWS_S3_BUCKET_NAME
                aws_p.region = settings.AWS_DEFAULT_REGION

            res_gcp = await session.execute(select(CloudProvider).where(CloudProvider.name == "GCP_STORAGE"))
            gcp_p = res_gcp.scalars().first()
            if not gcp_p:
                gcp_p = CloudProvider(
                    name="GCP_STORAGE",
                    is_active=True,
                    is_primary=False,
                    bucket_name=settings.GCP_BUCKET_NAME,
                    region=settings.GCP_DEFAULT_LOCATION,
                    status="HEALTHY",
                    current_latency_ms=24.2,
                )
                session.add(gcp_p)
            else:
                gcp_p.bucket_name = settings.GCP_BUCKET_NAME
                gcp_p.region = settings.GCP_DEFAULT_LOCATION

            # Seed Default Cost-Aware Replication Policy
            res_policy = await session.execute(select(ReplicationPolicy).where(ReplicationPolicy.name == "Default Cost-Aware"))
            if not res_policy.scalars().first():
                default_policy = ReplicationPolicy(
                    name="Default Cost-Aware",
                    strategy_type="COST_AWARE_ADAPTIVE",
                    target_rpo_seconds=3600,
                    target_rto_seconds=300,
                    max_budget_monthly_usd=100.0,
                    weights_json='{"w_priority": 0.35, "w_access": 0.25, "w_rpo": 0.15, "w_size": 0.15, "w_cost": 0.10}',
                    threshold_score=0.5,
                    is_active=True,
                )
                session.add(default_policy)

            await session.commit()
        except Exception as e:
            logger.error(f"Error seeding default records: {e}")
            await session.rollback()

    logger.info("Multi-Cloud DR Platform initialization complete.")
    yield
    logger.info("Shutting down Multi-Cloud DR Platform...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    """Middleware to collect Prometheus metrics and measure request duration."""
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    endpoint = request.url.path
    status_code = response.status_code

    REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, status_code=status_code).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
    return response


# Global Exception Handlers
@app.exception_handler(MultiCloudDRException)
async def domain_exception_handler(request: Request, exc: MultiCloudDRException):
    logger.warning(f"Domain Exception: {exc.message} - Details: {exc.details}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": exc.__class__.__name__, "message": exc.message, "details": exc.details},
    )


@app.exception_handler(StorageProviderError)
async def storage_exception_handler(request: Request, exc: StorageProviderError):
    logger.error(f"Storage Provider Error: {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": "StorageProviderError", "message": exc.message, "details": exc.details},
    )


# System Health & Metrics Endpoints
@app.get("/health", tags=["System Health"])
async def health_check():
    """Liveness probe."""
    return {"status": "healthy", "project": settings.PROJECT_NAME, "version": "1.0.0"}


@app.get("/health/ready", tags=["System Health"])
async def readiness_check():
    """Readiness probe."""
    return {"status": "ready", "simulation_mode": settings.SIMULATION_MODE}


@app.get("/metrics", tags=["System Health"])
async def metrics_endpoint():
    """Prometheus exposition format endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Include API V1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)

