"""Aggregating router for API v1."""

from fastapi import APIRouter

from app.api.v1.analyze import router as analyze_router
from app.api.v1.parser import router as parser_router
from app.api.v1.resumes import router as resumes_router

router = APIRouter(prefix="/api/v1")

router.include_router(analyze_router)
router.include_router(parser_router)
router.include_router(resumes_router)
