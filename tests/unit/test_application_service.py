import pytest
from sqlalchemy.orm import Session

from backend.core.constants import JobStatus
from backend.models.job import Job
from backend.repositories.application_repository import ApplicationRepository
from backend.repositories.job_repository import JobRepository
from backend.services.application_service import (
    ApplicationQueueItemNotFoundError,
    ApplicationService,
    InvalidApplicationStatusTransitionError,
)
from backend.services.job_service import JobNotFoundError


def make_service(db_session: Session) -> tuple[ApplicationService, JobRepository]:
    jobs = JobRepository(db_session)
    return ApplicationService(ApplicationRepository(db_session), jobs), jobs


def create_job(repository: JobRepository, status: str = "saved") -> Job:
    return repository.create(
        Job(
            company="Example Tech",
            position="Python Intern",
            job_description="Build APIs",
            source="official",
            job_url=None,
            match_score=85,
            strengths=[],
            weaknesses=[],
            suggestions=[],
            status=status,
        )
    )


def test_service_add_is_idempotent_and_mark_applied_updates_job(
    db_session: Session,
) -> None:
    service, jobs = make_service(db_session)
    job = create_job(jobs, status="planned")

    first = service.add_to_queue(job.id)
    second = service.add_to_queue(job.id)
    updated = service.mark_applied(job.id)

    assert first.queue_id == second.queue_id
    assert updated.status == JobStatus.APPLIED.value
    assert jobs.get_by_id(job.id).status == JobStatus.APPLIED.value


def test_service_rejects_quick_apply_from_later_status(
    db_session: Session,
) -> None:
    service, jobs = make_service(db_session)
    job = create_job(jobs, status="interview_1")
    service.add_to_queue(job.id)

    with pytest.raises(InvalidApplicationStatusTransitionError):
        service.mark_applied(job.id)


def test_service_reports_missing_job_and_queue_item(
    db_session: Session,
) -> None:
    service, jobs = make_service(db_session)
    job = create_job(jobs)

    with pytest.raises(JobNotFoundError):
        service.add_to_queue(999)
    with pytest.raises(ApplicationQueueItemNotFoundError):
        service.remove_from_queue(job.id)
