from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.interview_preparation import InterviewPreparation


class InterviewPreparationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_job_id(self, job_id: int) -> Optional[InterviewPreparation]:
        statement = select(InterviewPreparation).where(
            InterviewPreparation.job_id == job_id
        )
        return self._db.scalar(statement)

    def list_job_ids(self) -> set[int]:
        statement = select(InterviewPreparation.job_id)
        return set(self._db.scalars(statement).all())

    def upsert(
        self,
        job_id: int,
        source_hash: str,
        result: dict,
        model: str,
    ) -> InterviewPreparation:
        preparation = self.get_by_job_id(job_id)
        if preparation is None:
            preparation = InterviewPreparation(job_id=job_id)
            self._db.add(preparation)

        preparation.source_hash = source_hash
        preparation.result = result
        preparation.model = model

        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        self._db.refresh(preparation)
        return preparation
