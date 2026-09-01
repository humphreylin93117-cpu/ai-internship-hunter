from datetime import datetime, timezone
from typing import Optional

import pytest

from backend.core.constants import JobStatus
from backend.models.job import Job
from backend.schemas.job import JobCreate
from backend.services.job_service import JobNotFoundError, JobService


class FakeJobRepository:
    def __init__(self) -> None:
        self.jobs: dict[int, Job] = {}
        self.list_arguments: Optional[tuple] = None

    def create(self, job: Job) -> Job:
        job.id = len(self.jobs) + 1
        job.created_at = datetime.now(timezone.utc)
        job.updated_at = job.created_at
        self.jobs[job.id] = job
        return job

    def list(
        self,
        status: Optional[str] = None,
        company: Optional[str] = None,
        min_match_score: Optional[int] = None,
    ) -> list[Job]:
        self.list_arguments = (status, company, min_match_score)
        return list(self.jobs.values())

    def get_by_id(self, job_id: int) -> Optional[Job]:
        return self.jobs.get(job_id)

    def update_status(self, job: Job, status: str) -> Job:
        job.status = status
        job.updated_at = datetime.now(timezone.utc)
        return job


def make_job_create() -> JobCreate:
    return JobCreate(
        company=" Example Tech ",
        position="Python Intern",
        job_description="Build APIs",
        source="official",
        match_score=85,
        strengths=["Python"],
        weaknesses=["Cloud experience"],
        suggestions=["Review deployment basics"],
    )


def test_service_creates_job() -> None:
    repository = FakeJobRepository()
    service = JobService(repository)  # type: ignore[arg-type]

    created = service.create(make_job_create())

    assert created.id == 1
    assert created.company == "Example Tech"
    assert created.status == JobStatus.SAVED.value


def test_service_passes_list_filters_to_repository() -> None:
    repository = FakeJobRepository()
    service = JobService(repository)  # type: ignore[arg-type]

    service.list(JobStatus.APPLIED, "Example", 75)

    assert repository.list_arguments == ("applied", "Example", 75)


def test_service_raises_when_job_does_not_exist() -> None:
    service = JobService(FakeJobRepository())  # type: ignore[arg-type]

    with pytest.raises(JobNotFoundError):
        service.get(123)


def test_service_updates_status() -> None:
    repository = FakeJobRepository()
    service = JobService(repository)  # type: ignore[arg-type]
    created = service.create(make_job_create())

    updated = service.update_status(created.id, JobStatus.INTERVIEW_1)

    assert updated.status == "interview_1"
