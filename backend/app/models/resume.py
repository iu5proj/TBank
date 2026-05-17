"""Resume ORM model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.session import Base


def _resume_audit_join():
    from app.models.audit_log import AuditLogResume

    return Resume.id == foreign(AuditLogResume.resume_id)


class Resume(Base):
    """Current state of a user's resume used for salary estimation."""

    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    experience_years: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
    skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    education_level: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    experience_entries: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="resumes")
    estimates = relationship("SalaryEstimate", back_populates="resume", lazy="selectin")
    audit_logs = relationship(
        "AuditLogResume",
        back_populates="resume",
        lazy="noload",
        primaryjoin=_resume_audit_join,
    )
