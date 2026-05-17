"""Pydantic schemas for resume API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExperienceEntry(BaseModel):
    """Single work experience block."""

    company: str = Field(..., min_length=1, max_length=255, examples=["Yandex"])
    title: str = Field(..., min_length=1, max_length=255, examples=["Backend Developer"])
    duration_months: int = Field(..., ge=1, le=600, examples=[24])
    description: str = Field(
        default="",
        max_length=5000,
        examples=["Built high-load Python services"],
    )


class ResumeCreate(BaseModel):
    """Request body to create or update a resume."""

    job_title: str = Field(..., min_length=1, max_length=255, examples=["Senior Python Developer"])
    experience_years: float = Field(..., ge=0, le=50, examples=[5.0])
    skills: list[str] = Field(..., min_length=1, examples=[["Python", "FastAPI", "PostgreSQL"]])
    location: str = Field(..., min_length=1, max_length=255, examples=["Moscow"])
    education_level: Literal["none", "bachelor", "master", "phd"] = Field(
        default="none",
        examples=["bachelor"],
    )
    experience_entries: list[ExperienceEntry] = Field(default_factory=list)


class ResumeUpdate(BaseModel):
    """Partial update with only changed fields."""

    job_title: str | None = Field(default=None, min_length=1, max_length=255)
    experience_years: float | None = Field(default=None, ge=0, le=50)
    skills: list[str] | None = Field(default=None, min_length=1)
    location: str | None = Field(default=None, min_length=1, max_length=255)
    education_level: Literal["none", "bachelor", "master", "phd"] | None = None
    experience_entries: list[ExperienceEntry] | None = None


class ResumeResponse(BaseModel):
    """Resume as returned from the API."""

    id: uuid.UUID
    user_id: uuid.UUID
    job_title: str
    experience_years: float
    skills: list[str]
    location: str
    education_level: str
    experience_entries: list[ExperienceEntry]
    updated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}

