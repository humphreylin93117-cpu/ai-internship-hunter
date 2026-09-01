from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.api.routes.resumes import get_resume_optimization_service
from backend.main import app
from backend.schemas.resume import (
    ResumeOptimizationCacheResponse,
    ResumeOptimizationResponse,
)
from backend.services.job_service import JobNotFoundError


client = TestClient(app)


def make_response() -> ResumeOptimizationResponse:
    return ResumeOptimizationResponse(
        target_position="Python Intern",
        priority_experiences=["FastAPI project"],
        keywords_to_emphasize=["Python", "REST API"],
        content_to_deemphasize=["Unrelated content"],
        project_rewrites=[
            {
                "project": "AI Internship Hunter",
                "original": "Built a FastAPI endpoint",
                "suggested": "使用 FastAPI 实现岗位分析 REST API",
                "reason": "Matches the target backend responsibilities",
            }
        ],
        skill_section_suggestions=["Put Python first"],
        missing_requirements=["Docker is not documented"],
        warnings=["Do not claim production deployment"],
    )


def test_optimize_resume_returns_structured_response() -> None:
    expected = make_response()

    class FakeService:
        def optimize(
            self,
            job_id: int,
            force_regenerate: bool = False,
        ) -> ResumeOptimizationResponse:
            assert job_id == 1
            assert force_regenerate is False
            return expected

    app.dependency_overrides[
        get_resume_optimization_service
    ] = lambda: FakeService()
    try:
        response = client.post("/resumes/optimize", json={"job_id": 1})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == expected.model_dump()


def test_optimize_resume_returns_404_for_missing_job() -> None:
    class MissingJobService:
        def optimize(
            self,
            job_id: int,
            force_regenerate: bool = False,
        ) -> ResumeOptimizationResponse:
            raise JobNotFoundError(f"Job {job_id} was not found")

    app.dependency_overrides[
        get_resume_optimization_service
    ] = lambda: MissingJobService()
    try:
        response = client.post("/resumes/optimize", json={"job_id": 999})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}


def test_optimize_resume_passes_force_regenerate() -> None:
    expected = make_response()

    class FakeService:
        def optimize(
            self,
            job_id: int,
            force_regenerate: bool = False,
        ) -> ResumeOptimizationResponse:
            assert job_id == 4
            assert force_regenerate is True
            return expected

    app.dependency_overrides[
        get_resume_optimization_service
    ] = lambda: FakeService()
    try:
        response = client.post(
            "/resumes/optimize",
            json={"job_id": 4, "force_regenerate": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == expected.model_dump()


def test_get_cached_resume_optimization() -> None:
    expected = make_response()
    now = datetime.now(timezone.utc)

    class FakeService:
        def get_cached(self, job_id: int):
            assert job_id == 4
            return ResumeOptimizationCacheResponse(
                result=expected,
                model="test-model",
                created_at=now,
                updated_at=now,
            )

    app.dependency_overrides[
        get_resume_optimization_service
    ] = lambda: FakeService()
    try:
        response = client.get("/resumes/optimizations/4")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["result"] == expected.model_dump()
    assert response.json()["model"] == "test-model"
