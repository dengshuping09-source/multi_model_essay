from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.modules.reviews.service import provider_statuses
from app.modules.service_status import get_service_statuses
from app.schemas.review import ProviderStatusResponse, ServiceStatusResponse

router = APIRouter(tags=["review providers"])


@router.get("/review-providers", response_model=list[ProviderStatusResponse])
async def list_review_providers(_: CurrentUser) -> list[ProviderStatusResponse]:
    return [ProviderStatusResponse(**item.__dict__) for item in provider_statuses()]


@router.get("/service-status", response_model=list[ServiceStatusResponse])
async def list_service_status(_: CurrentUser) -> list[ServiceStatusResponse]:
    return [ServiceStatusResponse(**item) for item in get_service_statuses()]
