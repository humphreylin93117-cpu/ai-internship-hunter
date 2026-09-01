from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.orm import Session

from backend.ai.gateway import LLMConfigurationError, LLMGatewayError
from backend.core.constants import JobStatus
from backend.database.session import get_db
from backend.repositories.job_repository import JobRepository
from backend.schemas.job import (
    JobAnalysisRequest,
    JobAnalysisResponse,
    JobCreate,
    JobDuplicateCheckRequest,
    JobDuplicateCheckResponse,
    JobParseRequest,
    JobParseResponse,
    JobResponse,
    JobStatusUpdate,
)
from backend.services.job_analysis_service import job_analysis_service
from backend.services.job_duplicate_service import JobDuplicateService
from backend.services.job_parsing_service import JobParsingService
from backend.services.job_service import JobNotFoundError, JobService


router = APIRouter(prefix="/jobs", tags=["jobs"])
job_parsing_service = JobParsingService()


@router.post("/analyze", response_model=JobAnalysisResponse)
def analyze_job(request: JobAnalysisRequest) -> JobAnalysisResponse:
    try:
        return job_analysis_service.analyze(request.job_description)
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM API is not configured",
        ) from exc
    except LLMGatewayError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="LLM job analysis failed",
        ) from exc


@router.post("/parse", response_model=JobParseResponse)
def parse_job(request: JobParseRequest) -> JobParseResponse:
    return job_parsing_service.parse(request.raw_text, request.job_url)


def get_job_service(db: Session = Depends(get_db)) -> JobService:
    return JobService(JobRepository(db))


def get_job_duplicate_service(
    db: Session = Depends(get_db),
) -> JobDuplicateService:
    return JobDuplicateService(JobRepository(db))


@router.post(
    "/check-duplicate",
    response_model=JobDuplicateCheckResponse,
)
def check_duplicate_job(
    request: JobDuplicateCheckRequest,
    service: JobDuplicateService = Depends(get_job_duplicate_service),
) -> JobDuplicateCheckResponse:
    return service.check(request)


@router.post(
    "",
    response_model=JobResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def create_job(
    request: JobCreate,
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    return service.create(request)


@router.get("", response_model=list[JobResponse])
def list_jobs(
    status: Optional[JobStatus] = Query(default=None),
    company: Optional[str] = Query(default=None, max_length=255),
    min_match_score: Optional[int] = Query(
        default=None,
        ge=0,
        le=100,
    ),
    service: JobService = Depends(get_job_service),
) -> list[JobResponse]:
    return service.list(
        status=status,
        company=company,
        min_match_score=min_match_score,
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    try:
        return service.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc


@router.patch("/{job_id}/status", response_model=JobResponse)
def update_job_status(
    job_id: int,
    request: JobStatusUpdate,
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    try:
        return service.update_status(job_id, request.status)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc
