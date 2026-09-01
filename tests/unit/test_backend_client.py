import json

import httpx
import pytest

from frontend.api.backend_client import (
    BackendClient,
    BackendClientError,
    BackendConnectionError,
    BackendTimeoutError,
)


def make_client(handler) -> BackendClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return BackendClient(
        base_url="http://127.0.0.1:8000/",
        client=http_client,
    )


def test_analyze_job_posts_expected_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/jobs/analyze"
        assert request.read() == b'{"job_description":"Python JD"}'
        return httpx.Response(
            200,
            json={
                "match_score": 85,
                "strengths": ["Python"],
                "weaknesses": [],
                "suggestions": [],
            },
        )

    result = make_client(handler).analyze_job("Python JD")

    assert result["match_score"] == 85


def test_parse_job_posts_raw_text_and_optional_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/jobs/parse"
        assert json.loads(request.read()) == {
            "raw_text": "公司：示例科技",
            "job_url": "https://example.com/jobs/1",
        }
        return httpx.Response(
            200,
            json={
                "company": "示例科技",
                "position": "",
                "job_description": "公司：示例科技",
                "source": "官网",
                "job_url": "https://example.com/jobs/1",
            },
        )

    result = make_client(handler).parse_job(
        "公司：示例科技",
        "https://example.com/jobs/1",
    )

    assert result["company"] == "示例科技"


def test_check_duplicate_posts_confirmed_job_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/jobs/check-duplicate"
        assert json.loads(request.read()) == {
            "company": "示例科技",
            "position": "Python 实习生",
            "job_description": "Python JD",
            "job_url": None,
        }
        return httpx.Response(
            200,
            json={"is_duplicate": False, "jobs": []},
        )

    result = make_client(handler).check_job_duplicate(
        "示例科技",
        "Python 实习生",
        "Python JD",
    )

    assert result == {"is_duplicate": False, "jobs": []}


def test_discover_jobs_posts_search_conditions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/discovery/jobs"
        assert json.loads(request.read()) == {
            "keywords": ["数据分析", "Python"],
            "cities": ["广州", "深圳"],
            "max_results": 15,
        }
        return httpx.Response(
            200,
            json={"query": "combined query", "results": []},
        )

    result = make_client(handler).discover_jobs(
        keywords=["数据分析", "Python"],
        cities=["广州", "深圳"],
        max_results=15,
    )

    assert result["results"] == []


def test_extract_job_content_posts_only_selected_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/discovery/extract"
        assert json.loads(request.read()) == {
            "url": "https://example.com/jobs/1"
        }
        return httpx.Response(
            200,
            json={
                "url": "https://example.com/jobs/1",
                "content": "完整岗位正文",
            },
        )

    result = make_client(handler).extract_job_content(
        "https://example.com/jobs/1"
    )

    assert result["content"] == "完整岗位正文"


def test_create_job_posts_confirmed_analysis() -> None:
    payload = {
        "company": "Example Tech",
        "position": "Python Intern",
        "job_description": "Python JD",
        "source": "official",
        "job_url": None,
        "match_score": 85,
        "strengths": ["Python"],
        "weaknesses": [],
        "suggestions": [],
        "status": "saved",
    }

    def checking_handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/jobs"
        assert json.loads(request.read()) == payload
        return httpx.Response(201, json={**payload, "id": 9})

    result = make_client(checking_handler).create_job(payload)

    assert result["id"] == 9


def test_get_dashboard_summary_uses_summary_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/dashboard/summary"
        return httpx.Response(
            200,
            json={
                "saved_planned_count": 2,
                "pending_queue_count": 1,
                "applied_count": 3,
            },
        )

    result = make_client(handler).get_dashboard_summary()

    assert result["saved_planned_count"] == 2
    assert result["pending_queue_count"] == 1


def test_list_jobs_only_sends_active_filters() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/jobs"
        assert dict(request.url.params) == {
            "status": "applied",
            "company": "Example",
            "min_match_score": "75",
        }
        assert request.extensions["timeout"] == {
            "connect": 60.0,
            "read": 60.0,
            "write": 60.0,
            "pool": 60.0,
        }
        return httpx.Response(200, json=[])

    result = make_client(handler).list_jobs(
        status="applied",
        company=" Example ",
        min_match_score=75,
    )

    assert result == []


def test_update_status_uses_job_status_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/jobs/7/status"
        assert request.read() == b'{"status":"interview_1"}'
        return httpx.Response(200, json={"id": 7, "status": "interview_1"})

    result = make_client(handler).update_job_status(7, "interview_1")

    assert result["status"] == "interview_1"


def test_application_queue_client_methods_use_expected_endpoints() -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.method == "GET":
            assert dict(request.url.params) == {
                "sort_order": "asc",
                "status": "planned",
                "company": "Example",
                "min_match_score": "80",
            }
            return httpx.Response(200, json=[])
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"job_id": 7})

    client = make_client(handler)
    assert client.list_application_queue(
        status="planned",
        company=" Example ",
        min_match_score=80,
        sort_order="asc",
    ) == []
    assert client.add_to_application_queue(7)["job_id"] == 7
    assert client.mark_application_applied(7)["job_id"] == 7
    assert client.remove_from_application_queue(7) is None
    assert requests == [
        ("GET", "/applications/queue"),
        ("POST", "/applications/queue/7"),
        ("PATCH", "/applications/queue/7/apply"),
        ("DELETE", "/applications/queue/7"),
    ]


def test_optimize_resume_posts_selected_job_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/resumes/optimize"
        assert json.loads(request.read()) == {"job_id": 12}
        assert request.extensions["timeout"] == {
            "connect": 5.0,
            "read": 180.0,
            "write": 180.0,
            "pool": 180.0,
        }
        return httpx.Response(
            200,
            json={
                "target_position": "Python Intern",
                "priority_experiences": [],
                "keywords_to_emphasize": [],
                "content_to_deemphasize": [],
                "project_rewrites": [],
                "skill_section_suggestions": [],
                "missing_requirements": [],
                "warnings": [],
            },
        )

    result = make_client(handler).optimize_resume(12)

    assert result["target_position"] == "Python Intern"


def test_optimize_resume_can_force_regeneration() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/resumes/optimize"
        assert json.loads(request.read()) == {
            "job_id": 12,
            "force_regenerate": True,
        }
        return httpx.Response(200, json={"target_position": "Python Intern"})

    result = make_client(handler).optimize_resume(
        12,
        force_regenerate=True,
    )

    assert result["target_position"] == "Python Intern"


def test_get_cached_resume_optimization() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/resumes/optimizations/12"
        return httpx.Response(
            200,
            json={
                "result": {"target_position": "Python Intern"},
                "model": "test-model",
                "created_at": "2026-08-16T00:00:00Z",
                "updated_at": "2026-08-16T00:00:00Z",
            },
        )

    result = make_client(handler).get_cached_resume_optimization(12)

    assert result["model"] == "test-model"


def test_prepare_interview_posts_selected_job() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/interviews/prepare"
        assert json.loads(request.read()) == {
            "job_id": 8,
            "force_regenerate": True,
        }
        assert request.extensions["timeout"]["connect"] == 5.0
        assert request.extensions["timeout"]["read"] == 180.0
        return httpx.Response(
            200,
            json={"target_position": "Python Intern"},
        )

    result = make_client(handler).prepare_interview(
        8,
        force_regenerate=True,
    )

    assert result["target_position"] == "Python Intern"


def test_get_cached_interview_preparation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/interviews/preparations/8"
        return httpx.Response(
            200,
            json={
                "result": {"target_position": "Python Intern"},
                "model": "test-model",
            },
        )

    result = make_client(handler).get_cached_interview_preparation(8)

    assert result["model"] == "test-model"


def test_backend_error_exposes_safe_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            502,
            json={"detail": "LLM job analysis failed"},
        )

    with pytest.raises(BackendClientError) as error:
        make_client(handler).analyze_job("Python JD")

    assert str(error.value) == "LLM job analysis failed"
    assert error.value.status_code == 502


def test_connection_error_has_friendly_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(BackendConnectionError) as error:
        make_client(handler).list_jobs()

    assert str(error.value) == "无法连接 FastAPI 后端，请确认后端已启动。"


def test_resume_read_timeout_is_not_reported_as_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=request)

    with pytest.raises(BackendTimeoutError) as error:
        make_client(handler).optimize_resume(12)

    assert str(error.value) == "简历优化请求超时，请稍后重试。"
    assert not isinstance(error.value, BackendConnectionError)


def test_resume_502_has_specific_friendly_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            502,
            json={"detail": "LLM resume optimization failed"},
        )

    with pytest.raises(BackendClientError) as error:
        make_client(handler).optimize_resume(12)

    assert str(error.value) == "LLM简历优化失败"
    assert error.value.status_code == 502
