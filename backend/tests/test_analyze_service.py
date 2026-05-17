"""Tests for analyze orchestration and idempotency edges."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from redis.exceptions import RedisError

import app.services.analyze as analyze_module
from app.models.llm_salary_result import LlmSalaryResult
from app.schemas.analyze import AnalyzeRequest
from app.services.analyze import AnalyzeService
from app.services.gpt_oss_client import GptOssClientError
from app.services.preflight import PreflightResult


def _request(*, force_refresh: bool = False) -> AnalyzeRequest:
    return AnalyzeRequest(
        profile={
            "title": "Python Backend Developer",
            "experience_years": 3,
            "location": "Москва",
            "skills": ["Python", "FastAPI"],
        },
        options={"force_refresh": force_refresh},
    )


def _input_payload(request_hash: str = "hash") -> dict:
    return {
        "request_hash": request_hash,
        "profile": _request().profile.model_dump(mode="json"),
        "segment": {
            "segment_key": "backend_developer:python:moscow:middle",
            "segment_data_version": "2026-05-17",
        },
        "candidate_vacancies": [
            {
                "id": "v1",
                "title": "Python Backend Developer",
                "salary_min_net": 180000,
                "salary_max_net": 240000,
                "skills_required": ["Python", "FastAPI", "Docker"],
                "source": "fixture",
            }
        ],
        "rules": {"return_only_json": True},
    }


def _valid_output(request_hash: str = "hash") -> dict:
    return {
        "request_hash": request_hash,
        "segment": {
            "segment_key": "backend_developer:python:moscow:middle",
            "segment_data_version": "2026-05-17",
        },
        "market_sample": {
            "candidate_vacancies_received": 1,
            "vacancies_used_for_estimation": 1,
            "used_vacancy_ids": ["v1"],
            "excluded_vacancies": [],
            "salary_quantiles": {"p25": 180000, "p50": 210000, "p75": 240000},
        },
        "salary_range": {"min": 180000, "median": 210000, "max": 240000, "currency": "RUB"},
        "confidence": {"score": 0.8, "level": "high", "reason": "Fixture sample."},
        "matched_skills": ["Python", "FastAPI"],
        "missing_skills": [{"skill": "Docker", "impact": "high", "reason": "Present in sample."}],
        "factor_analysis": [{"factor": "Experience", "impact": "positive", "explanation": "Middle level."}],
        "recommendations": [
            {
                "priority": 1,
                "type": "skill_gap",
                "title": "Add Docker evidence",
                "resume_change": "Add Docker only if there is real project experience.",
            }
        ],
    }


def _cached_result(request_hash: str = "hash", *, validation_status: str = "valid") -> LlmSalaryResult:
    payload = _input_payload(request_hash)
    return LlmSalaryResult(
        request_hash=request_hash,
        profile_snapshot=payload["profile"],
        segment_key=payload["segment"]["segment_key"],
        segment_data_version=payload["segment"]["segment_data_version"],
        model_name="gpt-oss-20b",
        model_version="gpt-oss-20b-salary-v1",
        prompt_version="salary_estimation_prompt_v13",
        input_payload=payload,
        output_payload=_valid_output(request_hash) if validation_status == "valid" else {"error": "old failed run"},
        validation_status=validation_status,
        validation_errors=None if validation_status == "valid" else ["old failed run"],
    )


@pytest.mark.asyncio
async def test_force_refresh_does_not_recall_same_request_hash(monkeypatch, mock_db):
    preflight = PreflightResult(
        request_hash="hash",
        segment_key="backend_developer:python:moscow:middle",
        segment_data_version="2026-05-17",
        llm_input_payload=_input_payload("hash"),
    )
    monkeypatch.setattr(analyze_module, "preflight_salary_request", AsyncMock(return_value=preflight))
    monkeypatch.setattr(analyze_module, "find_llm_result_by_hash", AsyncMock(return_value=_cached_result("hash")))
    generate_once = AsyncMock()
    monkeypatch.setattr(analyze_module.gpt_oss_client, "generate_once", generate_once)

    response = await AnalyzeService().analyze(db=mock_db, request=_request(force_refresh=True), redis=None)

    assert response.status == "success"
    assert response.source == "cache"
    generate_once.assert_not_called()


@pytest.mark.asyncio
async def test_failed_cached_result_can_be_replaced(monkeypatch, mock_db):
    preflight = PreflightResult(
        request_hash="hash",
        segment_key="backend_developer:python:moscow:middle",
        segment_data_version="2026-05-17",
        llm_input_payload=_input_payload("hash"),
    )
    service = AnalyzeService()
    save_result = AsyncMock()
    monkeypatch.setattr(service, "_save_result", save_result)
    monkeypatch.setattr(analyze_module, "preflight_salary_request", AsyncMock(return_value=preflight))
    monkeypatch.setattr(
        analyze_module,
        "find_llm_result_by_hash",
        AsyncMock(return_value=_cached_result("hash", validation_status="failed")),
    )
    generate_once = AsyncMock(return_value=_valid_output("hash"))
    monkeypatch.setattr(analyze_module.gpt_oss_client, "generate_once", generate_once)

    response = await service.analyze(db=mock_db, request=_request(), redis=None)

    assert response.status == "success"
    assert response.source == "gpt-oss-20b"
    generate_once.assert_awaited_once()
    save_result.assert_awaited_once()


@pytest.mark.asyncio
async def test_model_client_error_returns_grounded_fallback(monkeypatch, mock_db):
    preflight = PreflightResult(
        request_hash="hash",
        segment_key="backend_developer:python:moscow:middle",
        segment_data_version="2026-05-17",
        llm_input_payload=_input_payload("hash"),
    )
    service = AnalyzeService()
    save_result = AsyncMock()
    monkeypatch.setattr(service, "_save_result", save_result)
    monkeypatch.setattr(analyze_module, "preflight_salary_request", AsyncMock(return_value=preflight))
    monkeypatch.setattr(analyze_module, "find_llm_result_by_hash", AsyncMock(return_value=None))
    monkeypatch.setattr(
        analyze_module.gpt_oss_client,
        "generate_once",
        AsyncMock(side_effect=GptOssClientError("model returned invalid JSON content")),
    )

    response = await service.analyze(db=mock_db, request=_request(), redis=None)

    assert response.status == "success"
    assert response.source == "grounded-fallback"
    assert response.data is not None
    assert response.data.request_hash == "hash"
    assert response.data.recommendations
    save_result.assert_awaited_once()
    assert save_result.await_args.kwargs["validation_status"] == "valid"


@pytest.mark.asyncio
async def test_invalid_model_payload_returns_grounded_fallback(monkeypatch, mock_db):
    preflight = PreflightResult(
        request_hash="hash",
        segment_key="backend_developer:python:moscow:middle",
        segment_data_version="2026-05-17",
        llm_input_payload=_input_payload("hash"),
    )
    service = AnalyzeService()
    save_result = AsyncMock()
    monkeypatch.setattr(service, "_save_result", save_result)
    monkeypatch.setattr(analyze_module, "preflight_salary_request", AsyncMock(return_value=preflight))
    monkeypatch.setattr(analyze_module, "find_llm_result_by_hash", AsyncMock(return_value=None))
    generate_once = AsyncMock(return_value={"request_hash": "wrong-shape"})
    monkeypatch.setattr(analyze_module.gpt_oss_client, "generate_once", generate_once)

    response = await service.analyze(db=mock_db, request=_request(), redis=None)

    assert response.status == "success"
    assert response.source == "grounded-fallback"
    assert response.data is not None
    assert response.data.salary_range.median == 210000
    assert response.data.missing_skills[0].skill == "Docker"
    save_result.assert_awaited_once()
    assert save_result.await_args.kwargs["validation_status"] == "valid"


@pytest.mark.asyncio
async def test_save_result_updates_failed_existing_row(mock_db):
    existing = _cached_result("hash", validation_status="failed")
    mock_db.scalar = AsyncMock(return_value=existing)

    await AnalyzeService()._save_result(
        db=mock_db,
        request=_request(),
        input_payload=_input_payload("hash"),
        output_payload=_valid_output("hash"),
        validation_status="valid",
        validation_errors=[],
    )

    assert existing.validation_status == "valid"
    assert existing.output_payload["request_hash"] == "hash"
    mock_db.add.assert_not_called()
    mock_db.flush.assert_awaited_once()
    mock_db.commit.assert_awaited_once()


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool | None:
        if nx and key in self.values:
            return None
        self.values[key] = value
        return True

    async def eval(self, script: str, numkeys: int, key: str, token: str) -> int:
        if self.values.get(key) == token:
            del self.values[key]
            return 1
        return 0


@pytest.mark.asyncio
async def test_lock_release_does_not_delete_another_owner_token():
    service = AnalyzeService()
    redis = _FakeRedis()

    assert await service._acquire_lock(redis, "lock-key", "owner-a")
    await service._release_lock(redis, "lock-key", "owner-b", lock_acquired=True)
    assert redis.values["lock-key"] == "owner-a"

    await service._release_lock(redis, "lock-key", "owner-a", lock_acquired=True)
    assert "lock-key" not in redis.values


class _BrokenRedis:
    async def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
        raise RedisError("redis down")


@pytest.mark.asyncio
async def test_lock_unavailable_continues_without_redis(monkeypatch, mock_db):
    preflight = PreflightResult(
        request_hash="hash",
        segment_key="backend_developer:python:moscow:middle",
        segment_data_version="2026-05-17",
        llm_input_payload=_input_payload("hash"),
    )
    monkeypatch.setattr(analyze_module, "preflight_salary_request", AsyncMock(return_value=preflight))
    monkeypatch.setattr(analyze_module, "find_llm_result_by_hash", AsyncMock(return_value=None))
    generate_once = AsyncMock(return_value=_valid_output("hash"))
    monkeypatch.setattr(analyze_module.gpt_oss_client, "generate_once", generate_once)

    response = await AnalyzeService().analyze(db=mock_db, request=_request(), redis=_BrokenRedis())

    assert response.status == "success"
    assert response.source == "gpt-oss-20b"
    generate_once.assert_awaited_once()
