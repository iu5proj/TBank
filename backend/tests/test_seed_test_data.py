"""Tests for local seed data helpers."""

from app.schemas.analyze import ResumeProfile
from app.seed_test_data import segment_rows, vacancy_rows
from app.services.preflight import build_segment_key


def test_seed_contains_demo_backend_segment():
    segments = {row["segment_key"]: row for row in segment_rows()}
    assert "backend_developer:python:moscow:middle" in segments
    assert segments["backend_developer:python:moscow:middle"]["vacancies_count"] == 8


def test_seed_contains_backend_vacancies_with_salary_ranges():
    rows = [row for row in vacancy_rows() if row["segment_key"] == "backend_developer:python:moscow:middle"]
    assert len(rows) == 8
    assert all(row["salary_min_net"] and row["salary_max_net"] for row in rows)
    assert all(row["source"] == "test_seed" for row in rows)


def test_demo_profile_maps_to_seeded_segment():
    profile = ResumeProfile(
        title="Python Backend Developer",
        experience_years=3,
        location="Москва",
        skills=["Python", "FastAPI", "PostgreSQL"],
    )
    assert build_segment_key(profile) == "backend_developer:python:moscow:middle"
