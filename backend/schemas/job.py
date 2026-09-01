from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.core.constants import JobStatus


class JobAnalysisRequest(BaseModel):
    job_description: str = Field(
        min_length=1,
        max_length=30_000,
        description="需要分析的完整岗位 JD 文本",
    )

    @field_validator("job_description")
    @classmethod
    def normalize_job_description(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("job_description cannot be blank")
        return normalized


class JobAnalysisResponse(BaseModel):
    match_score: int = Field(
        ge=0,
        le=100,
        description="候选人与岗位的综合匹配度评分",
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="候选人资料中与岗位要求匹配的已有经历或能力",
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="岗位要求与候选人资料之间的差距",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="候选人针对该岗位的准备建议",
    )


class JobParseRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=30_000)
    job_url: Optional[str] = Field(default=None, max_length=2_048)

    @field_validator("raw_text")
    @classmethod
    def normalize_raw_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("raw_text cannot be blank")
        return normalized

    @field_validator("job_url")
    @classmethod
    def normalize_parse_job_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None


class JobParseResponse(BaseModel):
    company: str = ""
    position: str = ""
    job_description: str
    source: str = ""
    job_url: Optional[str] = None
    parse_status: str = "success"
    parse_message: str = ""


class JobIdentityExtraction(BaseModel):
    company: str = Field(default="", max_length=255)
    position: str = Field(default="", max_length=255)

    @field_validator("company", "position")
    @classmethod
    def normalize_identity_text(cls, value: str) -> str:
        return value.strip()


class JobDuplicateCheckRequest(BaseModel):
    company: str = ""
    position: str = ""
    job_description: str = Field(min_length=1, max_length=30_000)
    job_url: Optional[str] = Field(default=None, max_length=2_048)

    @field_validator("company", "position")
    @classmethod
    def normalize_duplicate_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("job_description")
    @classmethod
    def normalize_duplicate_job_description(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("job_description cannot be blank")
        return normalized

    @field_validator("job_url")
    @classmethod
    def normalize_duplicate_job_url(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None


class JobDuplicateSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company: str
    position: str
    status: JobStatus
    created_at: datetime


class JobDuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    jobs: list[JobDuplicateSummary] = Field(default_factory=list)


class JobCreate(BaseModel):
    company: str = Field(min_length=1, max_length=255)
    position: str = Field(min_length=1, max_length=255)
    job_description: str = Field(min_length=1, max_length=30_000)
    source: str = Field(min_length=1, max_length=100)
    job_url: Optional[str] = Field(default=None, max_length=2_048)
    match_score: int = Field(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    status: JobStatus = JobStatus.SAVED

    @field_validator("company", "position", "job_description", "source")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be blank")
        return normalized

    @field_validator("job_url")
    @classmethod
    def normalize_job_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None


class JobStatusUpdate(BaseModel):
    status: JobStatus


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company: str
    position: str
    job_description: str
    source: str
    job_url: Optional[str]
    match_score: int
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[str]
    status: JobStatus
    created_at: datetime
    updated_at: datetime
