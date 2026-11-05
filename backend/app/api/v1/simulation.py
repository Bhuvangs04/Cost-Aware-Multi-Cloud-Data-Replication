from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.schemas.experiment import SimulationControlRequest, SimulationControlResponse

router = APIRouter(prefix="/simulation", tags=["Failure Simulation"])


@router.get("/status", response_model=SimulationControlResponse)
async def get_simulation_status(current_user: User = Depends(get_current_user)):
    """Retrieves current simulation control settings (outages, latency, corruption)."""
    return SimulationControlResponse(
        simulation_mode=settings.SIMULATION_MODE,
        simulate_aws_outage=settings.SIMULATE_AWS_OUTAGE,
        simulate_gcp_outage=settings.SIMULATE_GCP_OUTAGE,
        simulated_aws_latency_ms=settings.SIMULATED_AWS_LATENCY_MS,
        simulated_gcp_latency_ms=settings.SIMULATED_GCP_LATENCY_MS,
        simulate_corrupt_checksum=settings.SIMULATE_CORRUPT_CHECKSUM,
        message="Current simulation state retrieved.",
    )


@router.post("/configure", response_model=SimulationControlResponse)
async def configure_simulation(
    request: SimulationControlRequest,
    current_user: User = Depends(get_current_user),
):
    """Updates simulation settings dynamically to test disaster recovery scenarios."""
    if request.simulate_aws_outage is not None:
        settings.SIMULATE_AWS_OUTAGE = request.simulate_aws_outage
    if request.simulate_gcp_outage is not None:
        settings.SIMULATE_GCP_OUTAGE = request.simulate_gcp_outage
    if request.simulated_aws_latency_ms is not None:
        settings.SIMULATED_AWS_LATENCY_MS = request.simulated_aws_latency_ms
    if request.simulated_gcp_latency_ms is not None:
        settings.SIMULATED_GCP_LATENCY_MS = request.simulated_gcp_latency_ms
    if request.simulate_corrupt_checksum is not None:
        settings.SIMULATE_CORRUPT_CHECKSUM = request.simulate_corrupt_checksum

    return SimulationControlResponse(
        simulation_mode=settings.SIMULATION_MODE,
        simulate_aws_outage=settings.SIMULATE_AWS_OUTAGE,
        simulate_gcp_outage=settings.SIMULATE_GCP_OUTAGE,
        simulated_aws_latency_ms=settings.SIMULATED_AWS_LATENCY_MS,
        simulated_gcp_latency_ms=settings.SIMULATED_GCP_LATENCY_MS,
        simulate_corrupt_checksum=settings.SIMULATE_CORRUPT_CHECKSUM,
        message="Simulation configuration successfully updated.",
    )


@router.post("/reset", response_model=SimulationControlResponse)
async def reset_simulation(current_user: User = Depends(get_current_user)):
    """Resets all simulated failures back to normal healthy operations."""
    settings.SIMULATE_AWS_OUTAGE = False
    settings.SIMULATE_GCP_OUTAGE = False
    settings.SIMULATED_AWS_LATENCY_MS = 0.0
    settings.SIMULATED_GCP_LATENCY_MS = 0.0
    settings.SIMULATE_CORRUPT_CHECKSUM = False

    return SimulationControlResponse(
        simulation_mode=settings.SIMULATION_MODE,
        simulate_aws_outage=False,
        simulate_gcp_outage=False,
        simulated_aws_latency_ms=0.0,
        simulated_gcp_latency_ms=0.0,
        simulate_corrupt_checksum=False,
        message="Simulation environment reset to normal healthy operations.",
    )

