"""Pydantic schemas for recommendation API contracts."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class RecommendationResponse(BaseModel):
    """Single recommendation returned by legacy recommendation endpoints."""

    id: uuid.UUID
    priority: int = Field(..., ge=1, le=5, examples=[1])
    category: Literal["hard_skill", "soft_skill", "formatting", "certification"] = Field(
        ...,
        examples=["hard_skill"],
    )
    title: str = Field(..., examples=["Add Docker skill"])
    description: str = Field(
        ...,
        examples=[
            "Docker is often requested for backend roles. Add it only if you have real experience."
        ],
    )
    impact: str = Field(..., examples=["+25 000 RUB to median"])
    action: str = Field(
        ...,
        examples=["Add Docker to skills and describe containerization experience in a project."],
    )

    model_config = {"from_attributes": True}

