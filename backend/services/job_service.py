from typing import Optional

from backend.core.constants import JobStatus
from backend.models.job import Job
from backend.repositories.job_repository import JobRepository
from backend.schemas.job import JobCreate


class JobNotFoundError(LookupError):
    """Raised when a requested job does not exist."""


class JobService:
    def __init__(self, repository: JobRepository) -> None:
        self._repository = repository

    def create(self, data: JobCreate) -> Job:
        job = Job(**data.model_dump(mode="json"))
        return self._repository.create(job)

    def list(
        self,
        status: Optional[JobStatus] = None,
        company: Optional[str] = None,
        min_match_score: Optional[int] = None,
    ) -> list[Job]:
        return self._repository.list(
            status=status.value if status is not None else None,
            company=company,
            min_match_score=min_match_score,
        )

    def get(self, job_id: int) -> Job:
        job = self._repository.get_by_id(job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} was not found")
        return job

    def update_status(self, job_id: int, status: JobStatus) -> Job:
        job = self.get(job_id)
        return self._repository.update_status(job, status.value)
