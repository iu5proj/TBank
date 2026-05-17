"""Estimation orchestrator — coordinates ML prediction, LLM recommendations, and DB persistence."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.estimate import SalaryEstimate
from app.models.recommendation import Recommendation
from app.models.resume import Resume
from app.schemas.estimate import EstimateResponse, MarketInsights, SalaryRange, ShapContribution
from app.schemas.recommendation import RecommendationResponse
from app.services.ml_client import ml_client
from app.services.recommendation import recommendation_service
from app.services.vacancy_search import vacancy_search_service

logger = logging.getLogger(__name__)


class EstimationService:
    """Orchestrates the full estimation pipeline:
    1. Search similar vacancies for market context
    2. Call ML service for quantile prediction + SHAP
    3. Generate LLM recommendations
    4. Persist results to DB
    5. Return structured response
    """

    async def estimate(self, db: AsyncSession, resume: Resume) -> EstimateResponse:
        """Run the full estimation pipeline for a resume."""
        skills_list = resume.skills if isinstance(resume.skills, list) else []

        # Step 1: Market context
        market_data = await vacancy_search_service.find_similar(
            db=db,
            job_title=resume.job_title,
            skills=skills_list,
            location=resume.location,
        )

        # Step 2: ML prediction
        prediction = await ml_client.predict(
            job_title=resume.job_title,
            experience_years=float(resume.experience_years),
            skills=skills_list,
            location=resume.location,
            education_level=resume.education_level,
        )

        # Step 3: LLM recommendations
        rec_data = await recommendation_service.generate(
            job_title=resume.job_title,
            skills=skills_list,
            experience_years=float(resume.experience_years),
            location=resume.location,
            salary_p50=prediction.p50_salary,
            shap_values=prediction.shap_values,
            counterfactuals=prediction.counterfactuals,
        )

        # Step 4: Persist estimate
        estimate = SalaryEstimate(
            id=uuid.uuid4(),
            resume_id=resume.id,
            p25_salary=prediction.p25_salary,
            p50_salary=prediction.p50_salary,
            p75_salary=prediction.p75_salary,
            shap_values=prediction.shap_values,
        )
        db.add(estimate)
        await db.flush()

        # Persist recommendations
        db_recommendations = []
        for rec in rec_data:
            db_rec = Recommendation(
                id=uuid.UUID(rec["id"]) if isinstance(rec.get("id"), str) else uuid.uuid4(),
                estimate_id=estimate.id,
                priority=rec.get("priority", 3),
                category=rec.get("category", "hard_skill"),
                title=rec.get("title", ""),
                description=rec.get("description", ""),
                impact=rec.get("impact", ""),
                action=rec.get("action", ""),
            )
            db.add(db_rec)
            db_recommendations.append(db_rec)

        await db.flush()

        # Step 5: Build response
        shap_contributions = [
            ShapContribution(feature=feat, contribution_rub=int(val)) for feat, val in prediction.shap_values.items()
        ]

        recommendation_responses = [
            RecommendationResponse(
                id=r.id,
                priority=r.priority,
                category=r.category,
                title=r.title,
                description=r.description,
                impact=r.impact,
                action=r.action,
            )
            for r in db_recommendations
        ]

        return EstimateResponse(
            id=estimate.id,
            resume_id=resume.id,
            salary_range=SalaryRange(
                p25=prediction.p25_salary,
                p50=prediction.p50_salary,
                p75=prediction.p75_salary,
            ),
            market_insights=MarketInsights(**market_data),
            shap_contributions=shap_contributions,
            recommendations=recommendation_responses,
            calculated_at=estimate.calculated_at,
        )


estimation_service = EstimationService()
