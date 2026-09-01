from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from backend.core.constants import JobStatus


class DashboardStageSummary(BaseModel):
    saved_planned: int = 0
    applied: int = 0
    assessment_interview: int = 0
    offer: int = 0
    rejected: int = 0
    abandoned: int = 0


class DashboardJobItem(BaseModel):
    id: int
    company: str
    position: str
    match_score: int
    status: JobStatus
    job_url: Optional[str] = None


class DashboardRecentJob(DashboardJobItem):
    created_at: datetime
    updated_at: datetime


class DashboardTodoItem(BaseModel):
    key: str
    label: str
    count: int = Field(ge=0)


class DashboardSummaryResponse(BaseModel):
    saved_planned_count: int = 0
    pending_queue_count: int = 0
    applied_count: int = 0
    assessment_interview_count: int = 0
    offer_count: int = 0
    rejected_count: int = 0
    abandoned_count: int = 0
    average_match_score: float = 0.0
    stages: DashboardStageSummary
    priority_jobs: list[DashboardJobItem] = Field(default_factory=list)
    todos: list[DashboardTodoItem] = Field(default_factory=list)
    recent_jobs: list[DashboardRecentJob] = Field(default_factory=list)
