"""Lightweight eval checks for model-output grounding."""

from __future__ import annotations

from app.services.analyze import validate_gpt_oss_output


def test_eval_rejects_hallucinated_missing_skill():
    input_payload = {
        "request_hash": "hash",
        "profile": {"skills": ["Python"]},
        "segment": {"segment_key": "backend:python:moscow:middle", "segment_data_version": "2026-05-17"},
        "candidate_vacancies": [
            {
                "id": "v1",
                "title": "Python Backend Developer",
                "salary_min_net": 100000,
                "salary_max_net": 150000,
                "skills_required": ["Python", "FastAPI"],
                "source": "fixture",
            }
        ],
    }
    output = {
        "request_hash": "hash",
        "segment": {"segment_key": "backend:python:moscow:middle", "segment_data_version": "2026-05-17"},
        "market_sample": {
            "candidate_vacancies_received": 1,
            "vacancies_used_for_estimation": 1,
            "used_vacancy_ids": ["v1"],
            "excluded_vacancies": [],
            "salary_quantiles": {"p25": 100000, "p50": 120000, "p75": 150000},
        },
        "salary_range": {"min": 100000, "median": 120000, "max": 150000, "currency": "RUB"},
        "confidence": {"score": 0.6, "level": "medium", "reason": "Fixture sample."},
        "matched_skills": ["Python"],
        "missing_skills": [{"skill": "Kubernetes", "impact": "medium", "reason": "Hallucinated."}],
        "factor_analysis": [{"factor": "Experience", "impact": "neutral", "explanation": "Grounded."}],
        "recommendations": [
            {
                "priority": 1,
                "type": "skill_gap",
                "title": "Do not hallucinate skills",
                "resume_change": "Use only candidate vacancy skills.",
            }
        ],
    }

    validation = validate_gpt_oss_output(output, input_payload)

    assert validation.status == "failed"
    assert any("missing_skills" in error for error in validation.errors)

