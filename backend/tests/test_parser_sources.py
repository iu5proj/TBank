"""Tests for segment-scoped vacancy source behavior."""

from __future__ import annotations

import pytest

from app.services.parser import (
    SegmentQuery,
    _extract_skills,
    _fetch_source,
    _fixture_vacancies,
    _normalize_location,
    _normalize_salary_range,
    collect_segment_vacancies,
)


def test_fixture_source_generates_segment_scoped_salary_vacancies():
    query = SegmentQuery(
        segment_key="backend_developer:python:moscow:middle",
        role_cluster="backend_developer",
        specialization="python",
        region="moscow",
        experience_bucket="middle",
    )

    vacancies = _fixture_vacancies(query)

    assert len(vacancies) >= 5
    assert all(v.segment_key == query.segment_key for v in vacancies)
    assert all(v.usable_for_salary_sample for v in vacancies)
    assert {v.source for v in vacancies} == {"fixture"}


def test_salary_normalization_converts_gross_to_net_rub():
    salary_min, salary_max = _normalize_salary_range(100_000, 200_000, currency="RUR", gross=True)

    assert salary_min == 87_000
    assert salary_max == 174_000


def test_location_normalization_repairs_mojibake_city():
    mojibake = "Санкт-Петербург".encode("utf-8").decode("cp1251")

    assert _normalize_location(mojibake) == "saint_petersburg"


def test_skill_extraction_uses_token_boundaries():
    skills = _extract_skills("Django REST API developer with PostgreSQL")

    assert "django" in skills
    assert "rest" in skills
    assert "postgresql" in skills
    assert "go" not in skills


def test_skill_extraction_does_not_match_plain_substrings():
    assert "rest" not in _extract_skills("Strong interest in backend systems")


def test_skill_extraction_matches_hyphenated_skill_mentions():
    assert "rest" in _extract_skills("Designed REST-api integrations")


@pytest.mark.asyncio
async def test_habr_source_is_optional_without_token(monkeypatch):
    monkeypatch.setattr("app.services.parser.settings.HABR_CAREER_API_TOKEN", "")
    query = SegmentQuery(
        segment_key="backend_developer:python:moscow:middle",
        role_cluster="backend_developer",
        specialization="python",
        region="moscow",
        experience_bucket="middle",
    )

    vacancies = await _fetch_source(client=None, source="habr", query=query)  # type: ignore[arg-type]

    assert vacancies == []


@pytest.mark.asyncio
async def test_collect_segment_vacancies_reports_fixture_source():
    query = SegmentQuery(
        segment_key="backend_developer:python:moscow:middle",
        role_cluster="backend_developer",
        specialization="python",
        region="moscow",
        experience_bucket="middle",
    )

    vacancies, reports = await collect_segment_vacancies(query, force_sources=["fixture"])

    assert len(vacancies) >= 5
    assert reports[0].source == "fixture"
    assert reports[0].status == "ok"
    assert reports[0].usable_count == len(vacancies)


@pytest.mark.asyncio
async def test_collect_segment_vacancies_reports_habr_without_token(monkeypatch):
    monkeypatch.setattr("app.services.parser.settings.HABR_CAREER_API_TOKEN", "")
    query = SegmentQuery(
        segment_key="backend_developer:python:moscow:middle",
        role_cluster="backend_developer",
        specialization="python",
        region="moscow",
        experience_bucket="middle",
    )

    vacancies, reports = await collect_segment_vacancies(query, force_sources=["habr"])

    assert vacancies == []
    assert reports[0].source == "habr"
    assert reports[0].status == "skipped"
    assert "HABR_CAREER_API_TOKEN" in reports[0].error
