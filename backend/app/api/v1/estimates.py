"""Salary estimation API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.resume import Resume
from app.models.user import User
from app.schemas.estimate import EstimateRequest, EstimateResponse
from app.services.estimation import estimation_service

router = APIRouter(prefix="/estimates", tags=["estimates"])


@router.post(
    "",
    response_model=EstimateResponse,
    status_code=status.HTTP_200_OK,
    summary="Estimate salary for a profile",
)
async def create_estimate(
    data: EstimateRequest,
    db: AsyncSession = Depends(get_db),
) -> EstimateResponse:
    """Run the full estimation pipeline: ML prediction + LLM recommendations.

    Creates a temporary resume record, runs estimation, returns results.
    """
    # Create anonymous user + resume for this estimation
    user = User(id=uuid.uuid4(), email=f"anon-{uuid.uuid4().hex[:8]}@zarabotok.local")
    db.add(user)
    await db.flush()

    resume = Resume(
        id=uuid.uuid4(),
        user_id=user.id,
        job_title=data.job_title,
        experience_years=data.experience_years,
        skills=data.skills,
        location=data.location,
        education_level=data.education_level,
        experience_entries=data.experience_entries,
    )
    db.add(resume)
    await db.flush()

    # Run estimation pipeline
    result = await estimation_service.estimate(db=db, resume=resume)
    return result


@router.post(
    "/resume/{resume_id}",
    response_model=EstimateResponse,
    summary="Re-estimate salary for an existing resume",
)
async def re_estimate(
    resume_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EstimateResponse:
    """Re-run estimation for an existing (possibly updated) resume.

    This is the core of the iterative improvement loop.
    """
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    estimate_result = await estimation_service.estimate(db=db, resume=resume)
    return estimate_result


@router.get(
    "/{estimate_id}",
    response_model=EstimateResponse,
    summary="Get a previous estimate by ID",
)
async def get_estimate(
    estimate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EstimateResponse:
    """Retrieve a cached salary estimate with its recommendations."""
    from app.models.estimate import SalaryEstimate
    from app.schemas.estimate import MarketInsights, SalaryRange, ShapContribution
    from app.schemas.recommendation import RecommendationResponse

    result = await db.execute(select(SalaryEstimate).where(SalaryEstimate.id == estimate_id))
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    shap = estimate.shap_values or {}

    return EstimateResponse(
        id=estimate.id,
        resume_id=estimate.resume_id,
        salary_range=SalaryRange(
            p25=estimate.p25_salary,
            p50=estimate.p50_salary,
            p75=estimate.p75_salary,
        ),
        market_insights=MarketInsights(
            vacancies_analyzed=0,
            skill_match_percentage=0,
            top_missing_skills=[],
            demand_trend="stable",
        ),
        shap_contributions=[ShapContribution(feature=k, contribution_rub=int(v)) for k, v in shap.items()],
        recommendations=[
            RecommendationResponse(
                id=r.id,
                priority=r.priority,
                category=r.category,
                title=r.title,
                description=r.description,
                impact=r.impact,
                action=r.action,
            )
            for r in estimate.recommendations
        ],
        calculated_at=estimate.calculated_at,
    )
