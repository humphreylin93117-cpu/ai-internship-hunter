from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.ai.gateway import LLMGatewayError
from backend.schemas.interview import InterviewPreparationResponse
from backend.services.interview_preparation_service import (
    InterviewPreparationService,
)
from backend.services.job_service import JobNotFoundError


class FakeJobRepository:
    def __init__(self, job=None) -> None:
        self.job = job

    def get_by_id(self, job_id: int):
        return self.job if self.job and self.job.id == job_id else None


class FakePreparationRepository:
    def __init__(self) -> None:
        self.cached = None
        self.upsert_calls = []

    def get_by_job_id(self, job_id: int):
        if self.cached and self.cached.job_id == job_id:
            return self.cached
        return None

    def upsert(self, **kwargs):
        self.upsert_calls.append(kwargs)
        now = datetime.now(timezone.utc)
        created_at = self.cached.created_at if self.cached else now
        self.cached = SimpleNamespace(
            id=1,
            created_at=created_at,
            updated_at=now,
            **kwargs,
        )
        return self.cached


class FakeLoader:
    def __init__(self) -> None:
        self.profile = "Python profile"
        self.projects = "FastAPI project"
        self.calls = 0

    def load_profile(self) -> str:
        self.calls += 1
        return self.profile

    def load_projects(self) -> str:
        self.calls += 1
        return self.projects


class FakeGateway:
    model_name = "test-model"

    def __init__(self, result: InterviewPreparationResponse) -> None:
        self.result = result
        self.inputs = []
        self.error = None

    @property
    def calls(self) -> int:
        return len(self.inputs)

    def prepare_interview_for_job(self, **kwargs):
        self.inputs.append(kwargs)
        if self.error:
            raise self.error
        return self.result


def make_response() -> InterviewPreparationResponse:
    return InterviewPreparationResponse(
        target_position="Python Intern",
        focus_areas=[
            {
                "topic": "Python backend",
                "importance": "high",
                "reason": "JD requirement",
            }
        ],
        likely_questions=[],
        project_questions=[],
        risk_questions=[],
        knowledge_gaps=[],
        questions_for_interviewer=["How is mentoring organized?"],
    )


def make_service():
    job = SimpleNamespace(
        id=3,
        position="Python Intern",
        job_description="Build Python APIs",
        match_score=82,
        strengths=["Python project"],
        weaknesses=["No Docker evidence"],
        suggestions=["Review containers"],
    )
    repository = FakePreparationRepository()
    loader = FakeLoader()
    gateway = FakeGateway(make_response())
    service = InterviewPreparationService(
        job_repository=FakeJobRepository(job),  # type: ignore[arg-type]
        preparation_repository=repository,  # type: ignore[arg-type]
        gateway=gateway,  # type: ignore[arg-type]
        profile_loader=loader,  # type: ignore[arg-type]
    )
    return service, job, repository, loader, gateway


def test_interview_first_generation_saves_result_and_match_analysis() -> None:
    service, job, repository, loader, gateway = make_service()

    result = service.prepare(job.id)

    assert result == gateway.result
    assert gateway.calls == 1
    assert len(repository.upsert_calls) == 1
    assert repository.upsert_calls[0]["result"] == result.model_dump(
        mode="json"
    )
    assert gateway.inputs[0]["match_analysis"] == {
        "match_score": 82,
        "strengths": ["Python project"],
        "weaknesses": ["No Docker evidence"],
        "suggestions": ["Review containers"],
    }


def test_interview_same_hash_returns_cache_without_llm() -> None:
    service, job, repository, loader, gateway = make_service()
    first = service.prepare(job.id)

    second = service.prepare(job.id)

    assert second == first
    assert gateway.calls == 1
    assert len(repository.upsert_calls) == 1


@pytest.mark.parametrize("source", ["profile", "projects", "job"])
def test_interview_source_change_invalidates_cache(source: str) -> None:
    service, job, repository, loader, gateway = make_service()
    service.prepare(job.id)
    old_hash = repository.cached.source_hash

    if source == "profile":
        loader.profile = "Changed profile"
    elif source == "projects":
        loader.projects = "Changed projects"
    else:
        job.job_description = "Changed JD"

    service.prepare(job.id)

    assert gateway.calls == 2
    assert repository.cached.source_hash != old_hash


def test_interview_force_regenerate_ignores_cache() -> None:
    service, job, repository, loader, gateway = make_service()
    service.prepare(job.id)

    service.prepare(job.id, force_regenerate=True)

    assert gateway.calls == 2
    assert len(repository.upsert_calls) == 2


def test_interview_failed_regeneration_preserves_cache() -> None:
    service, job, repository, loader, gateway = make_service()
    original = service.prepare(job.id)
    old_cache = repository.cached
    gateway.error = LLMGatewayError("failed")

    with pytest.raises(LLMGatewayError):
        service.prepare(job.id, force_regenerate=True)

    assert repository.cached is old_cache
    assert len(repository.upsert_calls) == 1
    assert InterviewPreparationResponse.model_validate(
        old_cache.result
    ) == original


def test_interview_missing_job_raises_404_domain_error() -> None:
    repository = FakePreparationRepository()
    loader = FakeLoader()
    gateway = FakeGateway(make_response())
    service = InterviewPreparationService(
        job_repository=FakeJobRepository(),  # type: ignore[arg-type]
        preparation_repository=repository,  # type: ignore[arg-type]
        gateway=gateway,  # type: ignore[arg-type]
        profile_loader=loader,  # type: ignore[arg-type]
    )

    with pytest.raises(JobNotFoundError):
        service.prepare(999)

    assert loader.calls == 0
    assert gateway.calls == 0
