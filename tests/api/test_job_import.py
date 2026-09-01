from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api.routes import jobs
from backend.database.session import get_db
from backend.main import app
from backend.schemas.job import JobAnalysisResponse


def api_client(db_session: Session) -> TestClient:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def saved_job_payload(**overrides) -> dict:
    payload = {
        "company": "示例科技",
        "position": "Python 后端实习生",
        "job_description": "负责 FastAPI 后端开发",
        "source": "官网",
        "job_url": None,
        "match_score": 88,
        "strengths": ["Python 项目经验"],
        "weaknesses": ["生产经验有限"],
        "suggestions": ["准备项目讲解"],
        "status": "saved",
    }
    payload.update(overrides)
    return payload


def test_parse_job_api_preserves_original_text() -> None:
    raw_text = "公司：示例科技\n岗位：Python 实习生\n职责：开发接口"

    response = TestClient(app).post(
        "/jobs/parse",
        json={
            "raw_text": raw_text,
            "job_url": "https://careers.example.com/jobs/1",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "company": "示例科技",
        "position": "Python 实习生",
        "job_description": raw_text,
        "source": "官网",
        "job_url": "https://careers.example.com/jobs/1",
        "parse_status": "success",
        "parse_message": "已检测到有效招聘内容",
    }


def test_parse_missing_fields_returns_empty_values() -> None:
    response = TestClient(app).post(
        "/jobs/parse",
        json={"raw_text": "职责：使用 Python 开发内部工具"},
    )

    assert response.status_code == 200
    assert response.json()["company"] == ""
    assert response.json()["position"] == ""


def test_parse_navigation_page_returns_explicit_invalid_status() -> None:
    response = TestClient(app).post(
        "/jobs/parse",
        json={
            "raw_text": (
                "首页 职位分类 热门城市 热门公司 企业入口 "
                "关于我们 联系我们"
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["parse_status"] == "invalid"
    assert "导航页" in response.json()["parse_message"]
    assert response.json()["job_description"] == ""


def test_parse_login_page_returns_explicit_invalid_status() -> None:
    response = TestClient(app).post(
        "/jobs/parse",
        json={"raw_text": "账号登录 验证码登录 登录后查看职位详情"},
    )

    assert response.status_code == 200
    assert response.json()["parse_status"] == "invalid"
    assert "登录页" in response.json()["parse_message"]


def test_parse_search_page_returns_explicit_invalid_status() -> None:
    response = TestClient(app).post(
        "/jobs/parse",
        json={"raw_text": "职位列表 为您找到 50 个职位 招聘频道"},
    )

    assert response.status_code == 200
    assert response.json()["parse_status"] == "invalid"
    assert "搜索或列表页" in response.json()["parse_message"]


def test_duplicate_url_and_content_hash_detection(
    db_session: Session,
) -> None:
    test_client = api_client(db_session)
    try:
        url_job = test_client.post(
            "/jobs",
            json=saved_job_payload(
                job_url="https://example.com/jobs/duplicate"
            ),
        ).json()
        hash_job = test_client.post(
            "/jobs",
            json=saved_job_payload(
                company="无链接公司",
                position="数据实习生",
                job_description="负责 SQL 数据分析",
            ),
        ).json()

        url_response = test_client.post(
            "/jobs/check-duplicate",
            json={
                "company": "任意公司",
                "position": "任意岗位",
                "job_description": "任意 JD",
                "job_url": "https://example.com/jobs/duplicate",
            },
        )
        hash_response = test_client.post(
            "/jobs/check-duplicate",
            json={
                "company": "无链接公司",
                "position": "数据实习生",
                "job_description": "负责 SQL 数据分析",
                "job_url": None,
            },
        )

        assert url_response.status_code == 200
        assert [job["id"] for job in url_response.json()["jobs"]] == [
            url_job["id"]
        ]
        assert hash_response.status_code == 200
        assert [job["id"] for job in hash_response.json()["jobs"]] == [
            hash_job["id"]
        ]
    finally:
        app.dependency_overrides.clear()


def test_parse_analyze_and_save_complete_flow(
    db_session: Session,
    monkeypatch,
) -> None:
    test_client = api_client(db_session)
    raw_text = (
        "公司：示例科技\n"
        "岗位：Python 后端实习生\n"
        "职责：使用 FastAPI 开发接口"
    )

    def fake_analyze(job_description: str) -> JobAnalysisResponse:
        assert job_description == raw_text
        return JobAnalysisResponse(
            match_score=86,
            strengths=["Python 项目经验"],
            weaknesses=["生产经验有限"],
            suggestions=["准备项目讲解"],
        )

    monkeypatch.setattr(jobs.job_analysis_service, "analyze", fake_analyze)
    try:
        parsed = test_client.post(
            "/jobs/parse",
            json={
                "raw_text": raw_text,
                "job_url": "https://careers.example.com/jobs/2",
            },
        ).json()
        analyzed = test_client.post(
            "/jobs/analyze",
            json={"job_description": parsed["job_description"]},
        ).json()
        created = test_client.post(
            "/jobs",
            json={**parsed, **analyzed, "status": "saved"},
        )

        assert created.status_code == 201
        assert created.json()["job_url"] == (
            "https://careers.example.com/jobs/2"
        )
        assert created.json()["match_score"] == 86
    finally:
        app.dependency_overrides.clear()
