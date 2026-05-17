from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
import time
from contextlib import AsyncExitStack
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from config import ParserSettings
from parsers import HHParser, HabrCareerParser, SuperJobParser, TrudvsemParser
from schemas import VacancyDatasetSchema


logger = logging.getLogger("parser")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect salary training dataset from Russian job platforms."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect and validate data without saving to DB.",
    )
    parser.add_argument(
        "--csv-output",
        type=str,
        default=None,
        help="Path to export collected data as CSV (always works, even with --dry-run).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Override max pages per source/search query.",
    )
    parser.add_argument(
        "--source",
        choices=["hh", "habr", "superjob", "trudvsem", "all"],
        default="all",
        help="Which source to parse: hh, habr, superjob, trudvsem, or all (default: all).",
    )
    parser.add_argument(
        "--skip-details",
        action="store_true",
        help="Skip fetching individual vacancy pages (faster, but less data per vacancy).",
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Search query. Can be passed multiple times. Defaults to built-in list.",
    )
    return parser


async def run(
    settings: ParserSettings,
    *,
    dry_run: bool = False,
    csv_output: str | None = None,
    source: str = "all",
) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    start_time = time.monotonic()

    # Build parsers based on --source flag
    parser_contexts = _build_parsers(settings, source)
    if not parser_contexts:
        logger.warning("No parsers to run (check --source flag and API keys)")
        return 0

    # Collect from all sources concurrently
    async with AsyncExitStack() as stack:
        parsers = [await stack.enter_async_context(p) for p in parser_contexts]
        results = await asyncio.gather(*(p.collect() for p in parsers), return_exceptions=True)

    # Merge results, log failures
    vacancies: list[VacancyDatasetSchema] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            parser_name = parser_contexts[i].source_name if i < len(parser_contexts) else "unknown"
            logger.exception("Parser '%s' failed", parser_name, exc_info=result)
            continue
        logger.info("Source '%s': collected %d vacancies",
                     parser_contexts[i].source_name, len(result))
        vacancies.extend(result)

    vacancies = _deduplicate_by_source_url(vacancies)
    elapsed = time.monotonic() - start_time

    # Print summary statistics
    _print_stats(vacancies, elapsed)

    # Export to CSV (always available, doesn't require DB)
    if csv_output:
        _export_csv(vacancies, csv_output)

    if dry_run:
        logger.info("Dry run — skipping DB save")
        return len(vacancies)

    # Save to PostgreSQL (only if DATABASE_URL is configured)
    if not settings.database_url:
        if csv_output:
            logger.info("No DATABASE_URL set — data saved to CSV only")
        else:
            logger.warning("No DATABASE_URL and no --csv-output. Data was collected but NOT saved!")
            logger.warning("Re-run with --csv-output <file.csv> or set DATABASE_URL in .env")
        return len(vacancies)

    try:
        from db import create_session_factory, save_vacancies, ensure_source_url_unique_index

        session_factory = create_session_factory(settings.database_url)

        # Ensure unique index exists (needed for upsert)
        async with session_factory() as session:
            await ensure_source_url_unique_index(session)

        # Save in batches to avoid losing everything on a crash
        total_saved = 0
        batch_size = settings.save_batch_size
        for i in range(0, len(vacancies), batch_size):
            batch = vacancies[i : i + batch_size]
            try:
                async with session_factory() as session:
                    saved = await save_vacancies(session, batch)
                    total_saved += saved
                    logger.info(
                        "Saved batch %d/%d (%d vacancies)",
                        i // batch_size + 1,
                        (len(vacancies) + batch_size - 1) // batch_size,
                        saved,
                    )
            except Exception:
                logger.exception("Failed to save batch starting at index %d", i)

        logger.info("Total saved/upserted: %d vacancies", total_saved)
        return total_saved
    except Exception:
        logger.exception("Database save failed — but CSV export (if any) succeeded")
        return len(vacancies)


def _build_parsers(settings: ParserSettings, source: str) -> list:
    """Build parser instances based on settings and source filter."""
    parsers = []

    if source in ("all", "hh"):
        parsers.append(
            HHParser(
                search_texts=settings.search_texts,
                areas=settings.hh_areas,
                per_page=settings.hh_per_page,
                max_pages=settings.max_pages,
                user_agent=settings.hh_user_agent,
                skip_details=settings.hh_skip_details,
                rate_limit_rps=settings.hh_rate_limit_rps,
                max_concurrency=settings.max_concurrency,
                timeout_seconds=settings.request_timeout_seconds,
                request_retries=settings.request_retries,
                currency_rates_to_rub=settings.currency_rates_to_rub,
            )
        )

    if source in ("all", "habr"):
        parsers.append(
            HabrCareerParser(
                search_texts=settings.search_texts,
                max_pages=settings.max_pages,
                user_agent=settings.habr_user_agent,
                rate_limit_rps=settings.habr_rate_limit_rps,
                max_concurrency=settings.max_concurrency,
                timeout_seconds=settings.request_timeout_seconds,
                request_retries=settings.request_retries,
                currency_rates_to_rub=settings.currency_rates_to_rub,
            )
        )

    if source in ("all", "superjob"):
        parsers.append(
            SuperJobParser(
                search_texts=settings.search_texts,
                app_id=settings.superjob_app_id,
                count=settings.superjob_count,
                max_pages=settings.max_pages,
                rate_limit_rps=settings.superjob_rate_limit_rps,
                max_concurrency=settings.max_concurrency,
                timeout_seconds=settings.request_timeout_seconds,
                request_retries=settings.request_retries,
                currency_rates_to_rub=settings.currency_rates_to_rub,
            )
        )

    if source in ("all", "trudvsem"):
        parsers.append(
            TrudvsemParser(
                regions=settings.trudvsem_regions,
                max_pages=settings.trudvsem_max_pages,
                rate_limit_rps=settings.trudvsem_rate_limit_rps,
                max_concurrency=settings.max_concurrency,
                timeout_seconds=settings.request_timeout_seconds,
                request_retries=settings.request_retries,
                currency_rates_to_rub=settings.currency_rates_to_rub,
            )
        )

    return parsers


def _deduplicate_by_source_url(vacancies: list[VacancyDatasetSchema]) -> list[VacancyDatasetSchema]:
    seen: set[str] = set()
    result: list[VacancyDatasetSchema] = []
    for vacancy in vacancies:
        if vacancy.source_url in seen:
            continue
        seen.add(vacancy.source_url)
        result.append(vacancy)
    return result


def _export_csv(vacancies: list[VacancyDatasetSchema], path: str) -> None:
    """Export dataset to CSV for direct use in ML training pipelines."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "title", "description", "salary_min_net", "salary_max_net",
                "skills_required", "location", "experience_range", "source_url",
            ],
        )
        writer.writeheader()
        for v in vacancies:
            row = v.model_dump()
            # Convert skills list to comma-separated string for CSV
            row["skills_required"] = ", ".join(row.get("skills_required") or [])
            writer.writerow(row)

    logger.info("Exported %d vacancies to %s", len(vacancies), output_path.resolve())


def _print_stats(vacancies: list[VacancyDatasetSchema], elapsed_seconds: float) -> None:
    """Print a summary of collected data."""
    if not vacancies:
        logger.warning("No vacancies collected!")
        return

    salaries = []
    for v in vacancies:
        if v.salary_min_net:
            salaries.append(v.salary_min_net)
        if v.salary_max_net:
            salaries.append(v.salary_max_net)

    locations: dict[str, int] = {}
    for v in vacancies:
        loc = v.location or "Не указан"
        locations[loc] = locations.get(loc, 0) + 1

    top_locations = sorted(locations.items(), key=lambda x: x[1], reverse=True)[:10]

    skills_count: dict[str, int] = {}
    for v in vacancies:
        for skill in v.skills_required:
            skills_count[skill] = skills_count.get(skill, 0) + 1
    top_skills = sorted(skills_count.items(), key=lambda x: x[1], reverse=True)[:15]

    # Count vacancies with salary ranges
    has_both = sum(1 for v in vacancies if v.salary_min_net and v.salary_max_net)
    has_min_only = sum(1 for v in vacancies if v.salary_min_net and not v.salary_max_net)
    has_max_only = sum(1 for v in vacancies if not v.salary_min_net and v.salary_max_net)
    has_skills = sum(1 for v in vacancies if v.skills_required)

    logger.info("=" * 60)
    logger.info("COLLECTION SUMMARY")
    logger.info("=" * 60)
    logger.info("Total unique vacancies: %d", len(vacancies))
    logger.info("Time elapsed: %.1f seconds (%.1f min)", elapsed_seconds, elapsed_seconds / 60)
    if salaries:
        logger.info("Salary range: %s — %s RUB", f"{min(salaries):,}", f"{max(salaries):,}")
        logger.info("Salary median: %s RUB", f"{sorted(salaries)[len(salaries) // 2]:,}")
    logger.info("With salary min+max: %d | min only: %d | max only: %d", has_both, has_min_only, has_max_only)
    logger.info("With skills extracted: %d / %d (%.0f%%)",
                has_skills, len(vacancies), has_skills / len(vacancies) * 100 if vacancies else 0)
    logger.info("Unique locations: %d", len(locations))
    logger.info("Top locations:")
    for loc, count in top_locations:
        logger.info("  %s: %d", loc, count)
    if top_skills:
        logger.info("Top skills:")
        for skill, count in top_skills:
            logger.info("  %s: %d", skill, count)
    logger.info("=" * 60)


def main() -> None:
    load_dotenv()
    args = build_arg_parser().parse_args()
    settings = ParserSettings.from_env()

    if args.max_pages is not None:
        settings = replace(settings, max_pages=args.max_pages)
    if args.skip_details:
        settings = replace(settings, hh_skip_details=True)
    if args.queries:
        search_texts = tuple(
            part.strip()
            for query in args.queries
            for part in query.split(",")
            if part.strip()
        )
        settings = replace(settings, search_texts=search_texts)

    # Default CSV output if none specified and no DB
    csv_output = args.csv_output
    if not csv_output and not settings.database_url and not args.dry_run:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        csv_output = f"dataset_{timestamp}.csv"
        logger.info("No DATABASE_URL set, will export to %s", csv_output)

    asyncio.run(run(settings, dry_run=args.dry_run, csv_output=csv_output, source=args.source))


if __name__ == "__main__":
    main()
