from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from backend.models.application import ApplicationQueueItem
from backend.models.interview_preparation import InterviewPreparation
from backend.models.job import Job
from backend.models.resume_optimization import ResumeOptimization


@dataclass(frozen=True)
class ApplicationQueueEntry:
    queue_id: int
    job_id: int
    company: str
    position: str
    match_score: int
    status: str
    has_resume_optimization: bool
    has_interview_preparation: bool
    job_url: Optional[str]
    queued_at: datetime


class ApplicationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def _entry_statement():
        return (
            select(
                ApplicationQueueItem.id.label("queue_id"),
                Job.id.label("job_id"),
                Job.company,
                Job.position,
                Job.match_score,
                Job.status,
                exists(
                    select(ResumeOptimization.id).where(
                        ResumeOptimization.job_id == Job.id
                    )
                ).label("has_resume_optimization"),
                exists(
                    select(InterviewPreparation.id).where(
                        InterviewPreparation.job_id == Job.id
                    )
                ).label("has_interview_preparation"),
                Job.job_url,
                ApplicationQueueItem.queued_at,
            )
            .join(Job, Job.id == ApplicationQueueItem.job_id)
        )

    def list(
        self,
        status: Optional[str] = None,
        company: Optional[str] = None,
        min_match_score: Optional[int] = None,
        sort_order: str = "desc",
    ) -> list[ApplicationQueueEntry]:
        statement = self._entry_statement()
        if status is not None:
            statement = statement.where(Job.status == status)
        if company is not None:
            statement = statement.where(Job.company.ilike(f"%{company}%"))
        if min_match_score is not None:
            statement = statement.where(Job.match_score >= min_match_score)

        score_order = (
            Job.match_score.asc()
            if sort_order == "asc"
            else Job.match_score.desc()
        )
        statement = statement.order_by(
            score_order,
            ApplicationQueueItem.queued_at.desc(),
            ApplicationQueueItem.id.desc(),
        )
        return [
            ApplicationQueueEntry(**row._mapping)
            for row in self._db.execute(statement).all()
        ]

    def get_by_job_id(
        self,
        job_id: int,
    ) -> Optional[ApplicationQueueItem]:
        statement = select(ApplicationQueueItem).where(
            ApplicationQueueItem.job_id == job_id
        )
        return self._db.scalar(statement)

    def get_entry_by_job_id(
        self,
        job_id: int,
    ) -> Optional[ApplicationQueueEntry]:
        row = self._db.execute(
            self._entry_statement().where(Job.id == job_id)
        ).first()
        return ApplicationQueueEntry(**row._mapping) if row else None

    def add(self, job_id: int) -> ApplicationQueueItem:
        item = ApplicationQueueItem(job_id=job_id)
        self._db.add(item)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        self._db.refresh(item)
        return item

    def remove(self, item: ApplicationQueueItem) -> None:
        self._db.delete(item)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
