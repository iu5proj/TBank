"""Tests for the GPT-OSS analyze contract."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.analyze import AnalyzeRequest, CandidateVacancy, GptOssSalaryResult, SalaryQuantiles
from app.services.analyze import validate_gpt_oss_output
from app.services.market_evidence import build_candidate_segment_keys, build_market_evidence
from app.services.preflight import build_segment_key, calculate_request_hash, is_stale, parse_segment_key


def _request() -> AnalyzeRequest:
    return AnalyzeRequest(
        profile={
            "title": "Python Backend Developer",
            "experience_years": 3,
            "location": "Москва",
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "resume_text": "Built FastAPI services.",
            "current_salary": 150000,
        },
        options={"target_salary": 250000, "force_refresh": False},
    )


def _input_payload(request_hash: str) -> dict:
    return {
        "request_hash": request_hash,
        "profile": _request().profile.model_dump(mode="json"),
        "segment": {
            "segment_key": "backend_developer:python:moscow:middle",
            "segment_data_version": "2026-05-15",
            "last_successful_update_at": "2026-05-15T09:30:00Z",
        },
        "candidate_vacancies": [
            {
                "id": "v1",
                "title": "Python Backend Developer",
                "description": "FastAPI services",
                "salary_min_net": 180000,
                "salary_max_net": 250000,
                "location": "Москва",
                "experience_range": "3-6",
                "skills_required": ["Python", "FastAPI", "Docker"],
                "source": "hh",
                "published_at": "2026-05-10",
            }
        ],
        "rules": {
            "use_only_candidate_vacancies": True,
            "do_not_use_external_salary_knowledge": True,
            "return_only_json": True,
        },
    }


def _valid_output(request_hash: str) -> dict:
    return {
        "request_hash": request_hash,
        "segment": {
            "segment_key": "backend_developer:python:moscow:middle",
            "segment_data_version": "2026-05-15",
        },
        "market_sample": {
            "candidate_vacancies_received": 1,
            "vacancies_used_for_estimation": 1,
            "used_vacancy_ids": ["v1"],
            "excluded_vacancies": [],
            "salary_quantiles": {"p25": 180000, "p50": 210000, "p75": 250000},
        },
        "salary_range": {"min": 180000, "median": 210000, "max": 250000, "currency": "RUB"},
        "confidence": {"score": 0.8, "level": "high", "reason": "Fresh candidate vacancies."},
        "matched_skills": ["Python", "FastAPI"],
        "missing_skills": [{"skill": "Docker", "impact": "high", "reason": "Present in candidate vacancy."}],
        "factor_analysis": [
            {"factor": "Experience 3 years", "impact": "positive", "explanation": "Matches middle segment."}
        ],
        "recommendations": [
            {
                "priority": 1,
                "type": "skill_gap",
                "title": "Add Docker",
                "resume_change": "Add Docker only if there is real project experience.",
                "expected_salary_effect": None,
            }
        ],
    }


def test_segment_key_matches_spec_example():
    assert build_segment_key(_request().profile) == "backend_developer:python:moscow:middle"


def test_parse_segment_key_roundtrip_for_manual_parser_activation():
    parts = parse_segment_key("backend_developer:python:moscow:middle")

    assert parts.role_cluster == "backend_developer"
    assert parts.specialization == "python"
    assert parts.region == "moscow"
    assert parts.experience_bucket == "middle"
    assert parts.segment_key == "backend_developer:python:moscow:middle"


def test_stale_after_14_days():
    assert is_stale(datetime.now(timezone.utc) - timedelta(days=14))
    assert not is_stale(datetime.now(timezone.utc) - timedelta(days=13, hours=23))


def test_request_hash_is_stable_for_same_payload():
    request = _request()
    first = calculate_request_hash(
        profile=request.profile,
        segment_key="backend_developer:python:moscow:middle",
        segment_data_version="2026-05-15",
    )
    second = calculate_request_hash(
        profile=request.profile,
        segment_key="backend_developer:python:moscow:middle",
        segment_data_version="2026-05-15",
    )
    assert first == second
    assert len(first) == 64


def test_request_hash_changes_when_prompt_version_changes():
    request = _request()
    first = calculate_request_hash(
        profile=request.profile,
        segment_key="backend_developer:python:moscow:middle",
        segment_data_version="2026-05-15",
        prompt_version="salary_estimation_prompt_v1",
    )
    second = calculate_request_hash(
        profile=request.profile,
        segment_key="backend_developer:python:moscow:middle",
        segment_data_version="2026-05-15",
        prompt_version="salary_estimation_prompt_v2",
    )
    assert first != second


def test_real_cyrillic_moscow_maps_to_seeded_segment():
    request = AnalyzeRequest(
        profile={
            "title": "Python Backend Developer",
            "experience_years": 3,
            "location": "Москва",
            "skills": ["Python", "FastAPI", "PostgreSQL"],
        },
    )
    assert build_segment_key(request.profile) == "backend_developer:python:moscow:middle"


def test_unicode_moscow_maps_to_seeded_segment():
    request = AnalyzeRequest(
        profile={
            "title": "Python Backend Developer",
            "experience_years": 3,
            "location": "Москва",
            "skills": ["Python", "FastAPI", "PostgreSQL"],
        },
    )
    assert build_segment_key(request.profile) == "backend_developer:python:moscow:middle"


def test_unicode_data_analyst_maps_to_data_segment():
    request = AnalyzeRequest(
        profile={
            "title": "Аналитик данных",
            "experience_years": 4,
            "location": "Москва",
            "skills": ["SQL", "Python"],
        },
    )
    assert build_segment_key(request.profile).startswith("data_specialist:")


def test_gpt_oss_result_schema_accepts_spec_payload():
    result = GptOssSalaryResult.model_validate(_valid_output("hash"))
    assert result.salary_range.currency == "RUB"
    assert result.recommendations[0].type == "skill_gap"


def test_salary_quantiles_order_invalid():
    with pytest.raises(ValidationError):
        SalaryQuantiles(p25=250000, p50=210000, p75=180000)


def test_output_validation_checks_linkage_to_input_payload():
    request_hash = "abc123"
    validation = validate_gpt_oss_output(_valid_output(request_hash), _input_payload(request_hash))
    assert validation.status == "valid"
    assert validation.errors == []


def test_output_validation_rejects_unknown_used_vacancy_id():
    request_hash = "abc123"
    output = _valid_output(request_hash)
    output["market_sample"]["used_vacancy_ids"] = ["missing"]
    validation = validate_gpt_oss_output(output, _input_payload(request_hash))
    assert validation.status == "failed"
    assert any("used_vacancy_ids" in error for error in validation.errors)


def test_output_validation_rejects_used_vacancy_count_mismatch():
    request_hash = "abc123"
    output = _valid_output(request_hash)
    output["market_sample"]["vacancies_used_for_estimation"] = 2
    validation = validate_gpt_oss_output(output, _input_payload(request_hash))
    assert validation.status == "failed"
    assert any("vacancies_used_for_estimation" in error for error in validation.errors)


def test_output_validation_rejects_duplicate_used_vacancy_ids():
    request_hash = "abc123"
    output = _valid_output(request_hash)
    output["market_sample"]["candidate_vacancies_received"] = 2
    output["market_sample"]["vacancies_used_for_estimation"] = 2
    output["market_sample"]["used_vacancy_ids"] = ["v1", "v1"]
    input_payload = _input_payload(request_hash)
    input_payload["candidate_vacancies"].append({**input_payload["candidate_vacancies"][0], "id": "v2"})
    validation = validate_gpt_oss_output(output, input_payload)
    assert validation.status == "failed"
    assert any("duplicates" in error for error in validation.errors)


def test_output_validation_accepts_skill_aliases():
    request_hash = "abc123"
    input_payload = _input_payload(request_hash)
    input_payload["profile"]["skills"] = ["Postgres"]
    output = _valid_output(request_hash)
    output["matched_skills"] = ["PostgreSQL"]
    output["missing_skills"] = [{"skill": "REST", "impact": "medium", "reason": "Required in sample."}]
    input_payload["candidate_vacancies"][0]["skills_required"] = ["Postgres", "rest api"]

    validation = validate_gpt_oss_output(output, input_payload)

    assert validation.status == "valid"


def test_market_evidence_builds_skill_pricing_and_fit():
    profile = _request().profile
    vacancies = [
        CandidateVacancy(
            id="v1",
            segment_key="backend_developer:python:moscow:middle",
            title="Python Backend Developer",
            salary_min_net=180000,
            salary_max_net=220000,
            skills_required=["Python", "FastAPI", "Docker"],
            source="fixture",
        ),
        CandidateVacancy(
            id="v2",
            segment_key="backend_developer:python:moscow:middle",
            title="Python Platform Engineer",
            salary_min_net=240000,
            salary_max_net=300000,
            skills_required=["Python", "FastAPI", "Kubernetes"],
            source="fixture",
        ),
        CandidateVacancy(
            id="v3",
            segment_key="backend_developer:python:moscow:middle",
            title="Python API Developer",
            salary_min_net=200000,
            salary_max_net=240000,
            skills_required=["Python", "FastAPI", "Docker"],
            source="fixture",
        ),
    ]

    evidence = build_market_evidence(
        profile=profile,
        target_segment_key="backend_developer:python:moscow:middle",
        candidate_segment_keys=build_candidate_segment_keys("backend_developer:python:moscow:middle"),
        candidate_vacancies=vacancies,
    )

    assert evidence["salary_quantiles"]["p50"] == 220000
    assert evidence["resume_market_fit"]["matched_skills"] == ["Python", "FastAPI"]
    assert evidence["resume_market_fit"]["missing_skills"][0]["skill"] == "Kubernetes"
    assert evidence["recommendation_candidates"][0]["type"] == "skill_gap"
    assert evidence["recommendation_candidates"][0]["title"] == "Добавить подтверждение Kubernetes"
    assert evidence["recommendation_candidates"][0]["expected_salary_effect"] == (
        "+50000 RUB к медиане выборки"
    )
