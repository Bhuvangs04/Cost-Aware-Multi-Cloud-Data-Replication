from fastapi import APIRouter
from app.api.v1 import (
    auth,
    cost_analytics,
    disaster_recovery,
    experiments,
    files,
    providers,
    replication,
    simulation,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(files.router)
api_router.include_router(providers.router)
api_router.include_router(replication.router)
api_router.include_router(disaster_recovery.router)
api_router.include_router(cost_analytics.router, prefix="/cost")
api_router.include_router(cost_analytics.router, prefix="/costs")
api_router.include_router(simulation.router)
api_router.include_router(experiments.router)

