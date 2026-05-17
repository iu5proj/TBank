"""Manual vacancy parser activation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_api_token
from app.schemas.parser import ParserRefreshRequest, ParserRefreshResponse, ParserSourceReport
from app.services.parser import (
    SegmentQuery,
    SegmentRefreshError,
    collect_segment_vacancies,
    refresh_segment_vacancies_with_report,
)
from app.services.preflight import build_segment_key, get_or_create_segment, parse_segment_key

router = APIRouter(prefix="/parser", tags=["parser"])


@router.post(
    "/refresh",
    response_model=ParserRefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh one vacancy segment without running salary analysis",
)
async def refresh_parser_segment(
    data: ParserRefreshRequest,
    _: None = Depends(require_api_token),
    db: AsyncSession = Depends(get_db),
) -> ParserRefreshResponse:
    """Start parser early for one segment; existing /analyze behavior is unchanged."""
    segment_key = build_segment_key(data.profile) if data.profile is not None else str(data.segment_key)
    parts = parse_segment_key(segment_key)
    sources = _normalize_sources(data.sources)

    if data.dry_run:
        query = SegmentQuery(
            segment_key=parts.segment_key,
            role_cluster=parts.role_cluster,
            specialization=parts.specialization,
            region=parts.region,
            experience_bucket=parts.experience_bucket,
        )
        raw, report = await collect_segment_vacancies(query, force_sources=sources)
        usable_count = sum(1 for vacancy in raw if vacancy.usable_for_salary_sample)
        return ParserRefreshResponse(
            status="success",
            dry_run=True,
            segment_key=parts.segment_key,
            fetched_count=len(raw),
            usable_count=usable_count,
            sources=[ParserSourceReport.model_validate(source.to_dict()) for source in report],
            message="Parser dry-run completed; vacancies were not persisted.",
        )

    segment = await get_or_create_segment(db, parts)
    try:
        segment, report = await refresh_segment_vacancies_with_report(db, segment, force_sources=sources)
    except SegmentRefreshError as exc:
        report = exc.report
        return ParserRefreshResponse(
            status="error",
            dry_run=False,
            segment_key=segment.segment_key,
            segment_data_version=segment.segment_data_version,
            last_successful_update_at=segment.last_successful_update_at,
            vacancies_count=segment.vacancies_count,
            fetched_count=report.fetched_count if report else 0,
            usable_count=report.usable_count if report else 0,
            sources=[ParserSourceReport.model_validate(source.to_dict()) for source in report.sources]
            if report
            else [],
            message=str(exc),
        )

    return ParserRefreshResponse(
        status="success",
        dry_run=False,
        segment_key=segment.segment_key,
        segment_data_version=segment.segment_data_version,
        last_successful_update_at=segment.last_successful_update_at,
        vacancies_count=segment.vacancies_count,
        fetched_count=report.fetched_count,
        usable_count=report.usable_count,
        sources=[ParserSourceReport.model_validate(source.to_dict()) for source in report.sources],
        message="Parser refresh completed and vacancies were persisted.",
    )


def _normalize_sources(sources: list[str] | None) -> list[str] | None:
    if sources is None:
        return None
    return [source.strip().lower() for source in sources if source.strip()]
