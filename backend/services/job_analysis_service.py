from typing import Optional

from backend.ai.gateway import LLMGateway
from backend.schemas.job import JobAnalysisResponse
from backend.services.candidate_profile_loader import CandidateProfileLoader


class JobAnalysisService:
    def __init__(
        self,
        gateway: Optional[LLMGateway] = None,
        profile_loader: Optional[CandidateProfileLoader] = None,
    ) -> None:
        self._gateway = gateway or LLMGateway()
        self._profile_loader = profile_loader or CandidateProfileLoader()

    def analyze(self, job_description: str) -> JobAnalysisResponse:
        candidate_profile = self._profile_loader.load_profile()
        candidate_projects = self._profile_loader.load_projects()

        return self._gateway.analyze_job_description(
            job_description=job_description,
            candidate_profile=candidate_profile,
            candidate_projects=candidate_projects,
        )


job_analysis_service = JobAnalysisService()
