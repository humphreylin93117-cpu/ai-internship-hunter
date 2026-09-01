from fastapi.testclient import TestClient

from backend.api.routes.interviews import get_interview_preparation_service
from backend.main import app
from backend.schemas.interview import InterviewPreparationResponse
from backend.services.job_service import JobNotFoundError


client = TestClient(app)


def make_response() -> InterviewPreparationResponse:
    return InterviewPreparationResponse(
        target_position="Python Intern",
        focus_areas=[],
        likely_questions=[],
        project_questions=[],
        risk_questions=[],
        knowledge_gaps=[],
        questions_for_interviewer=[],
    )


def test_prepare_interview_returns_structured_response() -> None:
    expected = make_response()

    class FakeService:
        def prepare(self, job_id: int, force_regenerate: bool = False):
            assert job_id == 1
            assert force_regenerate is False
            return expected

    app.dependency_overrides[
        get_interview_preparation_service
    ] = lambda: FakeService()
    try:
        response = client.post("/interviews/prepare", json={"job_id": 1})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == expected.model_dump()


def test_prepare_interview_returns_404_for_missing_job() -> None:
    class MissingService:
        def prepare(self, job_id: int, force_regenerate: bool = False):
            raise JobNotFoundError(f"Job {job_id} was not found")

    app.dependency_overrides[
        get_interview_preparation_service
    ] = lambda: MissingService()
    try:
        response = client.post(
            "/interviews/prepare",
            json={"job_id": 999},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}


def test_prepare_interview_passes_force_regenerate() -> None:
    expected = make_response()

    class FakeService:
        def prepare(self, job_id: int, force_regenerate: bool = False):
            assert job_id == 1
            assert force_regenerate is True
            return expected

    app.dependency_overrides[
        get_interview_preparation_service
    ] = lambda: FakeService()
    try:
        response = client.post(
            "/interviews/prepare",
            json={"job_id": 1, "force_regenerate": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
