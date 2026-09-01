from datetime import timedelta

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
from backend.services.dashboard_service import DashboardService


def create_job(
    db_session: Session,
    company: str,
    score: int,
    status: str,
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


def make_service(db_session: Session) -> DashboardService:
    return DashboardService(
        JobRepository(db_session),
        ApplicationRepository(db_session),
        ResumeOptimizationRepository(db_session),
        InterviewPreparationRepository(db_session),
    )


def test_dashboard_summary_counts_priorities_and_todos(
    db_session: Session,
) -> None:
    saved = create_job(db_session, "Saved", 90, "saved")
    planned = create_job(db_session, "Planned", 80, "planned")
    applied = create_job(db_session, "Applied", 70, "applied")
    written = create_job(db_session, "Written", 60, "written_test")
    create_job(db_session, "Interview 1", 50, "interview_1")
    create_job(db_session, "Interview 2", 40, "interview_2")
    create_job(db_session, "Offer", 30, "offer")
    create_job(db_session, "Rejected", 20, "rejected")
    create_job(db_session, "Abandoned", 10, "abandoned")

    applications = ApplicationRepository(db_session)
    applications.add(saved.id)
    applications.add(planned.id)
    applications.add(applied.id)
    ResumeOptimizationRepository(db_session).upsert(
        planned.id,
        "a" * 64,
        {"target_position": planned.position},
        "test-model",
    )
    InterviewPreparationRepository(db_session).upsert(
        written.id,
        "b" * 64,
        {"target_position": written.position},
        "test-model",
    )

    summary = make_service(db_session).get_summary()
    todos = {item.key: item.count for item in summary.todos}

    assert summary.saved_planned_count == 2
    assert summary.pending_queue_count == 2
    assert summary.applied_count == 1
    assert summary.assessment_interview_count == 3
    assert summary.offer_count == 1
    assert summary.rejected_count == 1
    assert summary.abandoned_count == 1
    assert summary.average_match_score == 50.0
    assert [job.id for job in summary.priority_jobs] == [
        saved.id,
        planned.id,
    ]
    assert todos == {
        "pending_without_resume": 1,
        "pending_without_interview": 2,
        "applied_without_interview": 1,
        "active_follow_up": 3,
    }


def test_dashboard_recent_jobs_use_updated_at(db_session: Session) -> None:
    older = create_job(db_session, "Older", 70, "saved")
    recently_updated = create_job(
        db_session,
        "Recently Updated",
        80,
        "applied",
    )
    older.updated_at = older.created_at - timedelta(days=2)
    recently_updated.updated_at = recently_updated.created_at + timedelta(
        days=2
    )
    db_session.commit()

    summary = make_service(db_session).get_summary()

    assert [job.id for job in summary.recent_jobs[:2]] == [
        recently_updated.id,
        older.id,
    ]


def test_empty_dashboard_has_zero_metrics(db_session: Session) -> None:
    summary = make_service(db_session).get_summary()

    assert summary.saved_planned_count == 0
    assert summary.pending_queue_count == 0
    assert summary.average_match_score == 0.0
    assert summary.priority_jobs == []
    assert summary.recent_jobs == []
