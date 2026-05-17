"""Resume history / audit trail API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.audit_log import AuditLogResume
from app.models.estimate import SalaryEstimate
from app.schemas.estimate import EstimateHistoryItem

router = APIRouter(prefix="/history", tags=["history"])


@router.get(
    "/resume/{resume_id}",
    response_model=list[EstimateHistoryItem],
    summary="Get salary evolution history for a resume",
)
async def get_resume_history(
    resume_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[EstimateHistoryItem]:
    """Return timeline of salary estimates showing how changes affected predictions.

    This powers the frontend chart:
    "Step 1: 100k → Step 2 (added Python): 130k → Step 3 (added Docker): 145k"
    """
    # Get all estimates for this resume
    estimates_result = await db.execute(
        select(SalaryEstimate).where(SalaryEstimate.resume_id == resume_id).order_by(SalaryEstimate.calculated_at.asc())
    )
    estimates = estimates_result.scalars().all()

    # Get audit logs for change context
    audit_result = await db.execute(
        select(AuditLogResume).where(AuditLogResume.resume_id == resume_id).order_by(AuditLogResume.performed_at.asc())
    )
    audits = audit_result.scalars().all()

    history: list[EstimateHistoryItem] = []
    for est in estimates:
        # Find closest audit entry for this estimate
        changed = []
        skills_snapshot = []
        for audit in audits:
            if audit.performed_at <= est.calculated_at:
                if audit.changed_fields:
                    changed = [f.strip() for f in audit.changed_fields.split(",")]
                if audit.new_data and "skills" in audit.new_data:
                    skills_snapshot = audit.new_data["skills"]

        history.append(
            EstimateHistoryItem(
                estimate_id=est.id,
                p25=est.p25_salary,
                p50=est.p50_salary,
                p75=est.p75_salary,
                skills_snapshot=skills_snapshot,
                changed_fields=changed,
                calculated_at=est.calculated_at,
            )
        )

    return history
