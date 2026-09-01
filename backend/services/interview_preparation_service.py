import json
from hashlib import sha256
from typing import Optional

from pydantic import ValidationError

from backend.ai.gateway import LLMGateway
from backend.models.interview_preparation import InterviewPreparation
from backend.models.job import Job
from backend.repositories.interview_preparation_repository import (
    InterviewPreparationRepository,
)
from backend.repositories.job_repository import JobRepository
from backend.schemas.interview import (
    InterviewPreparationCacheResponse,
    InterviewPreparationResponse,
)
from backend.services.candidate_profile_loader import CandidateProfileLoader
from backend.services.job_service import JobNotFoundError


class InterviewPreparationService:
    def __init__(
        self,
        job_repository: JobRepository,
        preparation_repository: InterviewPreparationRepository,
        gateway: Optional[LLMGateway] = None,
        profile_loader: Optional[CandidateProfileLoader] = None,
    ) -> None:
        self._job_repository = job_repository
        self._preparation_repository = preparation_repository
        self._gateway = gateway or LLMGateway()
        self._profile_loader = profile_loader or CandidateProfileLoader()

    def prepare(
        self,
        job_id: int,
        force_regenerate: bool = False,
    ) -> InterviewPreparationResponse:
        job, profile, projects, match_analysis = self._load_sources(job_id)
        source_hash = self._calculate_source_hash(
            job.job_description,
            profile,
            projects,
            match_analysis,
        )
        cached = self._preparation_repository.get_by_job_id(job_id)
        if not force_regenerate and self._is_valid_cache(cached, source_hash):
            cached_result = self._restore_result(cached)
            if cached_result is not None:
                return cached_result

        result = self._gateway.prepare_interview_for_job(
            target_position=job.position,
            job_description=job.job_description,
            candidate_profile=profile,
            candidate_projects=projects,
            match_analysis=match_analysis,
        )
        self._preparation_repository.upsert(
            job_id=job_id,
            source_hash=source_hash,
            result=result.model_dump(mode="json"),
            model=self._gateway.model_name,
        )
        return result

    def get_cached(
        self,
        job_id: int,
    ) -> Optional[InterviewPreparationCacheResponse]:
        job, profile, projects, match_analysis = self._load_sources(job_id)
        source_hash = self._calculate_source_hash(
            job.job_description,
            profile,
            projects,
            match_analysis,
        )
        cached = self._preparation_repository.get_by_job_id(job_id)
        if not self._is_valid_cache(cached, source_hash):
            return None
        result = self._restore_result(cached)
        if result is None:
            return None
        return InterviewPreparationCacheResponse(
            result=result,
            model=cached.model,
            created_at=cached.created_at,
            updated_at=cached.updated_at,
        )

    def _load_sources(self, job_id: int) -> tuple[Job, str, str, dict]:
        job = self._job_repository.get_by_id(job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} was not found")
        match_analysis = {
            "match_score": job.match_score,
            "strengths": job.strengths,
            "weaknesses": job.weaknesses,
            "suggestions": job.suggestions,
        }
        return (
            job,
            self._profile_loader.load_profile(),
            self._profile_loader.load_projects(),
            match_analysis,
        )

    @staticmethod
    def _calculate_source_hash(
        job_description: str,
        candidate_profile: str,
        candidate_projects: str,
        match_analysis: dict,
    ) -> str:
        match_json = json.dumps(
            match_analysis,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
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
                "<match_analysis>",
                match_json,
                "</match_analysis>",
            )
        )
        return sha256(source_text.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_valid_cache(
        cached: Optional[InterviewPreparation],
        source_hash: str,
    ) -> bool:
        return cached is not None and cached.source_hash == source_hash

    @staticmethod
    def _restore_result(
        cached: InterviewPreparation,
    ) -> Optional[InterviewPreparationResponse]:
        try:
            return InterviewPreparationResponse.model_validate(cached.result)
        except ValidationError:
            return None
