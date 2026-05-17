"""Resume CRUD API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import ResumeCreate, ResumeResponse, ResumeUpdate

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post(
    "",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new resume",
)
async def create_resume(
    data: ResumeCreate,
    db: AsyncSession = Depends(get_db),
) -> Resume:
    """Create a new resume. Auto-creates an anonymous user if needed."""
    # For MVP: create anonymous user
    user = User(id=uuid.uuid4(), email=f"anon-{uuid.uuid4().hex[:8]}@zarabotok.local")
    db.add(user)
    await db.flush()

    resume = Resume(
        id=uuid.uuid4(),
        user_id=user.id,
        job_title=data.job_title,
        experience_years=data.experience_years,
        skills=data.skills,
        location=data.location,
        education_level=data.education_level,
        experience_entries=[e.model_dump() for e in data.experience_entries],
    )
    db.add(resume)
    await db.flush()
    await db.refresh(resume)
    return resume


@router.get(
    "/{resume_id}",
    response_model=ResumeResponse,
    summary="Get resume by ID",
)
async def get_resume(
    resume_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Resume:
    """Retrieve a single resume by its UUID."""
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.patch(
    "/{resume_id}",
    response_model=ResumeResponse,
    summary="Update resume (partial)",
)
async def update_resume(
    resume_id: uuid.UUID,
    data: ResumeUpdate,
    db: AsyncSession = Depends(get_db),
) -> Resume:
    """Partially update a resume. Triggers audit log via DB trigger."""
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    update_data = data.model_dump(exclude_unset=True)
    if "experience_entries" in update_data and update_data["experience_entries"] is not None:
        update_data["experience_entries"] = [
            e if isinstance(e, dict) else e.model_dump() for e in update_data["experience_entries"]
        ]

    for field, value in update_data.items():
        setattr(resume, field, value)

    await db.flush()
    await db.refresh(resume)
    return resume
