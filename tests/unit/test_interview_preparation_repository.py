from sqlalchemy.orm import Session

from backend.models.job import Job
from backend.repositories.interview_preparation_repository import (
    InterviewPreparationRepository,
)
from backend.repositories.job_repository import JobRepository


def test_interview_repository_upserts_one_result_per_job(
    db_session: Session,
) -> None:
    job = JobRepository(db_session).create(
        Job(
            company="Example",
            position="Python Intern",
            job_description="Build APIs",
            source="official",
            job_url=None,
            match_score=80,
            strengths=[],
            weaknesses=[],
            suggestions=[],
            status="saved",
        )
    )
    repository = InterviewPreparationRepository(db_session)

    first = repository.upsert(
        job_id=job.id,
        source_hash="a" * 64,
        result={"target_position": "Python Intern"},
        model="model-a",
    )
    second = repository.upsert(
        job_id=job.id,
        source_hash="b" * 64,
        result={"target_position": "Backend Intern"},
        model="model-b",
    )

    assert first.id == second.id
    cached = repository.get_by_job_id(job.id)
    assert cached.source_hash == "b" * 64
    assert cached.result == {"target_position": "Backend Intern"}
    assert cached.model == "model-b"
