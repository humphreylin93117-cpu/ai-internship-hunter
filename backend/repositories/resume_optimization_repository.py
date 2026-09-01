from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.resume_optimization import ResumeOptimization


class ResumeOptimizationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_job_id(self, job_id: int) -> Optional[ResumeOptimization]:
        statement = select(ResumeOptimization).where(
            ResumeOptimization.job_id == job_id
        )
        return self._db.scalar(statement)

    def list_job_ids(self) -> set[int]:
        statement = select(ResumeOptimization.job_id)
        return set(self._db.scalars(statement).all())

    def upsert(
        self,
        job_id: int,
        source_hash: str,
        result: dict,
        model: str,
    ) -> ResumeOptimization:
        optimization = self.get_by_job_id(job_id)
        if optimization is None:
            optimization = ResumeOptimization(job_id=job_id)
            self._db.add(optimization)

        optimization.source_hash = source_hash
        optimization.result = result
        optimization.model = model

        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        self._db.refresh(optimization)
        return optimization
