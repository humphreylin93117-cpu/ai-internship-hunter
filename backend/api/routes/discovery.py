from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from backend.core.config import get_settings
from backend.discovery.providers.base import (
    JobDiscoveryConfigurationError,
    JobDiscoveryProviderError,
)
from backend.discovery.providers.tavily import TavilyJobDiscoveryProvider
from backend.schemas.discovery import (
    JobDiscoveryRequest,
    JobDiscoveryResponse,
    JobExtractRequest,
    JobExtractResponse,
)
from backend.services.job_discovery_service import JobDiscoveryService


router = APIRouter(prefix="/discovery", tags=["discovery"])


def get_job_discovery_service() -> JobDiscoveryService:
    settings = get_settings()
    provider = TavilyJobDiscoveryProvider(settings.tavily_api_key)
    return JobDiscoveryService(provider)


@router.post("/jobs", response_model=JobDiscoveryResponse)
def discover_jobs(
    request: JobDiscoveryRequest,
    service: JobDiscoveryService = Depends(get_job_discovery_service),
) -> JobDiscoveryResponse:
    try:
        return service.discover(request)
    except JobDiscoveryConfigurationError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job discovery provider is not configured",
        ) from exc
    except JobDiscoveryProviderError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="Job discovery provider request failed",
        ) from exc


@router.post("/extract", response_model=JobExtractResponse)
def extract_job_page(
    request: JobExtractRequest,
    service: JobDiscoveryService = Depends(get_job_discovery_service),
) -> JobExtractResponse:
    try:
        return service.extract(request.url)
    except JobDiscoveryConfigurationError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job discovery provider is not configured",
        ) from exc
    except JobDiscoveryProviderError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="Job discovery provider request failed",
        ) from exc
