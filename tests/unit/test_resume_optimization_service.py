from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.ai.gateway import LLMGatewayError
from backend.schemas.resume import ResumeOptimizationResponse
from backend.services.job_service import JobNotFoundError
from backend.services.resume_optimization_service import (
    ResumeOptimizationService,
)


class FakeJobRepository:
    def __init__(self, job=None) -> None:
        self.job = job
        self.requested_job_id = None

    def get_by_id(self, job_id: int):
        self.requested_job_id = job_id
        return self.job


class FakeOptimizationRepository:
    def __init__(self, cached=None) -> None:
        self.cached = cached
        self.upsert_calls = []

    def get_by_job_id(self, job_id: int):
        if self.cached is not None and self.cached.job_id == job_id:
            return self.cached
        return None

    def upsert(self, **kwargs):
        self.upsert_calls.append(kwargs)
        now = datetime.now(timezone.utc)
        created_at = (
            self.cached.created_at if self.cached is not None else now
        )
        self.cached = SimpleNamespace(
            id=1,
            created_at=created_at,
            updated_at=now,
            **kwargs,
        )
        return self.cached


class FakeProfileLoader:
    def __init__(
        self,
        profile: str = "Candidate profile facts",
        projects: str = "Candidate project facts",
    ) -> None:
        self.profile = profile
        self.projects = projects
        self.profile_calls = 0
        self.project_calls = 0

    def load_profile(self) -> str:
        self.profile_calls += 1
        return self.profile

    def load_projects(self) -> str:
        self.project_calls += 1
        return self.projects


class FakeGateway:
    model_name = "test-model"

    def __init__(self, result: ResumeOptimizationResponse) -> None:
        self.result = result
        self.received_inputs = []
        self.error = None

    @property
    def calls(self) -> int:
        return len(self.received_inputs)

    def optimize_resume_for_job(self, **kwargs) -> ResumeOptimizationResponse:
        self.received_inputs.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


def make_response(target: str = "Python Intern") -> ResumeOptimizationResponse:
    return ResumeOptimizationResponse(
        target_position=target,
        priority_experiences=["FastAPI project"],
        keywords_to_emphasize=["Python"],
        content_to_deemphasize=[],
        project_rewrites=[],
        skill_section_suggestions=[],
        missing_requirements=["Docker"],
        warnings=["Do not invent deployment experience"],
    )


def make_service():
    job = SimpleNamespace(
        id=7,
        position="Python Intern",
        job_description="Build Python APIs with FastAPI",
    )
    job_repository = FakeJobRepository(job)
    optimization_repository = FakeOptimizationRepository()
    loader = FakeProfileLoader()
    gateway = FakeGateway(make_response())
    service = ResumeOptimizationService(
        job_repository=job_repository,  # type: ignore[arg-type]
        optimization_repository=optimization_repository,  # type: ignore[arg-type]
        gateway=gateway,  # type: ignore[arg-type]
        profile_loader=loader,  # type: ignore[arg-type]
    )
    return service, job, optimization_repository, loader, gateway


def test_first_request_generates_and_saves_result() -> None:
    service, job, cache_repository, loader, gateway = make_service()

    result = service.optimize(job.id)

    assert result == gateway.result
    assert gateway.calls == 1
    assert len(cache_repository.upsert_calls) == 1
    saved = cache_repository.upsert_calls[0]
    assert saved["job_id"] == job.id
    assert len(saved["source_hash"]) == 64
    assert saved["result"] == result.model_dump(mode="json")
    assert saved["model"] == "test-model"
    assert gateway.received_inputs[0] == {
        "target_position": "Python Intern",
        "job_description": "Build Python APIs with FastAPI",
        "candidate_profile": "Candidate profile facts",
        "candidate_projects": "Candidate project facts",
    }


def test_second_request_with_same_sources_returns_cache() -> None:
    service, job, cache_repository, loader, gateway = make_service()
    first = service.optimize(job.id)

    second = service.optimize(job.id)

    assert second == first
    assert gateway.calls == 1
    assert len(cache_repository.upsert_calls) == 1


@pytest.mark.parametrize("changed_source", ["profile", "projects", "job"])
def test_source_change_regenerates_cache(changed_source: str) -> None:
    service, job, cache_repository, loader, gateway = make_service()
    service.optimize(job.id)
    old_hash = cache_repository.cached.source_hash

    if changed_source == "profile":
        loader.profile = "Updated candidate profile"
    elif changed_source == "projects":
        loader.projects = "Updated candidate projects"
    else:
        job.job_description = "Updated job description"

    service.optimize(job.id)

    assert gateway.calls == 2
    assert len(cache_repository.upsert_calls) == 2
    assert cache_repository.cached.source_hash != old_hash


def test_force_regenerate_ignores_matching_cache() -> None:
    service, job, cache_repository, loader, gateway = make_service()
    service.optimize(job.id)

    service.optimize(job.id, force_regenerate=True)

    assert gateway.calls == 2
    assert len(cache_repository.upsert_calls) == 2


def test_failed_force_regenerate_preserves_old_cache() -> None:
    service, job, cache_repository, loader, gateway = make_service()
    original = service.optimize(job.id)
    old_cache = cache_repository.cached
    old_result = dict(old_cache.result)
    gateway.error = LLMGatewayError("provider failed")

    with pytest.raises(LLMGatewayError):
        service.optimize(job.id, force_regenerate=True)

    assert cache_repository.cached is old_cache
    assert cache_repository.cached.result == old_result
    assert len(cache_repository.upsert_calls) == 1
    assert ResumeOptimizationResponse.model_validate(old_result) == original


def test_cached_json_restores_resume_optimization_response() -> None:
    service, job, cache_repository, loader, gateway = make_service()
    expected = service.optimize(job.id)
    gateway.error = AssertionError("LLM must not be called")

    cached = service.get_cached(job.id)

    assert cached is not None
    assert cached.result == expected
    assert cached.model == "test-model"
    assert cached.updated_at == cache_repository.cached.updated_at
    assert gateway.calls == 1


def test_service_raises_404_before_loading_profile() -> None:
    job_repository = FakeJobRepository()
    cache_repository = FakeOptimizationRepository()
    loader = FakeProfileLoader()
    gateway = FakeGateway(make_response())
    service = ResumeOptimizationService(
        job_repository=job_repository,  # type: ignore[arg-type]
        optimization_repository=cache_repository,  # type: ignore[arg-type]
        gateway=gateway,  # type: ignore[arg-type]
        profile_loader=loader,  # type: ignore[arg-type]
    )

    with pytest.raises(JobNotFoundError):
        service.optimize(999)

    assert job_repository.requested_job_id == 999
    assert loader.profile_calls == 0
    assert loader.project_calls == 0
    assert gateway.calls == 0
