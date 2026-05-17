"""Legacy recommendation service for non-analyze endpoints.

The ML/RAG analyze endpoint does not use this service. It remains for existing
resume/estimate code paths copied from the older backend.
"""

from __future__ import annotations

import json
import logging
import uuid

from anthropic import AsyncAnthropic

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a career consultant.
Generate concrete resume-improvement recommendations from the provided profile,
salary estimate and feature contributions.

Rules:
1. Return strict JSON array without markdown.
2. Each item must include priority, category, title, description, impact and action.
3. Do not suggest adding skills without real experience.
"""


class RecommendationService:
    """Generates structured resume-improvement recommendations."""

    def __init__(self) -> None:
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None
        self.model = settings.ANTHROPIC_MODEL

    async def generate(
        self,
        job_title: str,
        skills: list[str],
        experience_years: float,
        location: str,
        salary_p50: int,
        shap_values: dict[str, float],
        counterfactuals: list[dict],
    ) -> list[dict]:
        """Generate recommendations or return deterministic templates."""
        if not self.client:
            logger.warning("Anthropic API key not set, returning template recommendations")
            return self._template_recommendations(shap_values)

        user_prompt = self._build_user_prompt(
            job_title,
            skills,
            experience_years,
            location,
            salary_p50,
            shap_values,
            counterfactuals,
        )

        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw_text = message.content[0].text
            recommendations = json.loads(raw_text)
            for recommendation in recommendations:
                recommendation["id"] = str(uuid.uuid4())
            return recommendations[:5]
        except Exception as exc:  # noqa: BLE001 - legacy fallback path must not break API
            logger.error("LLM recommendation generation failed: %s", exc)
            return self._template_recommendations(shap_values)

    def _build_user_prompt(
        self,
        job_title: str,
        skills: list[str],
        experience_years: float,
        location: str,
        salary_p50: int,
        shap_values: dict[str, float],
        counterfactuals: list[dict],
    ) -> str:
        """Assemble structured prompt from profile and legacy ML outputs."""
        negative_shap = {key: value for key, value in shap_values.items() if value < 0}
        positive_shap = {key: value for key, value in shap_values.items() if value > 0}
        return "\n".join(
            [
                "PROFILE:",
                f"- Job title: {job_title}",
                f"- Experience: {experience_years} years",
                f"- Skills: {', '.join(skills)}",
                f"- Location: {location}",
                f"- Salary median: {salary_p50:,} RUB",
                f"- Positive feature contribution: {json.dumps(positive_shap, ensure_ascii=False)}",
                f"- Negative feature contribution: {json.dumps(negative_shap, ensure_ascii=False)}",
                f"- Counterfactuals: {json.dumps(counterfactuals, ensure_ascii=False)}",
                "Return 3-5 recommendations as a JSON array.",
            ]
        )

    def _template_recommendations(self, shap_values: dict[str, float]) -> list[dict]:
        """Fallback template recommendations when the LLM is unavailable."""
        recommendations = []
        sorted_shap = sorted(shap_values.items(), key=lambda item: item[1])

        for priority, (feature, value) in enumerate(sorted_shap[:3], start=1):
            rubles = abs(int(value))
            recommendations.append(
                {
                    "id": str(uuid.uuid4()),
                    "priority": priority,
                    "category": "hard_skill",
                    "title": f"Improve profile evidence for {feature}",
                    "description": f"Feature '{feature}' lowers the estimate by {rubles:,} RUB.",
                    "impact": f"+{rubles:,} RUB to median",
                    "action": f"Add concrete, truthful resume evidence for '{feature}'.",
                }
            )

        return recommendations


recommendation_service = RecommendationService()

