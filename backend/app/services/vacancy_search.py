"""Vacancy search service — finds similar market vacancies for context."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vacancy import Vacancy

logger = logging.getLogger(__name__)


class VacancySearchService:
    """Search reference vacancies in the dataset for market context."""

    async def find_similar(
        self,
        db: AsyncSession,
        job_title: str,
        skills: list[str],
        location: str | None = None,
        limit: int = 50,
    ) -> dict:
        """Find vacancies matching title/skills and compute market stats."""
        # Build query with ILIKE for title matching
        query = select(Vacancy).where(Vacancy.title.ilike(f"%{job_title}%"))

        if location:
            query = query.where(Vacancy.location.ilike(f"%{location}%"))

        query = query.order_by(Vacancy.parsed_at.desc()).limit(limit)

        result = await db.execute(query)
        vacancies = result.scalars().all()

        if not vacancies:
            return self._empty_insights()

        # Compute stats
        all_required_skills: list[str] = []
        for v in vacancies:
            if isinstance(v.skills_required, list):
                all_required_skills.extend(v.skills_required)

        # Skill match percentage
        if all_required_skills:
            unique_required = set(s.lower() for s in all_required_skills)
            user_skills = set(s.lower() for s in skills)
            matched = user_skills & unique_required
            match_pct = round(len(matched) / len(unique_required) * 100, 1) if unique_required else 0
            missing = list(unique_required - user_skills)[:5]
        else:
            match_pct = 0
            missing = []

        return {
            "vacancies_analyzed": len(vacancies),
            "skill_match_percentage": match_pct,
            "top_missing_skills": missing,
            "demand_trend": "stable",
        }

    def _empty_insights(self) -> dict:
        """Return empty insights when no vacancies found."""
        return {
            "vacancies_analyzed": 0,
            "skill_match_percentage": 0,
            "top_missing_skills": [],
            "demand_trend": "unknown",
        }


vacancy_search_service = VacancySearchService()
