"""Pydantic schemas — ML service API contract.

This is the INTERFACE CONTRACT between backend and ML service.
The ML developer should keep these schemas stable when replacing the stub predictor.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    """Input profile vector for salary prediction."""

    job_title: str = Field(..., examples=["Senior Python Developer"])
    experience_years: float = Field(..., ge=0, le=50, examples=[5.0])
    skills: list[str] = Field(..., examples=[["Python", "FastAPI", "PostgreSQL"]])
    location: str = Field(..., examples=["Москва"])
    education_level: str = Field(default="none", examples=["bachelor"])


class Counterfactual(BaseModel):
    """A hypothetical profile change that would increase salary."""

    change_description: str = Field(..., examples=["Добавить навык Docker"])
    feature_changed: str = Field(..., examples=["skills"])
    new_value: str = Field(..., examples=["Docker"])
    estimated_salary_increase: int = Field(..., examples=[15000])


class PredictionResponse(BaseModel):
    """Output prediction with quantile salary range + explainability."""

    p25_salary: int = Field(..., examples=[80000])
    p50_salary: int = Field(..., examples=[120000])
    p75_salary: int = Field(..., examples=[170000])
    shap_values: dict[str, float] = Field(
        default_factory=dict,
        description="Feature name → SHAP contribution in rubles",
        examples=[{"experience_years": 25000, "skills:Python": 15000, "location:Москва": 10000}],
    )
    counterfactuals: list[Counterfactual] = Field(default_factory=list)
