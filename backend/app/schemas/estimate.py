"""Pydantic schemas for salary estimation API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.recommendation import RecommendationResponse


class SalaryRange(BaseModel):
    """Quantile salary prediction."""

    p25: int = Field(..., description="25th percentile — lower market bound", examples=[80000])
    p50: int = Field(..., description="50th percentile — market median", examples=[120000])
    p75: int = Field(..., description="75th percentile — upper market bound", examples=[170000])


class MarketInsights(BaseModel):
    """Aggregated market context for the given profile."""

    vacancies_analyzed: int = Field(..., examples=[342])
    skill_match_percentage: float = Field(..., ge=0, le=100, examples=[72.5])
    top_missing_skills: list[str] = Field(default_factory=list, examples=[["Docker", "Kubernetes"]])
    demand_trend: str = Field(default="stable", examples=["growing"])


class ShapContribution(BaseModel):
    """SHAP value for a single feature — how it shifts salary from baseline."""

    feature: str = Field(..., examples=["skills:Python"])
    contribution_rub: int = Field(..., examples=[15000])


class EstimateRequest(BaseModel):
    """Explicit request body when estimating without a saved resume."""

    job_title: str = Field(..., min_length=1, max_length=255)
    experience_years: float = Field(..., ge=0, le=50)
    skills: list[str] = Field(..., min_length=1)
    location: str = Field(..., min_length=1, max_length=255)
    education_level: str = Field(default="none")
    experience_entries: list[dict] = Field(default_factory=list)


class EstimateResponse(BaseModel):
    """Full response for salary estimation — salary range + insights + recommendations."""

    id: uuid.UUID
    resume_id: uuid.UUID
    salary_range: SalaryRange
    market_insights: MarketInsights
    shap_contributions: list[ShapContribution] = Field(default_factory=list)
    recommendations: list[RecommendationResponse] = Field(default_factory=list)
    calculated_at: datetime

    model_config = {"from_attributes": True}


class EstimateHistoryItem(BaseModel):
    """Single history entry for resume evolution timeline."""

    estimate_id: uuid.UUID
    p25: int
    p50: int
    p75: int
    skills_snapshot: list[str]
    changed_fields: list[str] = Field(default_factory=list)
    calculated_at: datetime
