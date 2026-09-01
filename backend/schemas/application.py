from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from backend.core.constants import JobStatus


class ApplicationQueueItemResponse(BaseModel):
    queue_id: int
    job_id: int
    company: str
    position: str
    match_score: int
    status: JobStatus
    has_resume_optimization: bool
    has_interview_preparation: bool
    job_url: Optional[str]
    queued_at: datetime
