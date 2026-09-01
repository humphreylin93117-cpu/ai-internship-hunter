from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from backend.ai.gateway import LLMConfigurationError, LLMGatewayError
from backend.database.session import get_db
from backend.repositories.job_repository import JobRepository
from backend.repositories.resume_optimization_repository import (
    ResumeOptimizationRepository,
)
from backend.schemas.resume import (
    ResumeOptimizationCacheResponse,
    ResumeOptimizationRequest,
    ResumeOptimizationResponse,
)
from backend.services.job_service import JobNotFoundError
from backend.services.resume_optimization_service import (
    ResumeOptimizationService,
)


router = APIRouter(prefix="/resumes", tags=["resumes"])


def get_resume_optimization_service(
    db: Session = Depends(get_db),
) -> ResumeOptimizationService:
    return ResumeOptimizationService(
        JobRepository(db),
        ResumeOptimizationRepository(db),
    )


@router.post("/optimize", response_model=ResumeOptimizationResponse)
def optimize_resume(
    request: ResumeOptimizationRequest,
    service: ResumeOptimizationService = Depends(
        get_resume_optimization_service
    ),
) -> ResumeOptimizationResponse:
    try:
        return service.optimize(
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
            detail="LLM resume optimization failed",
        ) from exc


@router.get(
    "/optimizations/{job_id}",
    response_model=Optional[ResumeOptimizationCacheResponse],
)
def get_cached_resume_optimization(
    job_id: int,
    service: ResumeOptimizationService = Depends(
        get_resume_optimization_service
    ),
) -> Optional[ResumeOptimizationCacheResponse]:
    try:
        return service.get_cached(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc
