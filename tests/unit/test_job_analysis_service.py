from backend.schemas.job import JobAnalysisResponse
from backend.services.job_analysis_service import JobAnalysisService


class FakeGateway:
    def __init__(self, result: JobAnalysisResponse) -> None:
        self.result = result
        self.received_input = None

    def analyze_job_description(
        self,
        job_description: str,
        candidate_profile: str,
        candidate_projects: str,
    ) -> JobAnalysisResponse:
        self.received_input = {
            "job_description": job_description,
            "candidate_profile": candidate_profile,
            "candidate_projects": candidate_projects,
        }
        return self.result


class FakeProfileLoader:
    def load_profile(self) -> str:
        return "候选人掌握 Python 和 FastAPI"

    def load_projects(self) -> str:
        return "候选人开发过 AI 求职助手"


def test_service_delegates_job_analysis_to_gateway() -> None:
    expected = JobAnalysisResponse(
        match_score=75,
        strengths=["职责明确"],
        weaknesses=["经验要求偏高"],
        suggestions=["准备相关项目"],
    )
    gateway = FakeGateway(expected)
    service = JobAnalysisService(
        gateway=gateway,
        profile_loader=FakeProfileLoader(),
    )

    result = service.analyze("目标岗位 JD")

    assert result == expected
    assert gateway.received_input == {
        "job_description": "目标岗位 JD",
        "candidate_profile": "候选人掌握 Python 和 FastAPI",
        "candidate_projects": "候选人开发过 AI 求职助手",
    }
