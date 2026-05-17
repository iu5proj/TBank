"""Main salary analysis endpoint."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import analyze_rate_limit, get_db, get_redis, require_api_token
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.services.analyze import analyze_service

router = APIRouter(tags=["analyze"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze resume with one gpt-oss-20b call",
)
async def analyze_resume(
    data: AnalyzeRequest,
    _: None = Depends(require_api_token),
    __: None = Depends(analyze_rate_limit),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> AnalyzeResponse:
    """Run preflight, call the model once for a new request_hash, and return/cache the result."""
    return await analyze_service.analyze(db=db, request=data, redis=redis)
