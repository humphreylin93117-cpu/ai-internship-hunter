from hashlib import sha256
from typing import Optional

from pydantic import ValidationError

from backend.ai.gateway import LLMGateway
from backend.models.job import Job
from backend.models.resume_optimization import ResumeOptimization
from backend.repositories.job_repository import JobRepository
from backend.repositories.resume_optimization_repository import (
    ResumeOptimizationRepository,
)
from backend.schemas.resume import (
    ResumeOptimizationCacheResponse,
    ResumeOptimizationResponse,
)
from backend.services.candidate_profile_loader import CandidateProfileLoader
from backend.services.job_service import JobNotFoundError


class ResumeOptimizationService:
    def __init__(
        self,
        job_repository: JobRepository,
        optimization_repository: ResumeOptimizationRepository,
        gateway: Optional[LLMGateway] = None,
        profile_loader: Optional[CandidateProfileLoader] = None,
    ) -> None:
        self._job_repository = job_repository
        self._optimization_repository = optimization_repository
        self._gateway = gateway or LLMGateway()
        self._profile_loader = profile_loader or CandidateProfileLoader()

    def optimize(
        self,
        job_id: int,
        force_regenerate: bool = False,
    ) -> ResumeOptimizationResponse:
        job, candidate_profile, candidate_projects = self._load_sources(job_id)
        source_hash = self._calculate_source_hash(
            job.job_description,
            candidate_profile,
            candidate_projects,
        )

        cached = self._optimization_repository.get_by_job_id(job_id)
        if not force_regenerate and self._is_valid_cache(cached, source_hash):
            cached_result = self._restore_result(cached)
            if cached_result is not None:
                return cached_result

        result = self._gateway.optimize_resume_for_job(
            target_position=job.position,
            job_description=job.job_description,
            candidate_profile=candidate_profile,
            candidate_projects=candidate_projects,
        )

        self._optimization_repository.upsert(
            job_id=job_id,
            source_hash=source_hash,
            result=result.model_dump(mode="json"),
            model=self._gateway.model_name,
        )
        return result

    def get_cached(
        self,
        job_id: int,
    ) -> Optional[ResumeOptimizationCacheResponse]:
        job, candidate_profile, candidate_projects = self._load_sources(job_id)
        source_hash = self._calculate_source_hash(
            job.job_description,
            candidate_profile,
            candidate_projects,
        )
        cached = self._optimization_repository.get_by_job_id(job_id)
        if not self._is_valid_cache(cached, source_hash):
            return None

        result = self._restore_result(cached)
        if result is None:
            return None
        return ResumeOptimizationCacheResponse(
            result=result,
            model=cached.model,
            created_at=cached.created_at,
            updated_at=cached.updated_at,
        )

    def _load_sources(self, job_id: int) -> tuple[Job, str, str]:
        job = self._job_repository.get_by_id(job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} was not found")
        return (
            job,
            self._profile_loader.load_profile(),
            self._profile_loader.load_projects(),
        )

    @staticmethod
    def _calculate_source_hash(
        job_description: str,
        candidate_profile: str,
        candidate_projects: str,
    ) -> str:
        source_text = "\n".join(
            (
                "<job_description>",
                job_description,
                "</job_description>",
                "<candidate_profile>",
                candidate_profile,
                "</candidate_profile>",
                "<candidate_projects>",
                candidate_projects,
                "</candidate_projects>",
            )
        )
        return sha256(source_text.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_valid_cache(
        cached: Optional[ResumeOptimization],
        source_hash: str,
    ) -> bool:
        return cached is not None and cached.source_hash == source_hash

    @staticmethod
    def _restore_result(
        cached: ResumeOptimization,
    ) -> Optional[ResumeOptimizationResponse]:
        try:
            return ResumeOptimizationResponse.model_validate(cached.result)
        except ValidationError:
            return None
