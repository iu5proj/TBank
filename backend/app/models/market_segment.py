"""Market segment state for freshness checks."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MarketSegment(Base):
    """Technical market segment used by preflight."""

    __tablename__ = "market_segments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    segment_key: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    role_cluster: Mapped[str | None] = mapped_column(String, nullable=True)
    specialization: Mapped[str | None] = mapped_column(String, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    experience_bucket: Mapped[str | None] = mapped_column(String, nullable=True)
    last_successful_update_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    segment_data_version: Mapped[str | None] = mapped_column(String, nullable=True)
    vacancies_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
