from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.cloud_provider import CloudProvider
from app.models.user import User
from app.schemas.disaster_recovery import CloudProviderRead

router = APIRouter(prefix="/providers", tags=["Cloud Providers"])


@router.get("", response_model=List[CloudProviderRead])
@router.get("/", response_model=List[CloudProviderRead])
async def list_providers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves all registered cloud storage providers and their health status."""
    result = await db.execute(select(CloudProvider))
    return result.scalars().all()


@router.get("/{provider_id}", response_model=CloudProviderRead)
async def get_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves a specific cloud provider by ID."""
    result = await db.execute(select(CloudProvider).where(CloudProvider.id == provider_id))
    provider = result.scalars().first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider

