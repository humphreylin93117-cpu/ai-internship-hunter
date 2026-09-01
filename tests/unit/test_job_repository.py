from datetime import timedelta

from sqlalchemy.orm import Session

from backend.models.job import Job
from backend.repositories.job_repository import JobRepository


def make_job(
    company: str = "Example Tech",
    match_score: int = 80,
    status: str = "saved",
) -> Job:
    return Job(
        company=company,
        position="Python Intern",
        job_description="Build backend services with Python.",
        source="official",
        job_url=None,
        match_score=match_score,
        strengths=["Python project experience"],
        weaknesses=["Limited production experience"],
        suggestions=["Prepare a project walkthrough"],
        status=status,
    )


def test_create_assigns_id_and_timestamps(db_session: Session) -> None:
    repository = JobRepository(db_session)

    created = repository.create(make_job())

    assert created.id is not None
    assert created.created_at is not None
    assert created.updated_at is not None


def test_list_filters_and_orders_jobs(db_session: Session) -> None:
    repository = JobRepository(db_session)
    older = repository.create(make_job("Alpha", 70, "saved"))
    newer = repository.create(make_job("Beta Labs", 88, "applied"))
    older.created_at = newer.created_at - timedelta(days=1)
    db_session.commit()

    all_jobs = repository.list()
    applied = repository.list(status="applied")
    high_score = repository.list(min_match_score=75)
    company_match = repository.list(company="beta")

    assert [job.id for job in all_jobs] == [newer.id, older.id]
    assert [job.id for job in applied] == [newer.id]
    assert [job.id for job in high_score] == [newer.id]
    assert [job.id for job in company_match] == [newer.id]


def test_get_and_update_status(db_session: Session) -> None:
    repository = JobRepository(db_session)
    job = repository.create(make_job())

    updated = repository.update_status(job, "applied")

    assert repository.get_by_id(job.id) is job
    assert updated.status == "applied"
    assert updated.updated_at is not None
    assert repository.get_by_id(999_999) is None


def test_duplicate_lookup_finds_exact_url(
    db_session: Session,
) -> None:
    repository = JobRepository(db_session)
    url_job = make_job("URL Company")
    url_job.job_url = "https://example.com/jobs/1"
    repository.create(url_job)

    assert repository.find_by_job_url(url_job.job_url) == [url_job]
