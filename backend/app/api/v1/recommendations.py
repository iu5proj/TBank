"""Recommendations API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.recommendation import Recommendation
from app.schemas.recommendation import RecommendationResponse

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get(
    "/estimate/{estimate_id}",
    response_model=list[RecommendationResponse],
    summary="Get recommendations for an estimate",
)
async def get_recommendations_by_estimate(
    estimate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[Recommendation]:
    """Retrieve all recommendations linked to a specific salary estimate."""
    result = await db.execute(
        select(Recommendation).where(Recommendation.estimate_id == estimate_id).order_by(Recommendation.priority)
    )
    return list(result.scalars().all())
