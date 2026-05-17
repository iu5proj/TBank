"""Tests for ML client service."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.ml_client import MLClient, MLPrediction


class TestMLClient:
    """Test ML client with mock HTTP responses."""

    @pytest.fixture
    def client(self):
        return MLClient()

    @pytest.mark.asyncio
    async def test_successful_prediction(self, client):
        """ML service returns valid prediction."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "p25_salary": 80000,
            "p50_salary": 120000,
            "p75_salary": 170000,
            "shap_values": {"experience_years": 25000.0},
            "counterfactuals": [],
        }

        with patch("app.services.ml_client.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client_instance

            result = await client.predict(
                job_title="Senior Developer",
                experience_years=5.0,
                skills=["Python"],
                location="Москва",
                education_level="bachelor",
            )

            assert isinstance(result, MLPrediction)
            assert result.p25_salary == 80000
            assert result.p50_salary == 120000
            assert result.p75_salary == 170000
            assert "experience_years" in result.shap_values

    @pytest.mark.asyncio
    async def test_fallback_on_service_error(self, client):
        """ML service is down — fallback heuristic is used."""
        with patch("app.services.ml_client.httpx.AsyncClient") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client_instance

            result = await client.predict(
                job_title="Developer",
                experience_years=3.0,
                skills=["Python", "Docker"],
                location="Москва",
                education_level="none",
            )

            assert isinstance(result, MLPrediction)
            assert result.p50_salary > 0
            assert result.p25_salary < result.p50_salary < result.p75_salary

    def test_fallback_prediction_math(self, client):
        """Verify fallback heuristic produces sensible numbers."""
        result = client._fallback_prediction(
            experience_years=5.0,
            skills=["Python", "Docker", "Kubernetes"],
        )

        assert result.p25_salary < result.p50_salary < result.p75_salary
        assert result.p50_salary == 60_000 + int(5.0 * 12_000) + 3 * 3_000  # base + exp + skills
        assert "experience_years" in result.shap_values
        assert "skills_count" in result.shap_values

    def test_fallback_with_zero_experience(self, client):
        """Fallback with 0 experience still produces valid output."""
        result = client._fallback_prediction(experience_years=0, skills=[])
        assert result.p50_salary == 60_000
        assert result.p25_salary > 0
