from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from backend.ai.gateway import LLMConfigurationError, LLMGatewayError
from backend.database.session import get_db
from backend.repositories.interview_preparation_repository import (
    InterviewPreparationRepository,
)
from backend.repositories.job_repository import JobRepository
from backend.schemas.interview import (
    InterviewPreparationCacheResponse,
    InterviewPreparationRequest,
    InterviewPreparationResponse,
)
from backend.services.interview_preparation_service import (
    InterviewPreparationService,
)
from backend.services.job_service import JobNotFoundError


router = APIRouter(prefix="/interviews", tags=["interviews"])


def get_interview_preparation_service(
    db: Session = Depends(get_db),
) -> InterviewPreparationService:
    return InterviewPreparationService(
        JobRepository(db),
        InterviewPreparationRepository(db),
    )


@router.post("/prepare", response_model=InterviewPreparationResponse)
def prepare_interview(
    request: InterviewPreparationRequest,
    service: InterviewPreparationService = Depends(
        get_interview_preparation_service
    ),
) -> InterviewPreparationResponse:
    try:
        return service.prepare(
            request.job_id,
            force_regenerate=request.force_regenerate,
        )
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM API is not configured",
        ) from exc
    except LLMGatewayError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="LLM interview preparation failed",
        ) from exc


@router.get(
    "/preparations/{job_id}",
    response_model=Optional[InterviewPreparationCacheResponse],
)
def get_cached_interview_preparation(
    job_id: int,
    service: InterviewPreparationService = Depends(
        get_interview_preparation_service
    ),
) -> Optional[InterviewPreparationCacheResponse]:
    try:
        return service.get_cached(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc
