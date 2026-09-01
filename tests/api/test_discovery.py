from fastapi.testclient import TestClient

from backend.api.routes.discovery import get_job_discovery_service
from backend.discovery.providers.base import (
    JobDiscoveryConfigurationError,
    JobDiscoveryProviderError,
)
from backend.main import app
from backend.schemas.discovery import (
    DiscoveredJob,
    JobDiscoveryResponse,
    JobExtractResponse,
)


client = TestClient(app)


def test_unconfigured_provider_returns_503() -> None:
    class UnconfiguredService:
        def discover(self, request):
            raise JobDiscoveryConfigurationError("missing key")

    app.dependency_overrides[get_job_discovery_service] = (
        lambda: UnconfiguredService()
    )
    try:
        response = client.post(
            "/discovery/jobs",
            json={
                "keywords": ["Python"],
                "cities": ["深圳"],
                "max_results": 10,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Job discovery provider is not configured"
    }


def test_normal_search_returns_discovered_jobs() -> None:
    expected = JobDiscoveryResponse(
        query="深圳 Python 实习 招聘",
        results=[
            DiscoveredJob(
                title="Python 实习生招聘",
                url="https://example.com/jobs/1",
                snippet="负责后端岗位开发",
                source_domain="example.com",
                provider="tavily",
            )
        ],
    )

    class SearchService:
        def discover(self, request):
            assert request.keywords == ["Python"]
            return expected

    app.dependency_overrides[get_job_discovery_service] = (
        lambda: SearchService()
    )
    try:
        response = client.post(
            "/discovery/jobs",
            json={"keywords": ["Python"], "cities": ["深圳"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == expected.model_dump()


def test_provider_failure_returns_502() -> None:
    class FailingService:
        def discover(self, request):
            raise JobDiscoveryProviderError("Tavily failed")

    app.dependency_overrides[get_job_discovery_service] = (
        lambda: FailingService()
    )
    try:
        response = client.post(
            "/discovery/jobs",
            json={"keywords": ["Python"], "cities": ["深圳"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Job discovery provider request failed"
    }


def test_extract_success() -> None:
    class ExtractService:
        def extract(self, url):
            return JobExtractResponse(url=url, content="完整公开岗位正文")

    app.dependency_overrides[get_job_discovery_service] = (
        lambda: ExtractService()
    )
    try:
        response = client.post(
            "/discovery/extract",
            json={"url": "https://example.com/jobs/1"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["content"] == "完整公开岗位正文"
    assert response.json()["is_complete"] is True


def test_extract_failure_returns_502() -> None:
    class FailingExtractService:
        def extract(self, url):
            raise JobDiscoveryProviderError("extract failed")

    app.dependency_overrides[get_job_discovery_service] = (
        lambda: FailingExtractService()
    )
    try:
        response = client.post(
            "/discovery/extract",
            json={"url": "https://example.com/jobs/1"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502


def test_discovery_result_can_enter_existing_parse_flow() -> None:
    content = (
        "公司：示例科技\n岗位：Python 实习生\n"
        "岗位职责：使用 Python 开发和维护内部接口。\n"
        "任职要求：熟悉 FastAPI，并具备良好沟通能力。"
    )

    class ImportService:
        def discover(self, request):
            return JobDiscoveryResponse(
                query="深圳 Python 实习 招聘",
                results=[
                    DiscoveredJob(
                        title="Python 实习生招聘",
                        url="https://careers.example.com/jobs/1",
                        snippet="公开招聘岗位",
                        source_domain="careers.example.com",
                        provider="tavily",
                    )
                ],
            )

        def extract(self, url):
            return JobExtractResponse(url=url, content=content)

    app.dependency_overrides[get_job_discovery_service] = (
        lambda: ImportService()
    )
    try:
        discovered = client.post(
            "/discovery/jobs",
            json={"keywords": ["Python"], "cities": ["深圳"]},
        ).json()["results"][0]
        extracted = client.post(
            "/discovery/extract",
            json={"url": discovered["url"]},
        ).json()
        parsed = client.post(
            "/jobs/parse",
            json={
                "raw_text": extracted["content"],
                "job_url": extracted["url"],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert parsed.status_code == 200
    assert parsed.json()["company"] == "示例科技"
    assert parsed.json()["position"] == "Python 实习生"
