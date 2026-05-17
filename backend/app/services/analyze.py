"""Analyze pipeline that matches the GPT-OSS technical specification."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis
from pydantic import ValidationError
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.llm_salary_result import LlmSalaryResult
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse, GptOssSalaryResult
from app.services.gpt_oss_client import GptOssClientError, gpt_oss_client
from app.services.grounded_fallback import build_grounded_fallback_output
from app.services.market_evidence import canonical_skill_key
from app.services.preflight import (
    NoCandidateVacanciesError,
    SegmentRefreshFailedError,
    find_llm_result_by_hash,
    preflight_salary_request,
)

logger = logging.getLogger(__name__)

_RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


@dataclass(slots=True)
class OutputValidation:
    status: str
    output: GptOssSalaryResult | None
    raw_output: dict[str, Any]
    errors: list[str]


class AnalyzeService:
    """Orchestrates preflight, one model call, validation, and persistence."""

    async def analyze(
        self,
        *,
        db: AsyncSession,
        request: AnalyzeRequest,
        redis: aioredis.Redis | None = None,
    ) -> AnalyzeResponse:
        try:
            preflight = await preflight_salary_request(db, request)
        except NoCandidateVacanciesError as exc:
            return AnalyzeResponse(
                status="error",
                code="NO_CANDIDATE_VACANCIES",
                message=str(exc),
            )
        except SegmentRefreshFailedError as exc:
            return AnalyzeResponse(
                status="error",
                code="SEGMENT_REFRESH_FAILED",
                message=str(exc),
            )

        if preflight.existing_result is not None:
            return self._response_from_cached(preflight.existing_result)

        assert preflight.llm_input_payload is not None
        lock_key = f"llm_salary_request:{preflight.request_hash}"
        lock_token = uuid.uuid4().hex
        try:
            lock_acquired = await self._acquire_lock(redis, lock_key, lock_token)
        except RedisError as exc:
            logger.warning(
                "Could not acquire idempotency lock for request_hash=%s; continuing without Redis lock: %s",
                preflight.request_hash,
                exc,
            )
            redis = None
            lock_acquired = True
        if not lock_acquired:
            existing = await find_llm_result_by_hash(db, preflight.request_hash)
            if existing is not None and existing.validation_status == "valid":
                return self._response_from_cached(existing)
            return AnalyzeResponse(
                status="error",
                code="DUPLICATE_REQUEST",
                message="A request with the same request_hash is already being processed.",
            )

        fallback_source = False
        validation_errors_for_storage: list[str] = []
        try:
            existing = await find_llm_result_by_hash(db, preflight.request_hash)
            if existing is not None and existing.validation_status == "valid":
                return self._response_from_cached(existing)

            model_started_at = time.monotonic()
            logger.info(
                "Calling GPT-OSS for request_hash=%s segment=%s candidates=%d",
                preflight.request_hash,
                preflight.segment_key,
                len(preflight.llm_input_payload.get("candidate_vacancies") or []),
            )
            raw_output = await gpt_oss_client.generate_once(preflight.llm_input_payload)
            logger.info(
                "GPT-OSS returned for request_hash=%s in %.1fs",
                preflight.request_hash,
                time.monotonic() - model_started_at,
            )
            validation = validate_gpt_oss_output(raw_output, preflight.llm_input_payload)
            if validation.status != "valid" or validation.output is None:
                fallback_source = True
                validation_errors_for_storage = validation.errors
                logger.warning(
                    "GPT-OSS output invalid for request_hash=%s; using grounded fallback: %s",
                    preflight.request_hash,
                    validation.errors,
                )
                validation = self._grounded_fallback_validation(
                    preflight.llm_input_payload,
                    reason="; ".join(validation.errors) or "model output did not match schema",
                )
            output_payload = validation.output.model_dump(mode="json") if validation.output else validation.raw_output
            await self._save_result(
                db=db,
                request=request,
                input_payload=preflight.llm_input_payload,
                output_payload=output_payload,
                validation_status=validation.status,
                validation_errors=validation_errors_for_storage or validation.errors,
            )
        except GptOssClientError as exc:
            fallback_source = True
            logger.warning(
                "GPT-OSS call failed for request_hash=%s; using grounded fallback: %s",
                preflight.request_hash,
                exc,
            )
            validation = self._grounded_fallback_validation(preflight.llm_input_payload, reason=str(exc))
            output_payload = validation.output.model_dump(mode="json") if validation.output else validation.raw_output
            await self._save_result(
                db=db,
                request=request,
                input_payload=preflight.llm_input_payload,
                output_payload=output_payload,
                validation_status=validation.status,
                validation_errors=[str(exc)] + validation.errors,
            )
        finally:
            await self._release_lock(redis, lock_key, lock_token, lock_acquired=lock_acquired)

        if validation.status != "valid" or validation.output is None:
            return AnalyzeResponse(
                status="error",
                code="LLM_OUTPUT_VALIDATION_FAILED",
                message="The model returned a payload that does not match the expected schema.",
                validation_errors=validation.errors,
            )

        source = "grounded-fallback" if fallback_source else "gpt-oss-20b"
        return AnalyzeResponse(status="success", source=source, data=validation.output)

    def _grounded_fallback_validation(self, input_payload: dict[str, Any], *, reason: str) -> OutputValidation:
        raw_output = build_grounded_fallback_output(input_payload, reason=reason)
        validation = validate_gpt_oss_output(raw_output, input_payload)
        if validation.status != "valid":
            logger.error(
                "Grounded fallback failed validation for request_hash=%s: %s",
                input_payload.get("request_hash"),
                validation.errors,
            )
        return validation

    def _response_from_cached(self, result: LlmSalaryResult) -> AnalyzeResponse:
        if result.validation_status != "valid" or not result.output_payload:
            return AnalyzeResponse(
                status="error",
                source="cache",
                code="LLM_OUTPUT_VALIDATION_FAILED",
                message="Cached model output is invalid.",
                validation_errors=result.validation_errors or [],
            )

        try:
            output = GptOssSalaryResult.model_validate(result.output_payload)
        except ValidationError as exc:
            return AnalyzeResponse(
                status="error",
                source="cache",
                code="LLM_OUTPUT_VALIDATION_FAILED",
                message="Cached model output no longer matches the response schema.",
                validation_errors=[str(error) for error in exc.errors()],
            )

        return AnalyzeResponse(status="success", source="cache", data=output)

    async def _save_result(
        self,
        *,
        db: AsyncSession,
        request: AnalyzeRequest,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
        validation_status: str,
        validation_errors: list[str],
    ) -> None:
        segment = input_payload["segment"]
        existing = await db.scalar(
            select(LlmSalaryResult).where(LlmSalaryResult.request_hash == input_payload["request_hash"])
        )
        values = {
            "profile_snapshot": request.profile.model_dump(mode="json"),
            "segment_key": segment["segment_key"],
            "segment_data_version": segment["segment_data_version"],
            "model_name": settings.GPT_OSS_MODEL_NAME,
            "model_version": settings.GPT_OSS_MODEL_VERSION,
            "prompt_version": settings.GPT_OSS_PROMPT_VERSION,
            "input_payload": input_payload,
            "output_payload": output_payload,
            "validation_status": validation_status,
            "validation_errors": validation_errors or None,
        }
        if existing is None:
            result = LlmSalaryResult(request_hash=input_payload["request_hash"], **values)
            db.add(result)
        elif existing.validation_status != "valid":
            logger.info(
                "Replacing failed cached result for request_hash=%s",
                input_payload["request_hash"],
            )
            for field, value in values.items():
                setattr(existing, field, value)
        else:
            logger.warning(
                "Result for request_hash=%s already exists; preserving first saved payload",
                input_payload["request_hash"],
            )
            return
        await db.flush()
        # Commit before releasing the Redis lock so another worker can see the
        # saved request_hash and will not make a second model call.
        await db.commit()

    async def _acquire_lock(self, redis: aioredis.Redis | None, lock_key: str, lock_token: str) -> bool:
        if redis is None:
            return True
        acquired = await redis.set(lock_key, lock_token, nx=True, ex=settings.LLM_LOCK_TTL_SECONDS)
        return bool(acquired)

    async def _release_lock(
        self,
        redis: aioredis.Redis | None,
        lock_key: str,
        lock_token: str,
        *,
        lock_acquired: bool,
    ) -> None:
        if redis is None or not lock_acquired:
            return
        try:
            await redis.eval(_RELEASE_LOCK_SCRIPT, 1, lock_key, lock_token)
        except RedisError:
            logger.warning("Could not release idempotency lock safely", exc_info=True, extra={"lock_key": lock_key})


def validate_gpt_oss_output(raw_output: dict[str, Any], input_payload: dict[str, Any]) -> OutputValidation:
    errors: list[str] = []
    try:
        output = GptOssSalaryResult.model_validate(raw_output)
    except ValidationError as exc:
        return OutputValidation(
            status="failed",
            output=None,
            raw_output=raw_output,
            errors=[f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()],
        )

    if output.request_hash != input_payload["request_hash"]:
        errors.append("request_hash does not match input payload")

    input_segment = input_payload["segment"]
    if output.segment.segment_key != input_segment["segment_key"]:
        errors.append("segment.segment_key does not match input payload")
    if output.segment.segment_data_version != input_segment["segment_data_version"]:
        errors.append("segment.segment_data_version does not match input payload")

    market_sample = output.market_sample
    if market_sample.vacancies_used_for_estimation > market_sample.candidate_vacancies_received:
        errors.append("vacancies_used_for_estimation exceeds candidate_vacancies_received")

    input_vacancies = input_payload["candidate_vacancies"]
    input_vacancy_ids = {str(vacancy["id"]) for vacancy in input_vacancies}
    if market_sample.vacancies_used_for_estimation != len(market_sample.used_vacancy_ids):
        errors.append("vacancies_used_for_estimation does not match used_vacancy_ids length")
    if len(set(market_sample.used_vacancy_ids)) != len(market_sample.used_vacancy_ids):
        errors.append("used_vacancy_ids must not contain duplicates")
    unknown_used_ids = [
        vacancy_id for vacancy_id in market_sample.used_vacancy_ids if vacancy_id not in input_vacancy_ids
    ]
    if unknown_used_ids:
        errors.append(f"used_vacancy_ids are not present in candidate_vacancies: {unknown_used_ids}")

    unknown_excluded_ids = [
        item.id for item in market_sample.excluded_vacancies if item.id not in input_vacancy_ids
    ]
    if unknown_excluded_ids:
        errors.append(f"excluded_vacancies ids are not present in candidate_vacancies: {unknown_excluded_ids}")

    if market_sample.candidate_vacancies_received != len(input_vacancies):
        errors.append("candidate_vacancies_received does not match input candidate_vacancies length")

    profile_skills = {canonical_skill_key(skill) for skill in input_payload["profile"].get("skills", [])}
    unknown_matched_skills = [
        skill for skill in output.matched_skills if canonical_skill_key(skill) not in profile_skills
    ]
    if unknown_matched_skills:
        errors.append(f"matched_skills are not present in profile.skills: {unknown_matched_skills}")

    candidate_skills = {
        canonical_skill_key(skill)
        for vacancy in input_payload["candidate_vacancies"]
        for skill in (vacancy.get("skills_required") or [])
    }
    unknown_missing_skills = [
        item.skill for item in output.missing_skills if canonical_skill_key(item.skill) not in candidate_skills
    ]
    if unknown_missing_skills:
        errors.append(f"missing_skills are not grounded in candidate_vacancies: {unknown_missing_skills}")

    return OutputValidation(
        status="valid" if not errors else "failed",
        output=output,
        raw_output=raw_output,
        errors=errors,
    )


analyze_service = AnalyzeService()
