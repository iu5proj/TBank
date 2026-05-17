"""Technical preflight for salary analysis requests."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.llm_salary_result import LlmSalaryResult
from app.models.market_segment import MarketSegment
from app.models.vacancy import Vacancy
from app.schemas.analyze import AnalyzeRequest, CandidateVacancy, GptOssInputPayload, ResumeProfile, SegmentPayload
from app.services.market_evidence import build_candidate_segment_keys, build_market_evidence, decode_mojibake
from app.services.parser import SegmentRefreshError, refresh_segment_vacancies

DEFAULT_CANDIDATE_LIMIT = 80


class NoCandidateVacanciesError(RuntimeError):
    """Raised when preflight cannot provide enough vacancies to the model."""


class SegmentRefreshFailedError(RuntimeError):
    """Raised when segment refresh failed and no acceptable stale data exists."""


@dataclass(slots=True)
class SegmentParts:
    role_cluster: str
    specialization: str
    region: str
    experience_bucket: str

    @property
    def segment_key(self) -> str:
        return ":".join((self.role_cluster, self.specialization, self.region, self.experience_bucket))


@dataclass(slots=True)
class PreflightResult:
    request_hash: str
    segment_key: str
    segment_data_version: str
    llm_input_payload: dict[str, Any] | None = None
    existing_result: LlmSalaryResult | None = None


def build_segment_key(profile: ResumeProfile) -> str:
    """Build the technical segment key; no salary analytics happen here."""
    return _segment_parts(profile).segment_key


def parse_segment_key(segment_key: str) -> SegmentParts:
    """Parse an existing technical segment key for manual parser activation."""
    parts = [part.strip() for part in segment_key.split(":")]
    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError("segment_key must have format role_cluster:specialization:region:experience_bucket")
    return SegmentParts(
        role_cluster=parts[0],
        specialization=parts[1],
        region=parts[2],
        experience_bucket=parts[3],
    )


async def get_or_create_segment(db: AsyncSession, parts: SegmentParts) -> MarketSegment:
    """Public wrapper used by preflight and manual parser activation."""
    return await _get_or_create_segment(db, parts)


def is_stale(last_successful_update_at: datetime | None, *, days: int | None = None) -> bool:
    if last_successful_update_at is None:
        return True
    updated_at = last_successful_update_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - updated_at
    return age.days >= (settings.SEGMENT_STALE_DAYS if days is None else days)


def calculate_request_hash(
    *,
    profile: ResumeProfile,
    segment_key: str,
    segment_data_version: str,
    model_version: str = settings.GPT_OSS_MODEL_VERSION,
    prompt_version: str = settings.GPT_OSS_PROMPT_VERSION,
) -> str:
    payload = {
        "profile": profile.model_dump(mode="json"),
        "segment_key": segment_key,
        "segment_data_version": segment_data_version,
        "model_version": model_version,
        "prompt_version": prompt_version,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def preflight_salary_request(db: AsyncSession, request: AnalyzeRequest) -> PreflightResult:
    """Prepare model input and enforce cache lookup before the model call."""
    profile = request.profile
    segment_parts = _segment_parts(profile)
    segment = await get_or_create_segment(db, segment_parts)

    if request.options.force_refresh or is_stale(segment.last_successful_update_at):
        try:
            segment = await refresh_segment_vacancies(db, segment)
        except SegmentRefreshError as exc:
            if segment.vacancies_count <= 0 or _too_stale_to_use(segment.last_successful_update_at):
                raise SegmentRefreshFailedError(str(exc)) from exc
        await db.flush()

    segment_data_version = segment.segment_data_version or datetime.now(timezone.utc).date().isoformat()
    request_hash = calculate_request_hash(
        profile=profile,
        segment_key=segment.segment_key,
        segment_data_version=segment_data_version,
    )

    existing_result = None
    if not request.options.force_refresh:
        existing_result = await find_llm_result_by_hash(db, request_hash)
        if existing_result is not None and existing_result.validation_status != "valid":
            existing_result = None
    if existing_result is not None:
        return PreflightResult(
            request_hash=request_hash,
            segment_key=segment.segment_key,
            segment_data_version=segment_data_version,
            existing_result=existing_result,
        )

    candidate_segment_keys = build_candidate_segment_keys(segment.segment_key)
    candidate_vacancies = await get_candidate_vacancies(
        db=db,
        segment_key=segment.segment_key,
        segment_keys=candidate_segment_keys,
        profile=profile,
        limit=DEFAULT_CANDIDATE_LIMIT,
    )
    if len(candidate_vacancies) < settings.MIN_CANDIDATE_VACANCIES:
        raise NoCandidateVacanciesError(
            f"Not enough candidate vacancies for segment {segment.segment_key}: "
            f"{len(candidate_vacancies)} < {settings.MIN_CANDIDATE_VACANCIES}"
        )

    payload = GptOssInputPayload(
        request_hash=request_hash,
        profile=profile.model_dump(mode="json"),
        segment=SegmentPayload(
            segment_key=segment.segment_key,
            segment_data_version=segment_data_version,
            last_successful_update_at=segment.last_successful_update_at,
        ),
        candidate_vacancies=candidate_vacancies,
        market_evidence=build_market_evidence(
            profile=profile,
            target_segment_key=segment.segment_key,
            candidate_segment_keys=candidate_segment_keys,
            candidate_vacancies=candidate_vacancies,
        ),
        rules={
            "use_only_candidate_vacancies": True,
            "do_not_use_external_salary_knowledge": True,
            "backend_precomputes_market_evidence": True,
            "market_evidence_is_precomputed": True,
            "model_must_use_market_evidence": True,
            "return_only_json": True,
        },
    )
    return PreflightResult(
        request_hash=request_hash,
        segment_key=segment.segment_key,
        segment_data_version=segment_data_version,
        llm_input_payload=payload.model_dump(mode="json"),
    )


async def find_llm_result_by_hash(db: AsyncSession, request_hash: str) -> LlmSalaryResult | None:
    result = await db.execute(select(LlmSalaryResult).where(LlmSalaryResult.request_hash == request_hash))
    return result.scalar_one_or_none()


async def get_candidate_vacancies(
    db: AsyncSession,
    segment_key: str,
    profile: ResumeProfile,
    limit: int,
    segment_keys: list[str] | None = None,
) -> list[CandidateVacancy]:
    """Return candidate vacancies without final relevance or salary analytics."""
    candidate_segment_keys = segment_keys or [segment_key]
    query = (
        select(Vacancy)
        .where(Vacancy.segment_key.in_(candidate_segment_keys))
        .where(Vacancy.salary_currency == "RUB")
        .where(and_(Vacancy.salary_min_net.is_not(None), Vacancy.salary_max_net.is_not(None)))
        .order_by(Vacancy.published_at.desc().nullslast(), Vacancy.parsed_at.desc().nullslast())
        .limit(max(limit, 1) * 3)
    )
    result = await db.execute(query)
    vacancies = list(result.scalars().all())
    ranked = sorted(vacancies, key=lambda vacancy: _retrieval_score(vacancy, profile), reverse=True)
    return [_vacancy_to_candidate(vacancy) for vacancy in ranked[:limit]]


async def _get_or_create_segment(db: AsyncSession, parts: SegmentParts) -> MarketSegment:
    result = await db.execute(select(MarketSegment).where(MarketSegment.segment_key == parts.segment_key))
    segment = result.scalar_one_or_none()
    if segment is not None:
        return segment

    segment = MarketSegment(
        segment_key=parts.segment_key,
        role_cluster=parts.role_cluster,
        specialization=parts.specialization,
        region=parts.region,
        experience_bucket=parts.experience_bucket,
    )
    db.add(segment)
    await db.flush()
    return segment


def _vacancy_to_candidate(vacancy: Vacancy) -> CandidateVacancy:
    assert vacancy.salary_min_net is not None
    assert vacancy.salary_max_net is not None
    return CandidateVacancy(
        id=str(vacancy.id),
        segment_key=vacancy.segment_key,
        title=vacancy.title,
        description=_truncate_description(vacancy.description),
        salary_min_net=vacancy.salary_min_net,
        salary_max_net=vacancy.salary_max_net,
        location=vacancy.location,
        experience_range=vacancy.experience_range,
        skills_required=vacancy.skills_required or [],
        source=vacancy.source,
        source_url=vacancy.source_url,
        published_at=vacancy.published_at,
    )


def _segment_parts(profile: ResumeProfile) -> SegmentParts:
    title = _profile_text(profile.title)
    skills = [_profile_text(skill) for skill in profile.skills]
    return SegmentParts(
        role_cluster=_role_cluster(title, skills),
        specialization=_specialization(title, skills),
        region=_region(profile.location),
        experience_bucket=_experience_bucket(profile.experience_years),
    )


def _profile_text(value: str) -> str:
    return decode_mojibake(value).casefold().strip()


def _role_cluster(title: str, skills: list[str]) -> str:
    text = " ".join([title, *skills])
    data_tokens = (
        "data",
        "ml",
        "machine learning",
        "\u0430\u043d\u0430\u043b\u0438\u0442\u0438\u043a",
        "\u0434\u0430\u043d\u043d",
    )
    if any(token in text for token in data_tokens):
        return "data_specialist"
    if any(token in text for token in ("backend", "back-end", "fastapi", "django", "python", "java", "go")):
        return "backend_developer"
    if any(token in text for token in ("frontend", "front-end", "react", "vue", "angular")):
        return "frontend_developer"
    if any(token in text for token in ("devops", "sre", "kubernetes", "terraform")):
        return "devops_engineer"
    return _slug(title, fallback="general_specialist")


def _specialization(title: str, skills: list[str]) -> str:
    text = " ".join([title, *skills])
    ordered = (
        "python",
        "java",
        "go",
        "javascript",
        "typescript",
        "react",
        "devops",
        "data",
        "ml",
        "postgresql",
    )
    for token in ordered:
        if token in text:
            return "machine_learning" if token == "ml" else token
    return _slug(skills[0] if skills else title, fallback="general")


def _region(location: str) -> str:
    normalized = decode_mojibake(location).casefold().strip()
    if normalized in {"moscow", "москва"}:
        return "moscow"
    if normalized in {"spb", "спб", "saint petersburg", "saint-petersburg"}:
        return "saint_petersburg"
    if "петербург" in normalized:
        return "saint_petersburg"
    if normalized in {"remote", "удаленно", "удалённо"}:
        return "remote"
    mapping = {
        "москва": "moscow",
        "РјРѕСЃРєРІР°": "moscow",
        "moscow": "moscow",
        "санкт-петербург": "saint_petersburg",
        "санкт петербург": "saint_petersburg",
        "спб": "saint_petersburg",
        "СЃР°РЅРєС‚-РїРµС‚РµСЂР±СѓСЂРі": "saint_petersburg",
        "СЃР°РЅРєС‚ РїРµС‚РµСЂР±СѓСЂРі": "saint_petersburg",
        "spb": "saint_petersburg",
        "remote": "remote",
        "удаленно": "remote",
        "удалённо": "remote",
        "СѓРґР°Р»РµРЅРЅРѕ": "remote",
        "СѓРґР°Р»С‘РЅРЅРѕ": "remote",
    }
    return mapping.get(normalized, _slug(normalized, fallback="unknown_region"))


def _experience_bucket(experience_years: float) -> str:
    if experience_years < 2:
        return "junior"
    if experience_years < 5:
        return "middle"
    return "senior"


def _slug(value: str, *, fallback: str) -> str:
    value = value.casefold().strip()
    value = re.sub(r"[^a-z0-9а-яёР°-СЏС‘]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or fallback


def _too_stale_to_use(last_successful_update_at: datetime | None) -> bool:
    if last_successful_update_at is None:
        return True
    return is_stale(last_successful_update_at, days=settings.MAX_STALE_SEGMENT_DAYS)


def _retrieval_score(vacancy: Vacancy, profile: ResumeProfile) -> tuple[int, float, float]:
    query_terms = set(_tokenize(" ".join([profile.title, *profile.skills, profile.resume_text or ""])))
    vacancy_text = " ".join([vacancy.title, vacancy.description or "", " ".join(vacancy.skills_required or [])])
    vacancy_terms = set(_tokenize(vacancy_text))
    keyword_score = len(query_terms & vacancy_terms)
    skill_overlap = len(
        {skill.casefold() for skill in profile.skills}
        & {skill.casefold() for skill in vacancy.skills_required or []}
    )
    freshness = vacancy.published_at.timestamp() if vacancy.published_at else 0.0
    return (skill_overlap, float(keyword_score), freshness)


def _tokenize(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9а-яёР°-СЏС‘+#/.-]+", value.casefold()) if len(token) >= 2]


def _truncate_description(description: str | None, *, limit: int = 1200) -> str | None:
    if description is None or len(description) <= limit:
        return description
    return f"{description[:limit].rstrip()}..."
