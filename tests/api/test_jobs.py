from backend.ai.gateway import LLMConfigurationError, LLMGatewayError
from backend.api.routes import jobs
from backend.database.session import get_db
from backend.main import app
from backend.schemas.job import JobAnalysisResponse
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


client = TestClient(app)


def job_payload(**overrides) -> dict:
    payload = {
        "company": "Example Tech",
        "position": "Python Intern",
        "job_description": "Build AI backend services with FastAPI.",
        "source": "official",
        "job_url": "https://example.com/jobs/1",
        "match_score": 85,
        "strengths": ["Python project experience"],
        "weaknesses": ["Limited cloud experience"],
        "suggestions": ["Prepare a FastAPI project demo"],
        "status": "saved",
    }
    payload.update(overrides)
    return payload


def api_client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_analyze_job_returns_structured_result(monkeypatch) -> None:
    expected = JobAnalysisResponse(
        match_score=82,
        strengths=["技术栈清晰", "适合实习生成长"],
        weaknesses=["要求较多"],
        suggestions=["准备 Python 项目案例"],
    )

    def fake_analyze(job_description: str) -> JobAnalysisResponse:
        assert job_description == "Python AI 实习生，负责 FastAPI 服务开发"
        return expected

    monkeypatch.setattr(jobs.job_analysis_service, "analyze", fake_analyze)

    response = client.post(
        "/jobs/analyze",
        json={"job_description": "  Python AI 实习生，负责 FastAPI 服务开发  "},
    )

    assert response.status_code == 200
    assert response.json() == expected.model_dump()


def test_analyze_job_rejects_blank_description() -> None:
    response = client.post(
        "/jobs/analyze",
        json={"job_description": "   "},
    )

    assert response.status_code == 422


def test_analyze_job_returns_503_when_llm_is_not_configured(
    monkeypatch,
) -> None:
    def raise_configuration_error(job_description: str) -> JobAnalysisResponse:
        raise LLMConfigurationError("missing key")

    monkeypatch.setattr(
        jobs.job_analysis_service,
        "analyze",
        raise_configuration_error,
    )

    response = client.post(
        "/jobs/analyze",
        json={"job_description": "Python 实习岗位"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "LLM API is not configured"}


def test_analyze_job_returns_502_when_llm_request_fails(
    monkeypatch,
) -> None:
    def raise_gateway_error(job_description: str) -> JobAnalysisResponse:
        raise LLMGatewayError("request failed")

    monkeypatch.setattr(
        jobs.job_analysis_service,
        "analyze",
        raise_gateway_error,
    )

    response = client.post(
        "/jobs/analyze",
        json={"job_description": "Python 实习岗位"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "LLM job analysis failed"}


def test_create_job_returns_generated_id(db_session: Session) -> None:
    test_client = api_client(db_session)

    response = test_client.post("/jobs", json=job_payload())

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["company"] == "Example Tech"
    assert body["status"] == "saved"
    assert body["created_at"]
    assert body["updated_at"]
    app.dependency_overrides.clear()


def test_list_jobs_is_newest_first(db_session: Session) -> None:
    test_client = api_client(db_session)
    first = test_client.post("/jobs", json=job_payload(company="First")).json()
    second = test_client.post("/jobs", json=job_payload(company="Second")).json()

    response = test_client.get("/jobs")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        second["id"],
        first["id"],
    ]
    app.dependency_overrides.clear()


def test_list_jobs_filters_saved_and_applied_statuses(
    db_session: Session,
) -> None:
    test_client = api_client(db_session)
    saved = test_client.post(
        "/jobs",
        json=job_payload(company="Saved", status="saved"),
    ).json()
    applied = test_client.post(
        "/jobs",
        json=job_payload(company="Applied", status="applied"),
    ).json()

    saved_response = test_client.get("/jobs", params={"status": "saved"})
    applied_response = test_client.get(
        "/jobs",
        params={"status": "applied"},
    )

    assert saved_response.status_code == 200
    assert [item["id"] for item in saved_response.json()] == [saved["id"]]
    assert all(item["status"] == "saved" for item in saved_response.json())
    assert applied_response.status_code == 200
    assert [item["id"] for item in applied_response.json()] == [applied["id"]]
    assert all(
        item["status"] == "applied" for item in applied_response.json()
    )
    app.dependency_overrides.clear()


def test_list_jobs_filters_by_minimum_match_score(
    db_session: Session,
) -> None:
    test_client = api_client(db_session)
    test_client.post("/jobs", json=job_payload(company="Low", match_score=70))
    high = test_client.post(
        "/jobs",
        json=job_payload(company="High", match_score=90),
    ).json()

    response = test_client.get("/jobs", params={"min_match_score": 75})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [high["id"]]
    app.dependency_overrides.clear()


def test_get_job_returns_full_record(db_session: Session) -> None:
    test_client = api_client(db_session)
    created = test_client.post("/jobs", json=job_payload()).json()

    response = test_client.get(f"/jobs/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created
    app.dependency_overrides.clear()


def test_get_missing_job_returns_404(db_session: Session) -> None:
    test_client = api_client(db_session)

    response = test_client.get("/jobs/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}
    app.dependency_overrides.clear()


def test_update_job_status(db_session: Session) -> None:
    test_client = api_client(db_session)
    created = test_client.post("/jobs", json=job_payload()).json()

    response = test_client.patch(
        f"/jobs/{created['id']}/status",
        json={"status": "applied"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "applied"
    assert response.json()["updated_at"]
    app.dependency_overrides.clear()


def test_update_job_rejects_invalid_status(db_session: Session) -> None:
    test_client = api_client(db_session)
    created = test_client.post("/jobs", json=job_payload()).json()

    response = test_client.patch(
        f"/jobs/{created['id']}/status",
        json={"status": "unknown"},
    )

    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_update_missing_job_returns_404(db_session: Session) -> None:
    test_client = api_client(db_session)

    response = test_client.patch(
        "/jobs/999999/status",
        json={"status": "applied"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}
    app.dependency_overrides.clear()
