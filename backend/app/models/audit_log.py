"""Audit log ORM model for resume change tracking."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.session import Base


def _audit_resume_join():
    from app.models.resume import Resume

    return foreign(AuditLogResume.resume_id) == Resume.id


class AuditLogResume(Base):
    """Immutable audit trail — captures every resume mutation via DB triggers."""

    __tablename__ = "audit_log_resumes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resume_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(10), nullable=False)
    old_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    changed_fields: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    resume = relationship(
        "Resume",
        back_populates="audit_logs",
        primaryjoin=_audit_resume_join,
    )
