"""Segment-scoped vacancy refresh for the RAG candidate pool.

This module deliberately does not estimate salary ranges or relevance. It only
collects externally published vacancies for one segment_key, normalizes salary
fields to RUB net monthly where possible, and upserts rows for retrieval.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.market_segment import MarketSegment
from app.models.vacancy import Vacancy

logger = logging.getLogger(__name__)

GROSS_TO_NET_RU = 0.87
RUB_RATES: dict[str, float] = {
    "RUR": 1.0,
    "RUB": 1.0,
    "KZT": 0.17,
    "BYR": 28.0,
    "BYN": 28.0,
    "USD": 90.0,
    "EUR": 98.0,
}

KNOWN_SKILLS = (
    "python",
    "fastapi",
    "django",
    "flask",
    "sqlalchemy",
    "postgresql",
    "postgres",
    "redis",
    "kafka",
    "docker",
    "kubernetes",
    "git",
    "ci/cd",
    "rest",
    "graphql",
    "java",
    "spring",
    "go",
    "golang",
    "javascript",
    "typescript",
    "react",
    "vue",
    "angular",
    "node.js",
    "ml",
    "machine learning",
    "pytorch",
    "tensorflow",
    "pandas",
    "spark",
)


@dataclass(slots=True)
class SegmentQuery:
    segment_key: str
    role_cluster: str
    specialization: str
    region: str
    experience_bucket: str

    @property
    def search_text(self) -> str:
        role = self.role_cluster.replace("_", " ")
        specialization = "" if self.specialization == "general" else self.specialization
        return " ".join(part for part in (specialization, role) if part).strip()


@dataclass(slots=True)
class NormalizedVacancy:
    segment_key: str
    source: str
    source_vacancy_id: str
    source_url: str | None
    title: str
    description: str | None
    location: str | None
    salary_min_net: int | None
    salary_max_net: int | None
    salary_currency: str
    experience_range: str | None
    skills_required: list[str]
    published_at: datetime | None
    raw_payload: dict[str, Any]

    @property
    def usable_for_salary_sample(self) -> bool:
        return (
            self.salary_currency == "RUB"
            and self.salary_min_net is not None
            and self.salary_max_net is not None
            and self.salary_min_net > 0
            and self.salary_max_net > 0
        )


@dataclass(slots=True)
class SourceFetchReport:
    source: str
    status: str
    fetched_count: int = 0
    usable_count: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "status": self.status,
            "fetched_count": self.fetched_count,
            "usable_count": self.usable_count,
            "error": self.error,
        }


@dataclass(slots=True)
class SegmentRefreshReport:
    segment_key: str
    sources: list[SourceFetchReport]
    fetched_count: int
    usable_count: int
    vacancies_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_key": self.segment_key,
            "sources": [source.to_dict() for source in self.sources],
            "fetched_count": self.fetched_count,
            "usable_count": self.usable_count,
            "vacancies_count": self.vacancies_count,
        }


class SegmentRefreshError(RuntimeError):
    """Raised when a segment cannot be refreshed and no old data can be used."""

    def __init__(self, message: str, *, report: SegmentRefreshReport | None = None) -> None:
        super().__init__(message)
        self.report = report


async def refresh_segment_vacancies(
    db: AsyncSession,
    segment: MarketSegment,
    *,
    force_sources: list[str] | None = None,
) -> MarketSegment:
    """Refresh only the requested segment_key and update segment metadata."""
    segment, _ = await refresh_segment_vacancies_with_report(db, segment, force_sources=force_sources)
    return segment


async def refresh_segment_vacancies_with_report(
    db: AsyncSession,
    segment: MarketSegment,
    *,
    force_sources: list[str] | None = None,
) -> tuple[MarketSegment, SegmentRefreshReport]:
    """Refresh one segment and return source-level diagnostics for manual activation."""
    query = segment_query_from_segment(segment)
    raw, source_reports = await collect_segment_vacancies(query, force_sources=force_sources)

    normalized = [vacancy for vacancy in _deduplicate(raw) if vacancy.usable_for_salary_sample]
    if normalized:
        await _upsert_vacancies(db, normalized)

    count_result = await db.execute(select(func.count(Vacancy.id)).where(Vacancy.segment_key == segment.segment_key))
    vacancies_count = int(count_result.scalar_one() or 0)
    if normalized:
        now = datetime.now(timezone.utc)
        segment.last_successful_update_at = now
        segment.segment_data_version = now.isoformat(timespec="seconds")
        segment.vacancies_count = vacancies_count
    else:
        segment.vacancies_count = vacancies_count

    report = SegmentRefreshReport(
        segment_key=segment.segment_key,
        sources=source_reports,
        fetched_count=len(raw),
        usable_count=len(normalized),
        vacancies_count=segment.vacancies_count,
    )
    if len(normalized) < settings.MIN_REFRESHED_VACANCIES and segment.vacancies_count == 0:
        raise SegmentRefreshError(
            f"Not enough salary vacancies collected for segment {segment.segment_key}: "
            f"{len(normalized)} < {settings.MIN_REFRESHED_VACANCIES}",
            report=report,
        )
    logger.info(
        "segment refresh finished",
        extra={
            "segment_key": segment.segment_key,
            "sources": [source.to_dict() for source in source_reports],
            "collected": len(normalized),
            "vacancies_count": segment.vacancies_count,
        },
    )
    return segment, report


async def collect_segment_vacancies(
    query: SegmentQuery,
    *,
    force_sources: list[str] | None = None,
) -> tuple[list[NormalizedVacancy], list[SourceFetchReport]]:
    """Fetch one segment from enabled sources without persisting anything."""
    sources = force_sources or _enabled_sources()
    raw: list[NormalizedVacancy] = []
    reports: list[SourceFetchReport] = []
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.VACANCY_SOURCE_TIMEOUT),
        headers={"User-Agent": settings.PARSER_USER_AGENT},
        follow_redirects=True,
    ) as client:
        for source in sources:
            disabled_reason = _source_disabled_reason(source)
            if disabled_reason:
                reports.append(SourceFetchReport(source=source, status="skipped", error=disabled_reason))
                continue
            try:
                fetched = await _fetch_source(client, source, query)
            except Exception as exc:  # noqa: BLE001 - source failure must not break refresh
                logger.warning("vacancy source failed", extra={"source": source, "error": str(exc)})
                reports.append(SourceFetchReport(source=source, status="error", error=str(exc)))
                continue
            raw.extend(fetched)
            reports.append(
                SourceFetchReport(
                    source=source,
                    status="ok",
                    fetched_count=len(fetched),
                    usable_count=sum(1 for vacancy in fetched if vacancy.usable_for_salary_sample),
                )
            )
    return raw, reports


def segment_query_from_segment(segment: MarketSegment) -> SegmentQuery:
    return SegmentQuery(
        segment_key=segment.segment_key,
        role_cluster=segment.role_cluster or "",
        specialization=segment.specialization or "general",
        region=segment.region or "unknown_region",
        experience_bucket=segment.experience_bucket or "middle",
    )


async def _fetch_source(
    client: httpx.AsyncClient,
    source: str,
    query: SegmentQuery,
) -> list[NormalizedVacancy]:
    if source == "hh":
        return await _fetch_hh(client, query)
    if source == "trudvsem":
        return await _fetch_trudvsem(client, query)
    if source == "habr":
        return await _fetch_habr(client, query)
    if source == "fixture":
        return _fixture_vacancies(query) if settings.PARSER_ENABLE_FIXTURE_SOURCE else []
    logger.warning("unknown vacancy source ignored", extra={"source": source})
    return []


async def _fetch_hh(client: httpx.AsyncClient, query: SegmentQuery) -> list[NormalizedVacancy]:
    area = _hh_area(query.region)
    params: dict[str, Any] = {
        "text": query.search_text,
        "per_page": min(settings.VACANCY_SOURCE_LIMIT, 100),
        "page": 0,
        "only_with_salary": "true",
    }
    if area:
        params["area"] = area

    response = await client.get(f"{settings.HH_BASE_URL.rstrip('/')}/vacancies", params=params)
    response.raise_for_status()
    payload = response.json()
    items = payload.get("items", []) if isinstance(payload, dict) else []
    vacancies: list[NormalizedVacancy] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_hh_item(item, query)
        if normalized is not None:
            vacancies.append(normalized)
    return vacancies


async def _fetch_trudvsem(client: httpx.AsyncClient, query: SegmentQuery) -> list[NormalizedVacancy]:
    params: dict[str, Any] = {
        "text": query.search_text,
        "limit": min(settings.VACANCY_SOURCE_LIMIT, 100),
        "offset": 0,
    }
    region_code = _trudvsem_region(query.region)
    url = f"{settings.TRUDVSEM_BASE_URL.rstrip('/')}/vacancies"
    if region_code:
        url = f"{url}/region/{region_code}"

    response = await client.get(url, params=params)
    response.raise_for_status()
    payload = response.json()
    items = _trudvsem_items(payload)
    vacancies: list[NormalizedVacancy] = []
    for item in items:
        normalized = _normalize_trudvsem_item(item, query)
        if normalized is not None:
            vacancies.append(normalized)
    return vacancies


async def _fetch_habr(client: httpx.AsyncClient, query: SegmentQuery) -> list[NormalizedVacancy]:
    if not settings.HABR_CAREER_API_TOKEN:
        logger.info("habr source skipped: HABR_CAREER_API_TOKEN is not configured")
        return []

    # Habr Career API access is contractual. Keep this adapter conservative:
    # if the configured endpoint/token does not work, the source fails open.
    headers = {"Authorization": f"Bearer {settings.HABR_CAREER_API_TOKEN}"}
    response = await client.get(
        f"{settings.HABR_CAREER_BASE_URL.rstrip('/')}/api/v1/vacancies",
        params={"q": query.search_text, "per_page": settings.VACANCY_SOURCE_LIMIT},
        headers=headers,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("vacancies") or payload.get("items") or []
    if not isinstance(items, list):
        return []

    vacancies: list[NormalizedVacancy] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_habr_item(item, query)
        if normalized is not None:
            vacancies.append(normalized)
    return vacancies


def _normalize_hh_item(item: dict[str, Any], query: SegmentQuery) -> NormalizedVacancy | None:
    salary = item.get("salary") or {}
    salary_min, salary_max = _normalize_salary_range(
        salary.get("from"),
        salary.get("to"),
        currency=salary.get("currency"),
        gross=bool(salary.get("gross")),
    )
    title = _clean_text(item.get("name"))
    if not title:
        return None
    area = item.get("area") or {}
    published_at = _parse_datetime(item.get("published_at"))
    source_id = str(item.get("id") or _stable_source_id("hh", item))
    snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
    description = _clean_text(snippet.get("requirement"))
    return NormalizedVacancy(
        segment_key=query.segment_key,
        source="hh",
        source_vacancy_id=source_id,
        source_url=item.get("alternate_url") or item.get("url"),
        title=title,
        description=description,
        location=_normalize_location(area.get("name") or query.region),
        salary_min_net=salary_min,
        salary_max_net=salary_max,
        salary_currency="RUB",
        experience_range=(item.get("experience") or {}).get("name"),
        skills_required=_extract_skills(f"{title} {description}"),
        published_at=published_at,
        raw_payload=item,
    )


def _normalize_trudvsem_item(item: dict[str, Any], query: SegmentQuery) -> NormalizedVacancy | None:
    vacancy = item.get("vacancy") if isinstance(item.get("vacancy"), dict) else item
    title = _clean_text(vacancy.get("job-name") or vacancy.get("name") or vacancy.get("jobName"))
    if not title:
        return None

    company = vacancy.get("company") if isinstance(vacancy.get("company"), dict) else {}
    salary_min, salary_max = _normalize_salary_range(
        vacancy.get("salary_min") or vacancy.get("salaryMin") or vacancy.get("salary"),
        vacancy.get("salary_max") or vacancy.get("salaryMax") or vacancy.get("salary"),
        currency="RUB",
        gross=False,
    )
    description = _clean_text(
        vacancy.get("duty")
        or vacancy.get("requirement")
        or vacancy.get("description")
        or vacancy.get("responsibilities")
    )
    source_id = str(
        vacancy.get("id")
        or vacancy.get("vacancy_id")
        or vacancy.get("vacancyId")
        or _stable_source_id("trudvsem", vacancy)
    )
    source_url = vacancy.get("vac_url") or vacancy.get("url")
    if not source_url and company.get("companycode"):
        source_url = (
            f"https://trudvsem.ru/vacancy/card/{company.get('companycode')}/{source_id}"
        )
    return NormalizedVacancy(
        segment_key=query.segment_key,
        source="trudvsem",
        source_vacancy_id=source_id,
        source_url=source_url,
        title=title,
        description=description,
        location=_normalize_location(vacancy.get("regionName") or vacancy.get("address") or query.region),
        salary_min_net=salary_min,
        salary_max_net=salary_max,
        salary_currency="RUB",
        experience_range=_clean_text(
            vacancy.get("requirement", {}).get("experience")
            if isinstance(vacancy.get("requirement"), dict)
            else ""
        ),
        skills_required=_extract_skills(f"{title} {description}"),
        published_at=_parse_datetime(vacancy.get("creation-date") or vacancy.get("date_create")),
        raw_payload=vacancy,
    )


def _normalize_habr_item(item: dict[str, Any], query: SegmentQuery) -> NormalizedVacancy | None:
    title = _clean_text(item.get("title") or item.get("name"))
    if not title:
        return None

    salary = item.get("salary") if isinstance(item.get("salary"), dict) else item
    salary_min, salary_max = _normalize_salary_range(
        salary.get("from") or salary.get("salary_min"),
        salary.get("to") or salary.get("salary_max"),
        currency=salary.get("currency") or "RUB",
        gross=False,
    )
    description = _clean_text(item.get("description") or item.get("body"))
    source_id = str(item.get("id") or _stable_source_id("habr", item))
    return NormalizedVacancy(
        segment_key=query.segment_key,
        source="habr",
        source_vacancy_id=source_id,
        source_url=item.get("url") or item.get("html_url"),
        title=title,
        description=description,
        location=_normalize_location(item.get("location") or query.region),
        salary_min_net=salary_min,
        salary_max_net=salary_max,
        salary_currency="RUB",
        experience_range=_clean_text(item.get("experience") or ""),
        skills_required=_extract_skills(f"{title} {description}"),
        published_at=_parse_datetime(item.get("published_at") or item.get("created_at")),
        raw_payload=item,
    )


def _fixture_vacancies(query: SegmentQuery) -> list[NormalizedVacancy]:
    base = {
        "python": ("Python Backend Developer", ["Python", "FastAPI", "PostgreSQL", "Docker"]),
        "react": ("React Frontend Developer", ["React", "TypeScript", "Redux", "Docker"]),
        "java": ("Java Backend Developer", ["Java", "Spring", "PostgreSQL", "Kafka"]),
        "go": ("Go Backend Developer", ["Go", "PostgreSQL", "Kafka", "Kubernetes"]),
        "machine_learning": ("Machine Learning Engineer", ["Python", "PyTorch", "Pandas", "Docker"]),
    }
    title, skills = base.get(query.specialization, ("Software Developer", ["Git", "SQL", "Docker"]))
    if query.role_cluster == "frontend_developer":
        title, skills = base["react"]
    salaries = [(150_000, 210_000), (170_000, 240_000), (190_000, 270_000), (210_000, 300_000), (230_000, 330_000)]
    now = datetime.now(timezone.utc)
    return [
        NormalizedVacancy(
            segment_key=query.segment_key,
            source="fixture",
            source_vacancy_id=f"{query.segment_key}:{index}",
            source_url=f"https://example.test/{query.segment_key}/{index}",
            title=f"{title} #{index}",
            description=f"{title}. Production services, tests, observability and teamwork.",
            location=query.region,
            salary_min_net=salary_min,
            salary_max_net=salary_max,
            salary_currency="RUB",
            experience_range=query.experience_bucket,
            skills_required=skills,
            published_at=now,
            raw_payload={"fixture": True, "segment_key": query.segment_key},
        )
        for index, (salary_min, salary_max) in enumerate(salaries, start=1)
    ]


async def _upsert_vacancies(db: AsyncSession, vacancies: list[NormalizedVacancy]) -> None:
    rows = [
        {
            "id": uuid.uuid5(uuid.NAMESPACE_URL, f"zarabotok:{v.source}:{v.source_vacancy_id}"),
            "segment_key": v.segment_key,
            "source": v.source,
            "source_vacancy_id": v.source_vacancy_id,
            "source_url": v.source_url,
            "title": v.title,
            "description": v.description,
            "location": v.location,
            "salary_min_net": v.salary_min_net,
            "salary_max_net": v.salary_max_net,
            "salary_currency": v.salary_currency,
            "experience_range": v.experience_range,
            "skills_required": v.skills_required,
            "published_at": v.published_at,
            "parsed_at": datetime.now(timezone.utc),
            "raw_payload": v.raw_payload,
        }
        for v in vacancies
    ]
    stmt = insert(Vacancy).values(rows)
    update_columns = {
        column.name: getattr(stmt.excluded, column.name)
        for column in Vacancy.__table__.columns
        if column.name not in {"id", "source", "source_vacancy_id"}
    }
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=["source", "source_vacancy_id"],
            set_=update_columns,
        )
    )


def _enabled_sources() -> list[str]:
    return [source.strip().lower() for source in settings.VACANCY_SOURCES.split(",") if source.strip()]


def _source_disabled_reason(source: str) -> str | None:
    if source == "habr" and not settings.HABR_CAREER_API_TOKEN:
        return "HABR_CAREER_API_TOKEN is not configured"
    if source == "fixture" and not settings.PARSER_ENABLE_FIXTURE_SOURCE:
        return "PARSER_ENABLE_FIXTURE_SOURCE is disabled"
    return None


def _deduplicate(vacancies: list[NormalizedVacancy]) -> list[NormalizedVacancy]:
    seen: set[tuple[str, str]] = set()
    result: list[NormalizedVacancy] = []
    for vacancy in vacancies:
        marker = (vacancy.source, vacancy.source_vacancy_id)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(vacancy)
    return result


def _normalize_salary_range(
    salary_from: Any,
    salary_to: Any,
    *,
    currency: Any,
    gross: bool,
) -> tuple[int | None, int | None]:
    rate = RUB_RATES.get(str(currency or "RUB").upper())
    if rate is None:
        return None, None

    salary_min = _to_int(salary_from)
    salary_max = _to_int(salary_to)
    if salary_min is None and salary_max is None:
        return None, None
    if salary_min is None:
        salary_min = salary_max
    if salary_max is None:
        salary_max = salary_min
    assert salary_min is not None
    assert salary_max is not None
    if salary_min <= 0 or salary_max <= 0:
        return None, None

    multiplier = rate * (GROSS_TO_NET_RU if gross else 1.0)
    normalized_min = int(round(salary_min * multiplier))
    normalized_max = int(round(salary_max * multiplier))
    if normalized_min > normalized_max:
        normalized_min, normalized_max = normalized_max, normalized_min
    return normalized_min, normalized_max


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(" ", "").replace(",", ".")))
    except ValueError:
        return None


def _extract_skills(text: str) -> list[str]:
    lowered = text.casefold()
    result: list[str] = []
    for skill in KNOWN_SKILLS:
        if _contains_skill(lowered, skill) and skill not in result:
            result.append(skill)
    return result


def _contains_skill(text: str, skill: str) -> bool:
    escaped = re.escape(skill.casefold()).replace(r"\ ", r"\s+")
    pattern = rf"(?<![a-z0-9+#/.]){escaped}(?![a-z0-9+#/.])"
    return re.search(pattern, text) is not None


def _clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_location(value: Any) -> str:
    text = _clean_text(value).casefold()
    if "москва" in text or "moscow" in text or "РјРѕСЃРєРІР°" in text:
        return "moscow"
    if "петербург" in text or "spb" in text or "СЃР°РЅРєС‚" in text:
        return "saint_petersburg"
    if "удален" in text or "удалён" in text or "remote" in text:
        return "remote"
    slug = re.sub(r"[^a-z0-9а-яёР°-СЏС‘]+", "_", text).strip("_")
    return slug or "unknown_region"


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _stable_source_id(source: str, item: dict[str, Any]) -> str:
    raw = f"{source}:{item.get('url') or item.get('alternate_url') or item.get('name') or item}"
    return uuid.uuid5(uuid.NAMESPACE_URL, raw).hex


def _hh_area(region: str) -> str | None:
    return {
        "moscow": "1",
        "saint_petersburg": "2",
        "spb": "2",
        "remote": "113",
    }.get(region)


def _trudvsem_region(region: str) -> str | None:
    return {
        "moscow": "77",
        "saint_petersburg": "78",
        "spb": "78",
    }.get(region)


def _trudvsem_items(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    results = payload.get("results") or payload.get("vacancies") or {}
    if isinstance(results, dict):
        vacancies = results.get("vacancies") or results.get("vacancy") or []
    else:
        vacancies = results
    if isinstance(vacancies, dict):
        vacancies = [vacancies]
    return [item for item in vacancies if isinstance(item, dict)]
