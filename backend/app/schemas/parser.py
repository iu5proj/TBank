"""Schemas for manual vacancy parser activation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.analyze import ResumeProfile


class ParserRefreshRequest(BaseModel):
    """Manual parser refresh request.

    Use either a profile, which will be converted to a segment_key, or an
    already known segment_key. The regular /analyze force_refresh path remains
    unchanged; this schema is for parser-only refreshes.
    """

    profile: ResumeProfile | None = None
    segment_key: str | None = Field(default=None, min_length=3, max_length=240)
    sources: list[str] | None = None
    dry_run: bool = False

    @model_validator(mode="after")
    def validate_target(self) -> "ParserRefreshRequest":
        if bool(self.profile) == bool(self.segment_key):
            raise ValueError("Provide exactly one of profile or segment_key")
        return self


class ParserSourceReport(BaseModel):
    source: str
    status: Literal["ok", "error", "skipped"]
    fetched_count: int = Field(default=0, ge=0)
    usable_count: int = Field(default=0, ge=0)
    error: str | None = None


class ParserRefreshResponse(BaseModel):
    status: Literal["success", "error"]
    dry_run: bool = False
    segment_key: str
    segment_data_version: str | None = None
    last_successful_update_at: datetime | None = None
    vacancies_count: int = Field(default=0, ge=0)
    fetched_count: int = Field(default=0, ge=0)
    usable_count: int = Field(default=0, ge=0)
    sources: list[ParserSourceReport] = Field(default_factory=list)
    message: str | None = None
