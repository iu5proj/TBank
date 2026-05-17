"""Salary estimate ORM model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class SalaryEstimate(Base):
    """Cached ML prediction result — quantile salary range."""

    __tablename__ = "salary_estimates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    p25_salary: Mapped[int] = mapped_column(Integer, nullable=False)
    p50_salary: Mapped[int] = mapped_column(Integer, nullable=False)
    p75_salary: Mapped[int] = mapped_column(Integer, nullable=False)
    shap_values: Mapped[dict] = mapped_column(JSONB, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    resume = relationship("Resume", back_populates="estimates")
    recommendations = relationship("Recommendation", back_populates="estimate", lazy="selectin")
