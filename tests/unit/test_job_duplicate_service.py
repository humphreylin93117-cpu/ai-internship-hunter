from datetime import datetime
from types import SimpleNamespace

from backend.schemas.job import JobDuplicateCheckRequest
from backend.services.job_duplicate_service import JobDuplicateService


def make_job(
    job_id: int,
    job_url=None,
    company: str = "示例科技",
    position: str = "Python 实习生",
    job_description: str = "负责 FastAPI 后端开发",
):
    return SimpleNamespace(
        id=job_id,
        company=company,
        position=position,
        job_description=job_description,
        job_url=job_url,
        status="saved",
        created_at=datetime(2026, 8, 16),
    )


class FakeRepository:
    def __init__(self, url_jobs=None, jobs=None) -> None:
        self.url_jobs = url_jobs or []
        self.jobs = jobs or []
        self.requested_url = None

    def find_by_job_url(self, job_url):
        self.requested_url = job_url
        return self.url_jobs

    def list(self):
        return self.jobs


def test_duplicate_url_has_priority() -> None:
    repository = FakeRepository(
        url_jobs=[make_job(1, "https://example.com/jobs/1")],
        jobs=[make_job(2)],
    )
    service = JobDuplicateService(repository)

    result = service.check(
        JobDuplicateCheckRequest(
            company="不同公司",
            position="不同岗位",
            job_description="不同 JD",
            job_url="https://example.com/jobs/1",
        )
    )

    assert result.is_duplicate is True
    assert [job.id for job in result.jobs] == [1]
    assert repository.requested_url == "https://example.com/jobs/1"


def test_duplicate_without_url_uses_content_hash() -> None:
    repository = FakeRepository(jobs=[make_job(3), make_job(4)])
    service = JobDuplicateService(repository)

    result = service.check(
        JobDuplicateCheckRequest(
            company="示例科技",
            position="Python 实习生",
            job_description="负责 FastAPI 后端开发",
        )
    )

    assert result.is_duplicate is True
    assert [job.id for job in result.jobs] == [3, 4]


def test_different_content_is_not_duplicate() -> None:
    service = JobDuplicateService(
        FakeRepository(jobs=[make_job(5)])
    )

    result = service.check(
        JobDuplicateCheckRequest(
            company="示例科技",
            position="数据分析实习生",
            job_description="负责 SQL 数据分析",
        )
    )

    assert result.is_duplicate is False
    assert result.jobs == []
