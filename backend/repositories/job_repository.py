from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.job import Job


class JobRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, job: Job) -> Job:
        self._db.add(job)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        self._db.refresh(job)
        return job

    def list(
        self,
        status: Optional[str] = None,
        company: Optional[str] = None,
        min_match_score: Optional[int] = None,
    ) -> list[Job]:
        statement = select(Job)

        if status is not None:
            statement = statement.where(Job.status == status)
        if company is not None:
            statement = statement.where(Job.company.ilike(f"%{company}%"))
        if min_match_score is not None:
            statement = statement.where(
                Job.match_score >= min_match_score
            )

        statement = statement.order_by(
            Job.created_at.desc(),
            Job.id.desc(),
        )
        return list(self._db.scalars(statement).all())

    def get_by_id(self, job_id: int) -> Optional[Job]:
        return self._db.get(Job, job_id)

    def find_by_job_url(self, job_url: str) -> list[Job]:
        statement = (
            select(Job)
            .where(Job.job_url == job_url)
            .order_by(Job.created_at.desc(), Job.id.desc())
        )
        return list(self._db.scalars(statement).all())

    def update_status(self, job: Job, status: str) -> Job:
        job.status = status
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        self._db.refresh(job)
        return job
