from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class InterviewPreparationRequest(BaseModel):
    job_id: int = Field(gt=0)
    force_regenerate: bool = False


class FocusArea(BaseModel):
    topic: str = Field(min_length=1)
    importance: Literal["high", "medium", "low"]
    reason: str = Field(min_length=1)


class LikelyQuestion(BaseModel):
    question: str = Field(min_length=1)
    category: str = Field(min_length=1)
    why_asked: str = Field(min_length=1)
    answer_points: list[str] = Field(default_factory=list, max_length=5)


class ProjectQuestion(BaseModel):
    project: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer_points: list[str] = Field(default_factory=list, max_length=5)


class RiskQuestion(BaseModel):
    question: str = Field(min_length=1)
    answer_strategy: list[str] = Field(default_factory=list, max_length=5)


class KnowledgeGap(BaseModel):
    topic: str = Field(min_length=1)
    priority: Literal["high", "medium", "low"]
    preparation: str = Field(min_length=1)


class InterviewPreparationResponse(BaseModel):
    target_position: str = Field(min_length=1)
    focus_areas: list[FocusArea] = Field(default_factory=list, max_length=5)
    likely_questions: list[LikelyQuestion] = Field(
        default_factory=list,
        max_length=8,
    )
    project_questions: list[ProjectQuestion] = Field(
        default_factory=list,
        max_length=5,
    )
    risk_questions: list[RiskQuestion] = Field(
        default_factory=list,
        max_length=4,
    )
    knowledge_gaps: list[KnowledgeGap] = Field(
        default_factory=list,
        max_length=5,
    )
    questions_for_interviewer: list[str] = Field(
        default_factory=list,
        max_length=5,
    )


class InterviewPreparationCacheResponse(BaseModel):
    result: InterviewPreparationResponse
    model: str
    created_at: datetime
    updated_at: datetime
