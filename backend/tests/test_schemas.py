"""Tests for Pydantic schemas — validation logic."""

import pytest
from pydantic import ValidationError

from app.schemas.estimate import (
    EstimateRequest,
    MarketInsights,
    SalaryRange,
)
from app.schemas.recommendation import RecommendationResponse
from app.schemas.resume import ExperienceEntry, ResumeCreate, ResumeUpdate


class TestExperienceEntry:
    """Test ExperienceEntry schema validation."""

    def test_valid_entry(self):
        entry = ExperienceEntry(
            company="Яндекс",
            title="Backend Developer",
            duration_months=24,
            description="Разрабатывал сервисы",
        )
        assert entry.company == "Яндекс"
        assert entry.duration_months == 24

    def test_empty_company_rejected(self):
        with pytest.raises(ValidationError):
            ExperienceEntry(
                company="",
                title="Developer",
                duration_months=12,
            )

    def test_negative_duration_rejected(self):
        with pytest.raises(ValidationError):
            ExperienceEntry(
                company="Test",
                title="Developer",
                duration_months=-1,
            )

    def test_excessive_duration_rejected(self):
        with pytest.raises(ValidationError):
            ExperienceEntry(
                company="Test",
                title="Developer",
                duration_months=601,
            )

    def test_default_description_is_empty(self):
        entry = ExperienceEntry(
            company="Test",
            title="Developer",
            duration_months=12,
        )
        assert entry.description == ""


class TestResumeCreate:
    """Test ResumeCreate schema validation."""

    def test_valid_resume(self, sample_resume_data):
        resume = ResumeCreate(**sample_resume_data)
        assert resume.job_title == "Senior Python Developer"
        assert resume.experience_years == 5.0
        assert len(resume.skills) == 3
        assert resume.education_level == "bachelor"

    def test_empty_job_title_rejected(self):
        with pytest.raises(ValidationError):
            ResumeCreate(
                job_title="",
                experience_years=5.0,
                skills=["Python"],
                location="Москва",
            )

    def test_negative_experience_rejected(self):
        with pytest.raises(ValidationError):
            ResumeCreate(
                job_title="Developer",
                experience_years=-1,
                skills=["Python"],
                location="Москва",
            )

    def test_experience_over_50_rejected(self):
        with pytest.raises(ValidationError):
            ResumeCreate(
                job_title="Developer",
                experience_years=51,
                skills=["Python"],
                location="Москва",
            )

    def test_empty_skills_rejected(self):
        with pytest.raises(ValidationError):
            ResumeCreate(
                job_title="Developer",
                experience_years=5,
                skills=[],
                location="Москва",
            )

    def test_invalid_education_rejected(self):
        with pytest.raises(ValidationError):
            ResumeCreate(
                job_title="Developer",
                experience_years=5,
                skills=["Python"],
                location="Москва",
                education_level="invalid_value",
            )

    def test_default_education_is_none(self):
        resume = ResumeCreate(
            job_title="Developer",
            experience_years=5,
            skills=["Python"],
            location="Москва",
        )
        assert resume.education_level == "none"

    def test_experience_entries_default_empty(self):
        resume = ResumeCreate(
            job_title="Developer",
            experience_years=5,
            skills=["Python"],
            location="Москва",
        )
        assert resume.experience_entries == []


class TestResumeUpdate:
    """Test ResumeUpdate partial update schema."""

    def test_all_none_by_default(self):
        update = ResumeUpdate()
        assert update.job_title is None
        assert update.experience_years is None
        assert update.skills is None

    def test_partial_update(self):
        update = ResumeUpdate(skills=["Python", "Docker"])
        assert update.skills == ["Python", "Docker"]
        assert update.job_title is None

    def test_exclude_unset(self):
        update = ResumeUpdate(skills=["Python"])
        dumped = update.model_dump(exclude_unset=True)
        assert "skills" in dumped
        assert "job_title" not in dumped


class TestSalaryRange:
    """Test SalaryRange schema."""

    def test_valid_range(self):
        sr = SalaryRange(p25=80000, p50=120000, p75=170000)
        assert sr.p25 < sr.p50 < sr.p75

    def test_serialization(self):
        sr = SalaryRange(p25=80000, p50=120000, p75=170000)
        data = sr.model_dump()
        assert data == {"p25": 80000, "p50": 120000, "p75": 170000}


class TestMarketInsights:
    """Test MarketInsights schema."""

    def test_valid_insights(self):
        mi = MarketInsights(
            vacancies_analyzed=342,
            skill_match_percentage=72.5,
            top_missing_skills=["Docker"],
            demand_trend="growing",
        )
        assert mi.vacancies_analyzed == 342

    def test_skill_match_over_100_rejected(self):
        with pytest.raises(ValidationError):
            MarketInsights(
                vacancies_analyzed=10,
                skill_match_percentage=101.0,
            )

    def test_negative_skill_match_rejected(self):
        with pytest.raises(ValidationError):
            MarketInsights(
                vacancies_analyzed=10,
                skill_match_percentage=-5.0,
            )


class TestRecommendationResponse:
    """Test RecommendationResponse schema."""

    def test_valid_recommendation(self):
        rec = RecommendationResponse(
            id="550e8400-e29b-41d4-a716-446655440000",
            priority=1,
            category="hard_skill",
            title="Добавьте Docker",
            description="Docker нужен",
            impact="+15 000 руб.",
            action="Добавьте Docker в навыки",
        )
        assert rec.priority == 1
        assert rec.category == "hard_skill"

    def test_priority_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            RecommendationResponse(
                id="550e8400-e29b-41d4-a716-446655440000",
                priority=6,
                category="hard_skill",
                title="Test",
                description="Test",
                impact="Test",
                action="Test",
            )

    def test_invalid_category_rejected(self):
        with pytest.raises(ValidationError):
            RecommendationResponse(
                id="550e8400-e29b-41d4-a716-446655440000",
                priority=1,
                category="invalid_category",
                title="Test",
                description="Test",
                impact="Test",
                action="Test",
            )


class TestEstimateRequest:
    """Test EstimateRequest schema."""

    def test_valid_request(self, sample_estimate_data):
        req = EstimateRequest(**sample_estimate_data)
        assert req.job_title == "Senior Python Developer"

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            EstimateRequest(
                job_title="",
                experience_years=5,
                skills=["Python"],
                location="Москва",
            )
