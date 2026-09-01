from sqlalchemy.orm import Session

from backend.models.job import Job
from backend.repositories.job_repository import JobRepository
from backend.repositories.resume_optimization_repository import (
    ResumeOptimizationRepository,
)


def create_job(db_session: Session) -> Job:
    return JobRepository(db_session).create(
        Job(
            company="Example Tech",
            position="Python Intern",
            job_description="Build APIs",
            source="official",
            job_url=None,
            match_score=85,
            strengths=[],
            weaknesses=[],
            suggestions=[],
            status="saved",
        )
    )


def test_repository_upserts_one_cache_per_job(db_session: Session) -> None:
    job = create_job(db_session)
    repository = ResumeOptimizationRepository(db_session)
    first_result = {"target_position": "Python Intern"}

    created = repository.upsert(
        job_id=job.id,
        source_hash="a" * 64,
        result=first_result,
        model="model-a",
    )
    updated = repository.upsert(
        job_id=job.id,
        source_hash="b" * 64,
        result={"target_position": "Backend Intern"},
        model="model-b",
    )

    assert created.id == updated.id
    assert repository.get_by_job_id(job.id).source_hash == "b" * 64
    assert repository.get_by_job_id(job.id).result == {
        "target_position": "Backend Intern"
    }
    assert repository.get_by_job_id(job.id).model == "model-b"
