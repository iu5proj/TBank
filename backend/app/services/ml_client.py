"""HTTP client for the ML prediction microservice."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class MLPrediction:
    """Structured ML prediction result."""

    p25_salary: int
    p50_salary: int
    p75_salary: int
    shap_values: dict[str, float]
    counterfactuals: list[dict]


class MLClient:
    """Async HTTP client to ML Service (:8001).

    If ML service is unavailable, returns a fallback heuristic prediction.
    """

    def __init__(self) -> None:
        self.base_url = settings.ML_SERVICE_URL
        self.timeout = settings.ML_SERVICE_TIMEOUT

    async def predict(
        self,
        job_title: str,
        experience_years: float,
        skills: list[str],
        location: str,
        education_level: str,
    ) -> MLPrediction:
        """Send profile vector to ML service and get quantile prediction."""
        payload = {
            "job_title": job_title,
            "experience_years": experience_years,
            "skills": skills,
            "location": location,
            "education_level": education_level,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/predict",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                return MLPrediction(
                    p25_salary=data["p25_salary"],
                    p50_salary=data["p50_salary"],
                    p75_salary=data["p75_salary"],
                    shap_values=data.get("shap_values", {}),
                    counterfactuals=data.get("counterfactuals", []),
                )

        except (httpx.HTTPError, KeyError) as exc:
            logger.warning("ML service unavailable, using fallback: %s", exc)
            return self._fallback_prediction(experience_years, skills)

    def _fallback_prediction(self, experience_years: float, skills: list[str]) -> MLPrediction:
        """Simple heuristic fallback when ML service is down."""
        base = 60_000
        exp_bonus = int(experience_years * 12_000)
        skill_bonus = len(skills) * 3_000
        median = base + exp_bonus + skill_bonus

        return MLPrediction(
            p25_salary=int(median * 0.75),
            p50_salary=median,
            p75_salary=int(median * 1.35),
            shap_values={
                "experience_years": exp_bonus,
                "skills_count": skill_bonus,
            },
            counterfactuals=[],
        )


ml_client = MLClient()
