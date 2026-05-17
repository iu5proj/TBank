"""Dependency injection for FastAPI routes."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import async_session_factory

_analyze_hits: dict[str, deque[float]] = defaultdict(deque)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Yield a Redis connection."""
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def require_api_token(authorization: str | None = Header(default=None)) -> None:
    """Optional bearer-token guard.

    Empty API_AUTH_TOKEN keeps local/dev behavior unchanged. When configured,
    frontend/mobile clients must send Authorization: Bearer <token>.
    """
    if not settings.API_AUTH_TOKEN:
        return
    if authorization != f"Bearer {settings.API_AUTH_TOKEN}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "UNAUTHORIZED", "message": "Invalid bearer token."},
        )


async def analyze_rate_limit(request: Request) -> None:
    limit = settings.RATE_LIMIT_ANALYZE_PER_MINUTE
    if limit <= 0:
        return

    now = time.monotonic()
    client_host = request.client.host if request.client else "unknown"
    auth_suffix = request.headers.get("authorization", "")[-16:]
    key = f"{client_host}:{auth_suffix}"
    hits = _analyze_hits[key]
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"status": "error", "code": "RATE_LIMITED", "message": "Too many analyze requests."},
        )
    hits.append(now)
