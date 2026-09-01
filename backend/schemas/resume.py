from datetime import datetime

from pydantic import BaseModel, Field


class ResumeOptimizationRequest(BaseModel):
    job_id: int = Field(gt=0)
    force_regenerate: bool = False


class ProjectRewrite(BaseModel):
    project: str = Field(min_length=1)
    original: str
    suggested: str
    reason: str


class ResumeOptimizationResponse(BaseModel):
    target_position: str = Field(min_length=1)
    priority_experiences: list[str] = Field(default_factory=list)
    keywords_to_emphasize: list[str] = Field(default_factory=list)
    content_to_deemphasize: list[str] = Field(default_factory=list)
    project_rewrites: list[ProjectRewrite] = Field(default_factory=list)
    skill_section_suggestions: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResumeOptimizationCacheResponse(BaseModel):
    result: ResumeOptimizationResponse
    model: str
    created_at: datetime
    updated_at: datetime
