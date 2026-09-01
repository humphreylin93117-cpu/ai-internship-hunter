from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class DiscoveredJob(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source_domain: str = ""
    provider: str


class JobDiscoveryRequest(BaseModel):
    keywords: list[str] = Field(min_length=1, max_length=10)
    cities: list[str] = Field(min_length=1, max_length=10)
    max_results: int = Field(default=10, ge=1, le=20)

    @field_validator("keywords", "cities")
    @classmethod
    def normalize_terms(cls, values: list[str]) -> list[str]:
        normalized = []
        seen = set()
        for value in values:
            term = value.strip()
            key = term.casefold()
            if term and key not in seen:
                normalized.append(term)
                seen.add(key)
        if not normalized:
            raise ValueError("at least one non-blank value is required")
        return normalized


class JobDiscoveryResponse(BaseModel):
    query: str
    results: list[DiscoveredJob] = Field(default_factory=list)


class JobExtractRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2_048)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        normalized = value.strip()
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be a valid HTTP(S) URL")
        return normalized


class JobExtractResponse(BaseModel):
    url: str
    content: str
    is_complete: bool = True
    warning: str = ""
