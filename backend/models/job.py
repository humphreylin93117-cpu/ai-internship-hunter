from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.constants import JOB_STATUS_VALUES, JobStatus
from backend.database.session import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "match_score BETWEEN 0 AND 100",
            name="ck_jobs_match_score_range",
        ),
        CheckConstraint(
            f"status IN {JOB_STATUS_VALUES}",
            name="ck_jobs_status_allowed",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company: Mapped[str] = mapped_column(String(255), index=True)
    position: Mapped[str] = mapped_column(String(255))
    job_description: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(100))
    job_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    match_score: Mapped[int] = mapped_column(Integer, index=True)
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, default=list)
    suggestions: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(
        String(32),
        default=JobStatus.SAVED.value,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
