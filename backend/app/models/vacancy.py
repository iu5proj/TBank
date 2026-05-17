"""Vacancy ORM model used by RAG retrieval."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Vacancy(Base):
    """Normalized market vacancy from external sources."""

    __tablename__ = "vacancies"
    __table_args__ = (
        UniqueConstraint("source", "source_vacancy_id", name="uq_vacancies_source_source_vacancy_id"),
        Index("ix_vacancies_published_at", "published_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    segment_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_vacancy_id: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    salary_min_net: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max_net: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="RUB")
    experience_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    skills_required: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parsed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
