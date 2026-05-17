from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from schemas import VacancyDatasetSchema


metadata = MetaData()

vacancies_dataset = Table(
    "vacancies_dataset",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("title", String(500), nullable=False),
    Column("description", Text, nullable=False),
    Column("salary_min_net", Integer, nullable=True),
    Column("salary_max_net", Integer, nullable=True),
    Column("skills_required", JSONB, nullable=False),
    Column("location", String(1000), nullable=False),
    Column("experience_range", String(255), nullable=False),
    Column("source_url", String(1000), nullable=False, unique=True),
)

SOURCE_URL_UNIQUE_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_vacancies_dataset_source_url
ON vacancies_dataset (source_url)
"""


def create_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


async def save_vacancies(
    session: AsyncSession,
    vacancies: Sequence[VacancyDatasetSchema],
    *,
    commit: bool = True,
) -> int:
    """Upsert vacancies by source_url into vacancies_dataset."""

    if not vacancies:
        return 0

    rows = [
        {
            "id": uuid4(),
            **vacancy.model_dump(mode="json"),
        }
        for vacancy in vacancies
    ]

    stmt = insert(vacancies_dataset).values(rows)
    update_columns = {
        column.name: getattr(stmt.excluded, column.name)
        for column in vacancies_dataset.c
        if column.name not in {"id", "source_url"}
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=[vacancies_dataset.c.source_url],
        set_=update_columns,
    )

    result = await session.execute(stmt)
    if commit:
        await session.commit()
    return result.rowcount or 0


async def ensure_source_url_unique_index(session: AsyncSession, *, commit: bool = True) -> None:
    """Create the index required by PostgreSQL ON CONFLICT(source_url)."""

    await session.execute(text(SOURCE_URL_UNIQUE_INDEX_SQL))
    if commit:
        await session.commit()
