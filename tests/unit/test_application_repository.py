from sqlalchemy.orm import Session

from backend.models.job import Job
from backend.repositories.application_repository import ApplicationRepository
from backend.repositories.interview_preparation_repository import (
    InterviewPreparationRepository,
)
from backend.repositories.job_repository import JobRepository
from backend.repositories.resume_optimization_repository import (
    ResumeOptimizationRepository,
)


def create_job(
    db_session: Session,
    company: str,
    score: int,
    status: str = "saved",
) -> Job:
    return JobRepository(db_session).create(
        Job(
            company=company,
            position="Python Intern",
            job_description="Build APIs",
            source="official",
            job_url=f"https://example.com/{company}",
            match_score=score,
            strengths=[],
            weaknesses=[],
            suggestions=[],
            status=status,
        )
    )


def test_repository_lists_queue_with_readiness_and_score_sorting(
    db_session: Session,
) -> None:
    low = create_job(db_session, "Low Tech", 70)
    high = create_job(db_session, "High Tech", 92, status="planned")
    repository = ApplicationRepository(db_session)
    repository.add(low.id)
    repository.add(high.id)
    ResumeOptimizationRepository(db_session).upsert(
        high.id,
        "a" * 64,
        {"target_position": high.position},
        "test-model",
    )
    InterviewPreparationRepository(db_session).upsert(
        low.id,
        "b" * 64,
        {"target_position": low.position},
        "test-model",
    )

    entries = repository.list(sort_order="desc")

    assert [entry.job_id for entry in entries] == [high.id, low.id]
    assert entries[0].has_resume_optimization is True
    assert entries[0].has_interview_preparation is False
    assert entries[1].has_resume_optimization is False
    assert entries[1].has_interview_preparation is True


def test_repository_filters_queue_and_removes_item(
    db_session: Session,
) -> None:
    matching = create_job(db_session, "Example Labs", 88, status="planned")
    other = create_job(db_session, "Other Corp", 95, status="saved")
    repository = ApplicationRepository(db_session)
    repository.add(matching.id)
    repository.add(other.id)

    entries = repository.list(
        status="planned",
        company="example",
        min_match_score=80,
        sort_order="asc",
    )

    assert [entry.job_id for entry in entries] == [matching.id]
    item = repository.get_by_job_id(matching.id)
    assert item is not None
    repository.remove(item)
    db_session.expire_all()
    reloaded_repository = ApplicationRepository(db_session)
    assert reloaded_repository.get_by_job_id(matching.id) is None
