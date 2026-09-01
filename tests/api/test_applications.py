from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.main import app
from backend.repositories.interview_preparation_repository import (
    InterviewPreparationRepository,
)
from backend.repositories.resume_optimization_repository import (
    ResumeOptimizationRepository,
)


def job_payload(**overrides) -> dict:
    payload = {
        "company": "Example Tech",
        "position": "Python Intern",
        "job_description": "Build AI backend services with FastAPI.",
        "source": "official",
        "job_url": "https://example.com/jobs/1",
        "match_score": 85,
        "strengths": ["Python"],
        "weaknesses": [],
        "suggestions": [],
        "status": "saved",
    }
    payload.update(overrides)
    return payload


def api_client(db_session: Session) -> TestClient:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_queue_add_is_persistent_and_idempotent(db_session: Session) -> None:
    client = api_client(db_session)
    try:
        job = client.post("/jobs", json=job_payload()).json()

        first = client.post(f"/applications/queue/{job['id']}")
        second = client.post(f"/applications/queue/{job['id']}")
        listed = client.get("/applications/queue")
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["queue_id"] == second.json()["queue_id"]
    assert [item["job_id"] for item in listed.json()] == [job["id"]]


def test_queue_lists_filters_sorting_and_generation_flags(
    db_session: Session,
) -> None:
    client = api_client(db_session)
    try:
        low = client.post(
            "/jobs",
            json=job_payload(company="Low Corp", match_score=70),
        ).json()
        high = client.post(
            "/jobs",
            json=job_payload(
                company="Example Labs",
                match_score=94,
                status="planned",
            ),
        ).json()
        client.post(f"/applications/queue/{low['id']}")
        client.post(f"/applications/queue/{high['id']}")
        ResumeOptimizationRepository(db_session).upsert(
            high["id"],
            "a" * 64,
            {"target_position": high["position"]},
            "test-model",
        )
        InterviewPreparationRepository(db_session).upsert(
            high["id"],
            "b" * 64,
            {"target_position": high["position"]},
            "test-model",
        )

        response = client.get(
            "/applications/queue",
            params={
                "status": "planned",
                "company": "example",
                "min_match_score": 80,
                "sort_order": "desc",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()) == 1
    item = response.json()[0]
    assert item["job_id"] == high["id"]
    assert item["has_resume_optimization"] is True
    assert item["has_interview_preparation"] is True


def test_queue_can_mark_saved_job_applied_and_remove_it(
    db_session: Session,
) -> None:
    client = api_client(db_session)
    try:
        job = client.post("/jobs", json=job_payload()).json()
        client.post(f"/applications/queue/{job['id']}")

        applied = client.patch(f"/applications/queue/{job['id']}/apply")
        after_apply = client.get("/applications/queue")
        removed = client.delete(f"/applications/queue/{job['id']}")
        listed = client.get("/applications/queue")
    finally:
        app.dependency_overrides.clear()

    assert applied.status_code == 200
    assert applied.json()["status"] == "applied"
    assert after_apply.json()[0]["status"] == "applied"
    assert removed.status_code == 204
    assert listed.json() == []


def test_follow_up_status_update_is_immediately_visible_in_queue(
    db_session: Session,
) -> None:
    client = api_client(db_session)
    try:
        job = client.post(
            "/jobs",
            json=job_payload(status="applied"),
        ).json()
        client.post(f"/applications/queue/{job['id']}")

        updated = client.patch(
            f"/jobs/{job['id']}/status",
            json={"status": "written_test"},
        )
        listed = client.get("/applications/queue")
    finally:
        app.dependency_overrides.clear()

    assert updated.status_code == 200
    assert updated.json()["status"] == "written_test"
    assert listed.json()[0]["status"] == "written_test"


def test_queue_rejects_invalid_quick_apply_and_missing_jobs(
    db_session: Session,
) -> None:
    client = api_client(db_session)
    try:
        job = client.post(
            "/jobs",
            json=job_payload(status="interview_1"),
        ).json()
        client.post(f"/applications/queue/{job['id']}")

        invalid = client.patch(f"/applications/queue/{job['id']}/apply")
        missing_job = client.post("/applications/queue/999999")
        missing_item = client.delete("/applications/queue/999999")
    finally:
        app.dependency_overrides.clear()

    assert invalid.status_code == 409
    assert missing_job.status_code == 404
    assert missing_item.status_code == 404
