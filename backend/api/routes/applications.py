from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi import status as http_status
from sqlalchemy.orm import Session

from backend.core.constants import JobStatus
from backend.database.session import get_db
from backend.repositories.application_repository import ApplicationRepository
from backend.repositories.job_repository import JobRepository
from backend.schemas.application import ApplicationQueueItemResponse
from backend.services.application_service import (
    ApplicationQueueItemNotFoundError,
    ApplicationService,
    InvalidApplicationStatusTransitionError,
)
from backend.services.job_service import JobNotFoundError


router = APIRouter(prefix="/applications", tags=["applications"])


def get_application_service(
    db: Session = Depends(get_db),
) -> ApplicationService:
    return ApplicationService(
        ApplicationRepository(db),
        JobRepository(db),
    )


@router.get(
    "/queue",
    response_model=list[ApplicationQueueItemResponse],
)
def list_application_queue(
    status: Optional[JobStatus] = Query(default=None),
    company: Optional[str] = Query(default=None, max_length=255),
    min_match_score: Optional[int] = Query(default=None, ge=0, le=100),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    service: ApplicationService = Depends(get_application_service),
) -> list[ApplicationQueueItemResponse]:
    return service.list_queue(
        status=status,
        company=company,
        min_match_score=min_match_score,
        sort_order=sort_order,
    )


@router.post(
    "/queue/{job_id}",
    response_model=ApplicationQueueItemResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def add_to_application_queue(
    job_id: int,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationQueueItemResponse:
    try:
        return service.add_to_queue(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc


@router.delete(
    "/queue/{job_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
def remove_from_application_queue(
    job_id: int,
    service: ApplicationService = Depends(get_application_service),
) -> Response:
    try:
        service.remove_from_queue(job_id)
    except ApplicationQueueItemNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Application queue item not found",
        ) from exc
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.patch(
    "/queue/{job_id}/apply",
    response_model=ApplicationQueueItemResponse,
)
def mark_application_applied(
    job_id: int,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationQueueItemResponse:
    try:
        return service.mark_applied(job_id)
    except ApplicationQueueItemNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Application queue item not found",
        ) from exc
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc
    except InvalidApplicationStatusTransitionError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
