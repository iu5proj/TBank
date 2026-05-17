"""Tests for ML service local stub predictor."""

import uuid

import pytest

from app.predictor import (
    COMPACT_ANALYZE_PROMPT,
    OpenAICompatibleAnalyzer,
    StubPredictor,
    _compact_model_payload,
    _compact_vacancy,
    _decode_mojibake,
    _extract_message_content,
    _fallback_analyze_output,
    _location_multiplier,
    _messages,
    _normalize_analyze_output,
    _ollama_think_value,
    _parse_json_object,
    _vacancy_count_phrase,
)
from app.schemas import Counterfactual, PredictionRequest, PredictionResponse

MOSCOW = "РњРѕСЃРєРІР°"
KAZAN = "РљР°Р·Р°РЅСЊ"


class TestStubPredictor:
    @pytest.fixture
    def predictor(self):
        return StubPredictor()

    def test_basic_prediction(self, predictor):
        req = PredictionRequest(
            job_title="Senior Python Developer",
            experience_years=5.0,
            skills=["Python", "FastAPI", "PostgreSQL"],
            location=MOSCOW,
            education_level="bachelor",
        )
        result = predictor.predict(req)
        assert isinstance(result, PredictionResponse)
        assert result.p25_salary < result.p50_salary < result.p75_salary

    def test_moscow_pays_more(self, predictor):
        base = dict(job_title="Developer", experience_years=3.0, skills=["Python"])
        moscow = predictor.predict(PredictionRequest(**base, location=MOSCOW))
        kazan = predictor.predict(PredictionRequest(**base, location=KAZAN))
        assert moscow.p50_salary > kazan.p50_salary

    def test_senior_earns_more(self, predictor):
        base = dict(skills=["Python"], location=MOSCOW)
        senior = predictor.predict(PredictionRequest(job_title="Senior Dev", experience_years=5.0, **base))
        junior = predictor.predict(PredictionRequest(job_title="Junior Dev", experience_years=1.0, **base))
        assert senior.p50_salary > junior.p50_salary

    def test_more_skills_higher_salary(self, predictor):
        base = dict(job_title="Developer", experience_years=3.0, location=MOSCOW)
        few = predictor.predict(PredictionRequest(**base, skills=["Python"]))
        many = predictor.predict(
            PredictionRequest(**base, skills=["Python", "Docker", "Kubernetes", "AWS"])
        )
        assert many.p50_salary > few.p50_salary

    def test_shap_values_present(self, predictor):
        req = PredictionRequest(
            job_title="Dev",
            experience_years=3.0,
            skills=["Python", "Docker"],
            location=MOSCOW,
            education_level="master",
        )
        result = predictor.predict(req)
        assert "experience_years" in result.shap_values
        assert "skills:Python" in result.shap_values
        assert "education:master" in result.shap_values

    def test_counterfactuals_generated(self, predictor):
        req = PredictionRequest(job_title="Dev", experience_years=3.0, skills=["Python"], location=MOSCOW)
        result = predictor.predict(req)
        assert 0 < len(result.counterfactuals) <= 3
        for counterfactual in result.counterfactuals:
            assert isinstance(counterfactual, Counterfactual)
            assert counterfactual.new_value.lower() != "python"

    def test_education_bonus(self, predictor):
        base = dict(job_title="Dev", experience_years=3.0, skills=["Python"], location=MOSCOW)
        none_edu = predictor.predict(PredictionRequest(**base, education_level="none"))
        phd = predictor.predict(PredictionRequest(**base, education_level="phd"))
        assert phd.p50_salary > none_edu.p50_salary

    def test_zero_experience_valid(self, predictor):
        req = PredictionRequest(job_title="Junior", experience_years=0, skills=["Python"], location=MOSCOW)
        result = predictor.predict(req)
        assert result.p50_salary > 0

    def test_analyze_contract_contains_valid_uuid_like_ids(self, predictor):
        payload = {
            "request_hash": "hash",
            "profile": {"experience_years": 3, "skills": ["Python"]},
            "segment": {"segment_key": "backend:python:moscow:middle", "segment_data_version": "v1"},
            "candidate_vacancies": [
                {
                    "id": str(uuid.uuid4()),
                    "title": "Python Developer",
                    "salary_min_net": 100000,
                    "salary_max_net": 150000,
                    "skills_required": ["Python", "Docker"],
                }
            ],
        }
        result = predictor.analyze(payload)
        assert result["request_hash"] == "hash"
        assert result["recommendations"]

    def test_analyze_uses_all_candidate_vacancies(self, predictor):
        vacancies = [
            {
                "id": str(uuid.uuid4()),
                "title": "Python Developer",
                "salary_min_net": 100000 + index * 10000,
                "salary_max_net": 150000 + index * 10000,
                "skills_required": ["Python", "Docker"],
            }
            for index in range(8)
        ]
        payload = {
            "request_hash": "hash",
            "profile": {"experience_years": 3, "skills": ["Python"]},
            "segment": {"segment_key": "backend:python:moscow:middle", "segment_data_version": "v1"},
            "candidate_vacancies": vacancies,
        }

        result = predictor.analyze(payload)

        assert result["market_sample"]["vacancies_used_for_estimation"] == len(vacancies)
        assert result["market_sample"]["used_vacancy_ids"] == [vacancy["id"] for vacancy in vacancies]
        assert result["market_sample"]["excluded_vacancies"] == []


def test_parse_json_object_accepts_fenced_model_output():
    result = _parse_json_object('```json\n{"request_hash": "hash"}\n```')
    assert result == {"request_hash": "hash"}


def test_location_multiplier_handles_mojibake_moscow():
    assert _location_multiplier(MOSCOW) > _location_multiplier(KAZAN)


def test_decode_mojibake_repairs_utf8_read_as_cp1251():
    assert _decode_mojibake(MOSCOW) == "Москва"


def test_vacancy_count_phrase_uses_russian_plural_forms():
    assert _vacancy_count_phrase(1) == "в 1 вакансии"
    assert _vacancy_count_phrase(3) == "в 3 вакансиях"
    assert _vacancy_count_phrase(12) == "в 12 вакансиях"


def test_parse_json_object_extracts_json_from_extra_text():
    result = _parse_json_object('Answer:\n{"request_hash": "hash", "ok": true}')
    assert result == {"request_hash": "hash", "ok": True}


def test_compact_vacancy_keeps_deterministic_field_order():
    compact = _compact_vacancy(
        {
            "title": "Python Developer",
            "id": "v1",
            "salary_max_net": 200000,
            "salary_min_net": 150000,
            "skills_required": ["Python", "FastAPI"],
            "source": "fixture",
            "description": "long text that is intentionally not sent to the local runner",
            "source_url": "https://example.test/v1",
        }
    )

    assert list(compact) == ["id", "title", "salary_min_net", "salary_max_net", "skills_required"]
    assert "description" not in compact
    assert "source_url" not in compact
    assert "source" not in compact


def test_compact_model_payload_removes_nonessential_ollama_context():
    payload = {
        "request_hash": "hash",
        "profile": {
            "title": "Python Backend Developer",
            "experience_years": 3,
            "location": "Moscow",
            "skills": ["Python", "FastAPI"],
            "resume_text": "x" * 1000,
        },
        "segment": {
            "segment_key": "backend_developer:python:moscow:middle",
            "segment_data_version": "v1",
            "last_successful_update_at": "2026-05-17T16:17:39Z",
        },
        "candidate_vacancies": [
            {
                "id": "v1",
                "segment_key": "backend_developer:python:moscow:middle",
                "title": "Python Developer",
                "description": "long description",
                "salary_min_net": 180000,
                "salary_max_net": 260000,
                "location": "Moscow",
                "skills_required": ["Python", "FastAPI", "PostgreSQL", "Docker"],
                "source": "fixture",
                "source_url": "https://example.test/v1",
            }
        ],
        "market_evidence": {
            "target_segment_key": "backend_developer:python:moscow:middle",
            "candidate_segment_keys": ["backend_developer:python:moscow:middle"],
            "sample": {
                "total_vacancies": 1,
                "target_segment_vacancies": 1,
                "adjacent_segment_vacancies": 0,
                "used_vacancy_ids": ["v1"],
            },
            "salary_quantiles": {"p25": 180000, "p50": 220000, "p75": 260000},
            "resume_market_fit": {
                "matched_skills": ["Python"],
                "missing_skills": [
                    {
                        "skill": "Docker",
                        "vacancy_count": 1,
                        "vacancy_share": 1.0,
                        "median_salary_with_skill": 220000,
                        "estimated_monthly_uplift_in_sample": 20000,
                        "impact": "high",
                    }
                ],
                "coverage_score": 0.5,
            },
            "recommendation_candidates": [
                {
                    "priority": 1,
                    "type": "skill_gap",
                    "title": "Add Docker",
                    "resume_change": "Add honest Docker project evidence.",
                    "expected_salary_effect": "+20000 RUB",
                    "market_reason": "verbose reason",
                }
            ],
        },
        "rules": {"return_only_json": True},
    }

    compact = _compact_model_payload(payload)

    assert "rules" not in compact
    assert compact["profile"]["resume_text"] == "x" * 700
    assert compact["segment"] == {
        "segment_key": "backend_developer:python:moscow:middle",
        "segment_data_version": "v1",
    }
    assert "description" not in compact["candidate_vacancies"][0]
    assert "source_url" not in compact["candidate_vacancies"][0]
    assert "used_vacancy_ids" not in compact["market_evidence"]["sample"]
    assert "candidate_segment_keys" not in compact["market_evidence"]
    assert "market_reason" not in compact["market_evidence"]["recommendation_candidates"][0]


def test_ollama_messages_use_compact_default_prompt():
    messages = _messages({"request_hash": "hash"}, "", compact=True)

    assert messages[0]["content"] == COMPACT_ANALYZE_PROMPT
    assert len(messages[0]["content"]) < 1400


def test_ollama_generate_body_requests_json_and_disables_low_thinking():
    analyzer = OpenAICompatibleAnalyzer(
        base_url="http://ollama:11434/v1",
        api_key="",
        model_name="gpt-oss:20b",
        api_style="ollama",
        timeout=25,
        max_tokens=900,
        num_ctx=4096,
        temperature=0.1,
        reasoning_effort="low",
        json_mode=True,
        prompt_path="",
    )

    body = analyzer._ollama_generate_body({"request_hash": "hash", "candidate_vacancies": []})

    assert body["format"] == "json"
    assert body["think"] is False
    assert body["raw"] is True
    assert "prompt" in body
    assert "messages" not in body
    assert "Return only the compact JSON object" in body["prompt"]
    assert body["options"]["num_predict"] == 900


def test_ollama_think_value_keeps_explicit_higher_effort():
    assert _ollama_think_value("none") is False
    assert _ollama_think_value("low") is False
    assert _ollama_think_value("medium") == "medium"


def test_extract_ollama_message_content_accepts_generate_response():
    assert _extract_message_content({"response": '{"ok": true}'}, api_style="ollama") == '{"ok": true}'


def test_extract_ollama_message_content_can_recover_json_from_thinking():
    envelope = {"thinking": 'Need answer. Final JSON should be {"ok": true}.'}

    assert _extract_message_content(envelope, api_style="ollama") == '{"ok": true}'


def test_compact_prompt_asks_for_short_normalizable_json():
    assert "You only need to" in COMPACT_ANALYZE_PROMPT
    assert "Keep the JSON short" in COMPACT_ANALYZE_PROMPT
    assert "Backend will calculate" in COMPACT_ANALYZE_PROMPT


def test_normalize_analyze_output_repairs_common_llm_shape_drift():
    vacancy_id = str(uuid.uuid4())
    payload = {
        "request_hash": "hash",
        "profile": {"skills": ["Python"]},
        "segment": {"segment_key": "backend:python:moscow:middle", "segment_data_version": "v1"},
        "candidate_vacancies": [
            {
                "id": vacancy_id,
                "salary_min_net": 100000,
                "salary_max_net": 150000,
                "skills_required": ["Python", "Docker"],
            }
        ],
    }
    model_output = {
        "market_sample": {
            "used_vacancy_ids": [vacancy_id],
            "salary_quantiles": {"p25": 100000, "p50": 125000, "p75": 150000},
        },
        "salary_range": {"min": 100000, "median": 125000, "max": 150000},
        "confidence": {"score": 0.7, "level": "средняя"},
        "matched_skills": ["Python", "Django"],
        "missing_skills": ["Docker", "Kafka"],
        "factor_analysis": "Relevant backend profile.",
        "recommendations": ["Add Docker project evidence."],
    }

    result = _normalize_analyze_output(payload, model_output)

    assert result["segment"]["segment_key"] == payload["segment"]["segment_key"]
    assert result["confidence"]["level"] == "medium"
    assert result["matched_skills"] == ["Python"]
    assert result["missing_skills"][0]["skill"] == "Docker"
    assert isinstance(result["factor_analysis"][0], dict)
    assert isinstance(result["recommendations"][0], dict)


def test_normalize_analyze_output_converts_thousand_salary_units():
    vacancy_id = str(uuid.uuid4())
    payload = {
        "request_hash": "hash",
        "profile": {"skills": ["Python"]},
        "segment": {"segment_key": "backend:python:moscow:middle", "segment_data_version": "v1"},
        "candidate_vacancies": [
            {
                "id": vacancy_id,
                "salary_min_net": 180000,
                "salary_max_net": 260000,
                "skills_required": ["Python"],
            }
        ],
    }
    result = _normalize_analyze_output(
        payload,
        {
            "market_sample": {
                "used_vacancy_ids": [vacancy_id],
                "salary_quantiles": {"p25": 180, "p50": 220, "p75": 260},
            },
            "salary_range": {"min": 180, "median": 220, "max": 260},
        },
    )

    assert result["market_sample"]["salary_quantiles"] == {"p25": 220000, "p50": 220000, "p75": 220000}
    assert result["salary_range"] == {"min": 180000, "median": 220000, "max": 260000, "currency": "RUB"}


def test_normalize_analyze_output_expands_to_all_candidate_vacancies():
    vacancies = []
    for index in range(6):
        vacancies.append(
            {
                "id": str(uuid.uuid4()),
                "title": "Python Backend Developer",
                "salary_min_net": 150000 + index * 10000,
                "salary_max_net": 210000 + index * 10000,
                "skills_required": ["Python", "FastAPI"],
            }
        )
    payload = {
        "request_hash": "hash",
        "profile": {"title": "Python Backend Developer", "location": "Москва", "skills": ["Python"]},
        "segment": {"segment_key": "backend:python:moscow:middle", "segment_data_version": "v1"},
        "candidate_vacancies": vacancies,
    }

    result = _normalize_analyze_output(
        payload,
        {
            "market_sample": {
                "used_vacancy_ids": [vacancies[0]["id"]],
                "salary_quantiles": {"p25": 180000, "p50": 180000, "p75": 180000},
            },
            "salary_range": {"min": 180000, "median": 180000, "max": 180000},
        },
    )

    assert result["market_sample"]["vacancies_used_for_estimation"] == 6
    assert result["market_sample"]["excluded_vacancies"] == []


def test_normalize_analyze_output_fills_empty_skills_from_used_vacancies():
    vacancies = []
    for skills in [
        ["Python", "FastAPI", "Postgres", "Docker", "Kubernetes"],
        ["Python", "FastAPI", "Docker"],
        ["Python", "PostgreSQL", "Docker", "Kafka"],
    ]:
        vacancies.append(
            {
                "id": str(uuid.uuid4()),
                "title": "Python Backend Developer",
                "salary_min_net": 180000,
                "salary_max_net": 260000,
                "skills_required": skills,
            }
        )
    payload = {
        "request_hash": "hash",
        "profile": {"skills": ["Python", "FastAPI", "PostgreSQL"]},
        "segment": {"segment_key": "backend:python:moscow:middle", "segment_data_version": "v1"},
        "candidate_vacancies": vacancies,
    }

    result = _normalize_analyze_output(
        payload,
        {
            "market_sample": {"used_vacancy_ids": [vacancy["id"] for vacancy in vacancies]},
            "matched_skills": [],
            "missing_skills": [],
            "recommendations": [],
        },
    )

    assert result["matched_skills"] == ["Python", "FastAPI", "PostgreSQL"]
    missing_by_skill = {item["skill"]: item for item in result["missing_skills"]}
    assert missing_by_skill["Docker"]["impact"] == "high"
    assert "Kafka" in missing_by_skill
    assert result["recommendations"][0]["type"] == "skill_gap"
    assert "Docker" in result["recommendations"][0]["title"]


def test_fallback_analyze_output_is_valid_grounded_response():
    vacancy_id = str(uuid.uuid4())
    payload = {
        "request_hash": "hash",
        "profile": {"skills": ["Python"]},
        "segment": {"segment_key": "backend:python:moscow:middle", "segment_data_version": "v1"},
        "candidate_vacancies": [
            {
                "id": vacancy_id,
                "title": "Python Backend Developer",
                "salary_min_net": 180000,
                "salary_max_net": 260000,
                "skills_required": ["Python", "Docker"],
            }
        ],
    }

    result = _fallback_analyze_output(payload, reason="ollama response has no message content")

    assert result["request_hash"] == "hash"
    assert result["market_sample"]["used_vacancy_ids"] == [vacancy_id]
    assert result["salary_range"]["median"] == 220000
    assert result["matched_skills"] == ["Python"]
    assert result["missing_skills"][0]["skill"] == "Docker"
    assert "Модель вернула только thinking" in result["confidence"]["reason"]
    assert "ollama response" not in result["confidence"]["reason"]


def test_fallback_analyze_output_uses_market_evidence_recommendations():
    vacancy_id = str(uuid.uuid4())
    payload = {
        "request_hash": "hash",
        "profile": {"skills": ["Python"]},
        "segment": {"segment_key": "backend:python:moscow:middle", "segment_data_version": "v1"},
        "candidate_vacancies": [
            {
                "id": vacancy_id,
                "title": "Python Backend Developer",
                "salary_min_net": 180000,
                "salary_max_net": 260000,
                "skills_required": ["Python", "Kubernetes"],
            }
        ],
        "market_evidence": {
            "sample": {
                "total_vacancies": 1,
                "target_segment_vacancies": 1,
                "adjacent_segment_vacancies": 0,
            },
            "salary_quantiles": {"p25": 220000, "p50": 220000, "p75": 220000},
            "resume_market_fit": {
                "matched_skills": ["Python"],
                "coverage_score": 0.5,
                "missing_skills": [
                    {
                        "skill": "Kubernetes",
                        "impact": "high",
                        "vacancy_count": 1,
                        "estimated_monthly_uplift_in_sample": 30000,
                    }
                ],
            },
            "recommendation_candidates": [
                {
                    "priority": 1,
                    "type": "skill_gap",
                    "title": "Добавить подтверждение Kubernetes",
                    "resume_change": (
                        "Добавьте в резюме честный проектный пример с Kubernetes."
                    ),
                    "expected_salary_effect": "+30000 RUB к медиане выборки",
                }
            ],
        },
    }

    result = _fallback_analyze_output(payload, reason="timeout")

    assert result["salary_range"]["median"] == 220000
    assert "Таймаут вызова локальной модели" in result["confidence"]["reason"]
    assert result["missing_skills"][0]["skill"] == "Kubernetes"
    assert result["missing_skills"][0]["reason"] == (
        "Kubernetes встречается в 1 вакансии с +30000 RUB к медиане выборки."
    )
    factors = {item["factor"]: item for item in result["factor_analysis"]}
    assert factors["Рыночная выборка"]["impact"] == "neutral"
    assert factors["Пробел в навыках: Kubernetes"]["impact"] == "negative"
    assert result["recommendations"][0]["expected_salary_effect"] == "+30000 RUB к медиане выборки"


def test_normalize_replaces_generic_factors_with_market_evidence():
    vacancy_id = str(uuid.uuid4())
    payload = {
        "request_hash": "hash",
        "profile": {"skills": ["Python"]},
        "segment": {"segment_key": "backend:python:moscow:middle", "segment_data_version": "v1"},
        "candidate_vacancies": [
            {
                "id": vacancy_id,
                "title": "Python Backend Developer",
                "salary_min_net": 180000,
                "salary_max_net": 260000,
                "skills_required": ["Python", "Kafka"],
            }
        ],
        "market_evidence": {
            "sample": {
                "total_vacancies": 1,
                "target_segment_vacancies": 1,
                "adjacent_segment_vacancies": 0,
            },
            "resume_market_fit": {
                "matched_skills": ["Python"],
                "coverage_score": 0.5,
                "missing_skills": [
                    {
                        "skill": "Kafka",
                        "impact": "medium",
                        "vacancy_count": 1,
                        "estimated_monthly_uplift_in_sample": 15000,
                    }
                ],
            },
        },
    }

    result = _normalize_analyze_output(
        payload,
        {
            "market_sample": {"used_vacancy_ids": [vacancy_id]},
            "factor_analysis": [
                {
                    "factor": "Market and profile fit",
                    "impact": "neutral",
                    "explanation": "The model did not provide detailed factor analysis.",
                }
            ],
        },
    )

    factors = {item["factor"]: item for item in result["factor_analysis"]}
    assert "Рыночная выборка" in factors
    assert "Пробел в навыках: Kafka" in factors


def test_normalize_replaces_generic_recommendations_with_market_evidence():
    vacancy_id = str(uuid.uuid4())
    payload = {
        "request_hash": "hash",
        "profile": {"skills": ["Python"]},
        "segment": {"segment_key": "backend:python:moscow:middle", "segment_data_version": "v1"},
        "candidate_vacancies": [
            {
                "id": vacancy_id,
                "title": "Python Backend Developer",
                "salary_min_net": 180000,
                "salary_max_net": 260000,
                "skills_required": ["Python", "Docker"],
            }
        ],
        "market_evidence": {
            "recommendation_candidates": [
                {
                    "priority": 1,
                    "type": "skill_gap",
                    "title": "Добавить подтверждение Docker",
                    "resume_change": (
                        "Добавьте в резюме честный проектный пример с Docker."
                    ),
                    "expected_salary_effect": "+15000 RUB к медиане выборки",
                }
            ]
        },
    }

    result = _normalize_analyze_output(
        payload,
        {
            "market_sample": {"used_vacancy_ids": [vacancy_id]},
            "recommendations": [
                {
                    "priority": 1,
                    "type": "skill_gap",
                    "title": "Improve resume evidence",
                    "resume_change": "Add concrete, truthful project evidence.",
                }
            ],
        },
    )

    assert result["recommendations"][0]["title"] == "Добавить подтверждение Docker"
    assert result["recommendations"][0]["expected_salary_effect"] == "+15000 RUB к медиане выборки"
