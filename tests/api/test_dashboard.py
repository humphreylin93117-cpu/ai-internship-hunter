from fastapi.testclient import TestClient

from backend.api.routes.dashboard import get_dashboard_service
from backend.main import app
from backend.schemas.dashboard import (
    DashboardStageSummary,
    DashboardSummaryResponse,
)


client = TestClient(app)


def test_dashboard_summary_api_uses_service() -> None:
    expected = DashboardSummaryResponse(
        saved_planned_count=3,
        pending_queue_count=2,
        applied_count=1,
        assessment_interview_count=2,
        offer_count=1,
        rejected_count=1,
        abandoned_count=0,
        average_match_score=82.5,
        stages=DashboardStageSummary(
            saved_planned=3,
            applied=1,
            assessment_interview=2,
            offer=1,
            rejected=1,
            abandoned=0,
        ),
    )

    class FakeDashboardService:
        def get_summary(self):
            return expected

    app.dependency_overrides[get_dashboard_service] = (
        lambda: FakeDashboardService()
    )
    try:
        response = client.get("/dashboard/summary")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == expected.model_dump()
