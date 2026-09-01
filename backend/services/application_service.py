from typing import Optional

from backend.core.constants import JobStatus
from backend.repositories.application_repository import (
    ApplicationQueueEntry,
    ApplicationRepository,
)
from backend.repositories.job_repository import JobRepository
from backend.services.job_service import JobNotFoundError


class ApplicationQueueItemNotFoundError(LookupError):
    """Raised when a job is not currently in the application queue."""


class InvalidApplicationStatusTransitionError(ValueError):
    """Raised when quick apply would overwrite a later workflow status."""


class ApplicationService:
    def __init__(
        self,
        application_repository: ApplicationRepository,
        job_repository: JobRepository,
    ) -> None:
        self._applications = application_repository
        self._jobs = job_repository

    def list_queue(
        self,
        status: Optional[JobStatus] = None,
        company: Optional[str] = None,
        min_match_score: Optional[int] = None,
        sort_order: str = "desc",
    ) -> list[ApplicationQueueEntry]:
        return self._applications.list(
            status=status.value if status is not None else None,
            company=company,
            min_match_score=min_match_score,
            sort_order=sort_order,
        )

    def add_to_queue(self, job_id: int) -> ApplicationQueueEntry:
        if self._jobs.get_by_id(job_id) is None:
            raise JobNotFoundError(f"Job {job_id} was not found")

        if self._applications.get_by_job_id(job_id) is None:
            self._applications.add(job_id)
        return self._require_entry(job_id)

    def remove_from_queue(self, job_id: int) -> None:
        item = self._applications.get_by_job_id(job_id)
        if item is None:
            raise ApplicationQueueItemNotFoundError(
                f"Job {job_id} is not in the application queue"
            )
        self._applications.remove(item)

    def mark_applied(self, job_id: int) -> ApplicationQueueEntry:
        self._require_entry(job_id)
        job = self._jobs.get_by_id(job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} was not found")

        allowed = {
            JobStatus.SAVED.value,
            JobStatus.PLANNED.value,
            JobStatus.APPLIED.value,
        }
        if job.status not in allowed:
            raise InvalidApplicationStatusTransitionError(
                f"Cannot quickly apply a job with status {job.status}"
            )
        if job.status != JobStatus.APPLIED.value:
            self._jobs.update_status(job, JobStatus.APPLIED.value)
        return self._require_entry(job_id)

    def _require_entry(self, job_id: int) -> ApplicationQueueEntry:
        entry = self._applications.get_entry_by_job_id(job_id)
        if entry is None:
            raise ApplicationQueueItemNotFoundError(
                f"Job {job_id} is not in the application queue"
            )
        return entry
