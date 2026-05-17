"""Schemas for the GPT-OSS salary analysis contract."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ResumeProfile(BaseModel):
    """User resume profile accepted by POST /api/v1/analyze."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=2, max_length=160)
    experience_years: float = Field(..., ge=0, le=60)
    location: str = Field(..., min_length=2, max_length=120)
    skills: list[str] = Field(default_factory=list)
    resume_text: str | None = Field(default=None, max_length=12_000)
    current_salary: int | None = Field(default=None, ge=0)

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        skills: list[str] = []
        for item in value:
            skill = str(item).strip()
            if not skill:
                continue
            dedupe_key = skill.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            skills.append(skill[:100])
        return skills[:80]


class AnalyzeOptions(BaseModel):
    """Optional controls for the analyze pipeline."""

    target_salary: int | None = Field(default=None, ge=0)
    force_refresh: bool = False


class AnalyzeRequest(BaseModel):
    """Main request body for POST /api/v1/analyze."""

    profile: ResumeProfile
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions)


class SegmentOut(BaseModel):
    segment_key: str
    segment_data_version: str


class SalaryQuantiles(BaseModel):
    p25: int = Field(..., gt=0)
    p50: int = Field(..., gt=0)
    p75: int = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_order(self) -> "SalaryQuantiles":
        if not self.p25 <= self.p50 <= self.p75:
            raise ValueError("salary_quantiles must satisfy p25 <= p50 <= p75")
        return self


class ExcludedVacancy(BaseModel):
    id: str
    reason: str = Field(..., min_length=1)


class MarketSample(BaseModel):
    candidate_vacancies_received: int = Field(..., ge=1)
    vacancies_used_for_estimation: int = Field(..., ge=1)
    used_vacancy_ids: list[str] = Field(..., min_length=1)
    excluded_vacancies: list[ExcludedVacancy] = Field(default_factory=list)
    salary_quantiles: SalaryQuantiles


class SalaryRange(BaseModel):
    min: int = Field(..., gt=0)
    median: int = Field(..., gt=0)
    max: int = Field(..., gt=0)
    currency: Literal["RUB"]

    @model_validator(mode="after")
    def validate_order(self) -> "SalaryRange":
        if not self.min <= self.median <= self.max:
            raise ValueError("salary_range must satisfy min <= median <= max")
        return self


class Confidence(BaseModel):
    score: float = Field(..., ge=0, le=1)
    level: Literal["low", "medium", "high"]
    reason: str = Field(..., min_length=1)


class MissingSkill(BaseModel):
    skill: str = Field(..., min_length=1)
    impact: Literal["low", "medium", "high"]
    reason: str = Field(..., min_length=1)


class Factor(BaseModel):
    factor: str = Field(..., min_length=1)
    impact: Literal["positive", "negative", "neutral"]
    explanation: str = Field(..., min_length=1)


class Recommendation(BaseModel):
    priority: int = Field(..., ge=1)
    type: Literal["skill_gap", "experience_detail", "resume_clarity", "salary_expectation"]
    title: str = Field(..., min_length=1)
    resume_change: str = Field(..., min_length=1)
    expected_salary_effect: str | None = None


class GptOssSalaryResult(BaseModel):
    """Strict model output schema from the technical specification."""

    request_hash: str
    segment: SegmentOut
    market_sample: MarketSample
    salary_range: SalaryRange
    confidence: Confidence
    matched_skills: list[str]
    missing_skills: list[MissingSkill]
    factor_analysis: list[Factor]
    recommendations: list[Recommendation] = Field(..., min_length=1)


class SegmentPayload(BaseModel):
    segment_key: str
    segment_data_version: str
    last_successful_update_at: datetime | None = None


class CandidateVacancy(BaseModel):
    id: str
    segment_key: str | None = None
    title: str
    description: str | None = None
    salary_min_net: int
    salary_max_net: int
    location: str | None = None
    experience_range: str | None = None
    skills_required: list[str] = Field(default_factory=list)
    source: str
    source_url: str | None = None
    published_at: date | datetime | str | None = None


class GptOssInputPayload(BaseModel):
    request_hash: str
    profile: dict[str, Any]
    segment: SegmentPayload
    candidate_vacancies: list[CandidateVacancy] = Field(..., min_length=1)
    market_evidence: dict[str, Any] = Field(default_factory=dict)
    rules: dict[str, bool]


class AnalyzeResponse(BaseModel):
    """Unified success/error response for the frontend."""

    status: Literal["success", "error"]
    source: Literal["gpt-oss-20b", "cache"] | None = None
    data: GptOssSalaryResult | None = None
    code: str | None = None
    message: str | None = None
    validation_errors: list[str] | None = None
