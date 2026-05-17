"""Seed local test data for the GPT-OSS analyze flow."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert

from app.db.session import async_session_factory
from app.models.market_segment import MarketSegment
from app.models.vacancy import Vacancy

NOW = datetime.now(timezone.utc)
DATA_VERSION = NOW.date().isoformat()


def segment_rows() -> list[dict[str, Any]]:
    """Return deterministic market segments that match common demo profiles."""
    return [
        {
            "id": uuid.uuid5(uuid.NAMESPACE_URL, "zarabotok:test-segment:backend-python-moscow-middle"),
            "segment_key": "backend_developer:python:moscow:middle",
            "role_cluster": "backend_developer",
            "specialization": "python",
            "region": "moscow",
            "experience_bucket": "middle",
            "last_successful_update_at": NOW,
            "segment_data_version": DATA_VERSION,
            "vacancies_count": 8,
        },
        {
            "id": uuid.uuid5(uuid.NAMESPACE_URL, "zarabotok:test-segment:frontend-react-moscow-middle"),
            "segment_key": "frontend_developer:react:moscow:middle",
            "role_cluster": "frontend_developer",
            "specialization": "react",
            "region": "moscow",
            "experience_bucket": "middle",
            "last_successful_update_at": NOW,
            "segment_data_version": DATA_VERSION,
            "vacancies_count": 5,
        },
    ]


def vacancy_rows() -> list[dict[str, Any]]:
    """Return test vacancies with salary ranges and skills for model payloads."""
    return [
        *_backend_python_vacancies(),
        *_frontend_react_vacancies(),
    ]


async def seed() -> None:
    """Upsert test segments and vacancies."""
    async with async_session_factory() as session:
        await _upsert_segments(session, segment_rows())
        await _upsert_vacancies(session, vacancy_rows())
        await session.commit()


async def _upsert_segments(session, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    stmt = insert(MarketSegment).values(rows)
    update_columns = {
        column.name: getattr(stmt.excluded, column.name)
        for column in MarketSegment.__table__.columns
        if column.name not in {"id", "segment_key", "created_at"}
    }
    await session.execute(stmt.on_conflict_do_update(index_elements=["segment_key"], set_=update_columns))


async def _upsert_vacancies(session, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    stmt = insert(Vacancy).values(rows)
    update_columns = {
        column.name: getattr(stmt.excluded, column.name)
        for column in Vacancy.__table__.columns
        if column.name not in {"id", "source", "source_vacancy_id"}
    }
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["source", "source_vacancy_id"],
            set_=update_columns,
        )
    )


def _backend_python_vacancies() -> list[dict[str, Any]]:
    segment_key = "backend_developer:python:moscow:middle"
    specs = [
        (
            "py-back-001",
            "Python Backend Developer",
            170_000,
            230_000,
            ["Python", "FastAPI", "PostgreSQL", "Docker"],
        ),
        (
            "py-back-002",
            "Middle Python Developer",
            180_000,
            250_000,
            ["Python", "Django", "PostgreSQL", "Redis"],
        ),
        (
            "py-back-003",
            "Backend Engineer Python",
            190_000,
            270_000,
            ["Python", "FastAPI", "Kafka", "Docker"],
        ),
        (
            "py-back-004",
            "Python Developer, fintech platform",
            210_000,
            290_000,
            ["Python", "FastAPI", "PostgreSQL", "Kubernetes"],
        ),
        (
            "py-back-005",
            "Middle Backend Developer",
            160_000,
            220_000,
            ["Python", "SQLAlchemy", "PostgreSQL", "Docker"],
        ),
        (
            "py-back-006",
            "Python API Developer",
            150_000,
            210_000,
            ["Python", "FastAPI", "REST", "Git"],
        ),
        (
            "py-back-007",
            "Backend Developer Python/PostgreSQL",
            200_000,
            280_000,
            ["Python", "PostgreSQL", "Redis", "CI/CD"],
        ),
        (
            "py-back-008",
            "Python Backend Engineer",
            220_000,
            320_000,
            ["Python", "FastAPI", "Kubernetes", "Kafka"],
        ),
    ]
    return [
        _vacancy(
            segment_key=segment_key,
            source_vacancy_id=source_vacancy_id,
            title=title,
            description=f"{title}. Development of backend services, API, tests, and production support.",
            salary_min_net=salary_min,
            salary_max_net=salary_max,
            skills_required=skills,
            published_days_ago=index,
        )
        for index, (source_vacancy_id, title, salary_min, salary_max, skills) in enumerate(specs, start=1)
    ]


def _frontend_react_vacancies() -> list[dict[str, Any]]:
    segment_key = "frontend_developer:react:moscow:middle"
    specs = [
        ("react-front-001", "React Frontend Developer", 150_000, 220_000, ["React", "TypeScript", "Redux"]),
        ("react-front-002", "Middle Frontend Engineer", 170_000, 240_000, ["React", "TypeScript", "Vite"]),
        ("react-front-003", "Frontend Developer React", 160_000, 230_000, ["React", "JavaScript", "CSS"]),
        ("react-front-004", "React UI Developer", 180_000, 260_000, ["React", "TypeScript", "Testing Library"]),
        ("react-front-005", "Frontend Engineer", 190_000, 270_000, ["React", "Next.js", "TypeScript"]),
    ]
    return [
        _vacancy(
            segment_key=segment_key,
            source_vacancy_id=source_vacancy_id,
            title=title,
            description=f"{title}. Product frontend development and UI performance work.",
            salary_min_net=salary_min,
            salary_max_net=salary_max,
            skills_required=skills,
            published_days_ago=index,
        )
        for index, (source_vacancy_id, title, salary_min, salary_max, skills) in enumerate(specs, start=1)
    ]


def _vacancy(
    *,
    segment_key: str,
    source_vacancy_id: str,
    title: str,
    description: str,
    salary_min_net: int,
    salary_max_net: int,
    skills_required: list[str],
    published_days_ago: int,
) -> dict[str, Any]:
    return {
        "id": uuid.uuid5(uuid.NAMESPACE_URL, f"zarabotok:test-vacancy:{source_vacancy_id}"),
        "segment_key": segment_key,
        "source": "test_seed",
        "source_vacancy_id": source_vacancy_id,
        "source_url": f"https://example.test/vacancies/{source_vacancy_id}",
        "title": title,
        "description": description,
        "location": "Москва",
        "salary_min_net": salary_min_net,
        "salary_max_net": salary_max_net,
        "salary_currency": "RUB",
        "experience_range": "3-6",
        "skills_required": skills_required,
        "published_at": NOW - timedelta(days=published_days_ago),
        "parsed_at": NOW,
        "raw_payload": {"seed": True},
    }


def main() -> None:
    asyncio.run(seed())
    print(f"Seeded {len(segment_rows())} market segments and {len(vacancy_rows())} vacancies.")


if __name__ == "__main__":
    main()
