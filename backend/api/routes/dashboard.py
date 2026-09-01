from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.repositories.application_repository import ApplicationRepository
from backend.repositories.interview_preparation_repository import (
    InterviewPreparationRepository,
)
from backend.repositories.job_repository import JobRepository
from backend.repositories.resume_optimization_repository import (
    ResumeOptimizationRepository,
)
from backend.schemas.dashboard import DashboardSummaryResponse
from backend.services.dashboard_service import DashboardService


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def get_dashboard_service(
    db: Session = Depends(get_db),
) -> DashboardService:
    return DashboardService(
        JobRepository(db),
        ApplicationRepository(db),
        ResumeOptimizationRepository(db),
        InterviewPreparationRepository(db),
    )


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardSummaryResponse:
    return service.get_summary()
