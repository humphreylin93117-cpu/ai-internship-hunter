import hashlib

from backend.repositories.job_repository import JobRepository
from backend.schemas.job import (
    JobDuplicateCheckRequest,
    JobDuplicateCheckResponse,
    JobDuplicateSummary,
)


class JobDuplicateService:
    def __init__(self, repository: JobRepository) -> None:
        self._repository = repository

    def check(
        self,
        request: JobDuplicateCheckRequest,
    ) -> JobDuplicateCheckResponse:
        if request.job_url:
            matches = self._repository.find_by_job_url(request.job_url)
        else:
            source_hash = self.calculate_source_hash(
                request.company,
                request.position,
                request.job_description,
            )
            matches = [
                job
                for job in self._repository.list()
                if self.calculate_source_hash(
                    job.company,
                    job.position,
                    job.job_description,
                )
                == source_hash
            ]

        summaries = [
            JobDuplicateSummary.model_validate(job) for job in matches
        ]
        return JobDuplicateCheckResponse(
            is_duplicate=bool(summaries),
            jobs=summaries,
        )

    @staticmethod
    def calculate_source_hash(
        company: str,
        position: str,
        job_description: str,
    ) -> str:
        source = "\n".join(
            (company.strip(), position.strip(), job_description.strip())
        )
        return hashlib.sha256(source.encode("utf-8")).hexdigest()
