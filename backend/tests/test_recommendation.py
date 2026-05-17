"""Tests for recommendation service."""

import uuid
from unittest.mock import patch

import pytest

from app.services.recommendation import RecommendationService


class TestRecommendationService:
    """Test LLM recommendation generation and fallback."""

    @pytest.fixture
    def service(self):
        """Service with no API key — will use templates."""
        with patch("app.services.recommendation.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = ""
            mock_settings.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
            return RecommendationService()

    @pytest.mark.asyncio
    async def test_template_fallback_when_no_api_key(self, service):
        """Without API key, service returns template recommendations."""
        result = await service.generate(
            job_title="Python Developer",
            skills=["Python"],
            experience_years=3.0,
            location="Москва",
            salary_p50=100000,
            shap_values={"experience_years": 30000, "skills:Docker": -15000},
            counterfactuals=[],
        )

        assert isinstance(result, list)
        assert len(result) > 0
        for rec in result:
            assert "id" in rec
            assert "priority" in rec
            assert "category" in rec
            assert "title" in rec
            assert "impact" in rec

    def test_template_recommendations_sorted_by_shap(self, service):
        """Template recommendations should prioritize lowest SHAP values."""
        shap_values = {
            "skills:Docker": -15000.0,
            "experience_years": 30000.0,
            "skills:Kubernetes": -25000.0,
        }

        result = service._template_recommendations(shap_values)

        assert len(result) == 3
        # Lowest SHAP first → Kubernetes (most negative) should be priority 1
        assert result[0]["priority"] == 1
        assert "Kubernetes" in result[0]["title"]

    def test_template_recommendations_max_3(self, service):
        """Template recommendations limited to 3."""
        shap_values = {f"skill_{i}": float(-i * 1000) for i in range(10)}
        result = service._template_recommendations(shap_values)
        assert len(result) <= 3

    def test_template_recommendation_has_uuid(self, service):
        """Each template recommendation should have a valid UUID."""
        result = service._template_recommendations({"test": -5000.0})
        for rec in result:
            uuid.UUID(rec["id"])  # Will raise if invalid

    def test_build_user_prompt(self, service):
        """Prompt should contain all key information."""
        prompt = service._build_user_prompt(
            job_title="Python Dev",
            skills=["Python", "FastAPI"],
            experience_years=3.0,
            location="Москва",
            salary_p50=100000,
            shap_values={"exp": 10000, "skill": -5000},
            counterfactuals=[{"change": "add Docker"}],
        )

        assert "Python Dev" in prompt
        assert "Python" in prompt
        assert "FastAPI" in prompt
        assert "Москва" in prompt
        assert "100,000" in prompt or "100000" in prompt
