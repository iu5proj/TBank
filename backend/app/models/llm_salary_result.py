"""Persisted GPT-OSS salary results."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LlmSalaryResult(Base):
    """One saved model response for one unique request_hash."""

    __tablename__ = "llm_salary_results"
    __table_args__ = (
        Index("ix_llm_salary_results_segment_version", "segment_key", "segment_data_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    profile_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    segment_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    segment_data_version: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_status: Mapped[str] = mapped_column(String, nullable=False)
    validation_errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
