from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from base import BaseParser
from schemas import VacancyDatasetSchema
from utils import clean_text, extract_skills_from_text, normalize_salary_range, unique_strings


class HHParser(BaseParser):
    """Parser for hh.ru public API.

    Key strategy for maximizing volume:
    - Iterates over MULTIPLE area IDs (regions) for each search query.
      HH.ru caps results at 2000 per (query + area) combination,
      so splitting by region lets us collect far more than the 2000 global cap.
    - Fetches vacancy detail pages concurrently to extract key_skills and full descriptions.
    - Supports a 'skip_details' mode for fast bulk collection (skips detail fetches).
    """

    source_name = "hh"
    search_url = "https://api.hh.ru/vacancies"

    def __init__(
        self,
        *,
        search_texts: Sequence[str],
        areas: Sequence[str] = ("113",),
        per_page: int = 100,
        max_pages: int = 20,
        user_agent: str,
        skip_details: bool = False,
        currency_rates_to_rub: Mapping[str, float] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json",
            },
            **kwargs,
        )
        self.search_texts = tuple(search_texts)
        self.areas = tuple(areas)
        self.per_page = max(1, min(per_page, 100))
        self.max_pages = max(1, min(max_pages, 20))  # HH.ru hard limit is 20 pages
        self.skip_details = skip_details
        self.currency_rates_to_rub = dict(currency_rates_to_rub or {})

    async def fetch_vacancies(self) -> list[dict[str, Any]]:
        """Fetch vacancy stubs from HH.ru across all search texts × areas.

        Includes a circuit breaker: if 30 consecutive requests return no data
        (likely an IP ban or API block), we stop early to avoid wasting time.
        """
        all_items: list[dict[str, Any]] = []
        consecutive_failures = 0
        max_consecutive_failures = 30  # ~2 queries × 15 areas = quick detection

        for search_text in self.search_texts:
            if consecutive_failures >= max_consecutive_failures:
                self.logger.warning(
                    "HH.ru: circuit breaker triggered after %d consecutive failures. "
                    "Likely IP-banned. Stopping HH collection.",
                    consecutive_failures,
                )
                break

            for area in self.areas:
                if consecutive_failures >= max_consecutive_failures:
                    break

                try:
                    area_items = await self._fetch_all_pages_for(search_text, area)
                    if area_items:
                        all_items.extend(area_items)
                        consecutive_failures = 0  # Reset on success
                    else:
                        consecutive_failures += 1
                except Exception:
                    consecutive_failures += 1
                    self.logger.exception(
                        "Failed to fetch HH vacancies for query=%r area=%s", search_text, area
                    )

        unique = self.deduplicate_by(all_items, "id")
        self.logger.info(
            "HH.ru: fetched %d raw items (%d unique) across %d queries × %d areas",
            len(all_items), len(unique), len(self.search_texts), len(self.areas),
        )
        return unique

    async def _fetch_all_pages_for(self, text: str, area: str) -> list[dict[str, Any]]:
        """Paginate through all available pages for a single (query, area) pair."""
        first_page = await self._fetch_page(text, area, 0)
        if not first_page:
            return []

        items = list(first_page.get("items", []))
        total_pages = min(int(first_page.get("pages") or 1), self.max_pages)
        found = first_page.get("found", 0)

        if total_pages <= 1:
            self.logger.debug("HH q=%r area=%s: %d found, 1 page", text, area, found)
            return items

        self.logger.debug("HH q=%r area=%s: %d found, fetching %d pages", text, area, found, total_pages)

        # Fetch remaining pages sequentially to respect rate limits better
        for page in range(1, total_pages):
            page_data = await self._fetch_page(text, area, page)
            if page_data:
                page_items = page_data.get("items", [])
                if not page_items:
                    break
                items.extend(page_items)

        return items

    async def parse_vacancy(self, raw_vacancy: dict[str, Any]) -> dict[str, Any] | None:
        """Fetch detail page for a vacancy to get key_skills and full description."""
        # Check if salary is present in the stub
        salary = raw_vacancy.get("salary")
        if not salary:
            return None

        detail = raw_vacancy
        if not self.skip_details:
            detail_url = raw_vacancy.get("url")
            if detail_url:
                fetched = await self._request_json(detail_url)
                if isinstance(fetched, dict):
                    detail = fetched

        # Extract key_skills from detail page (not available in search results)
        key_skills = [
            skill.get("name")
            for skill in detail.get("key_skills", [])
            if isinstance(skill, dict) and skill.get("name")
        ]

        description = clean_text(detail.get("description"))
        title = clean_text(detail.get("name") or raw_vacancy.get("name"))
        source_url = (
            detail.get("alternate_url")
            or raw_vacancy.get("alternate_url")
            or raw_vacancy.get("url")
        )
        if not title or not source_url:
            return None

        # Prefer explicit key_skills, fall back to NLP extraction from description
        skills = unique_strings(key_skills) or extract_skills_from_text(f"{title} {description}")

        area = detail.get("area") or raw_vacancy.get("area") or {}
        experience = detail.get("experience") or raw_vacancy.get("experience") or {}
        salary = detail.get("salary") or salary

        return {
            "title": title,
            "description": description,
            "salary_from": salary.get("from"),
            "salary_to": salary.get("to"),
            "salary_gross": bool(salary.get("gross")),
            "currency": salary.get("currency"),
            "skills_required": skills,
            "location": area.get("name", ""),
            "experience_range": experience.get("name", ""),
            "source_url": source_url,
        }

    def normalize_data(self, parsed_vacancy: dict[str, Any]) -> VacancyDatasetSchema | None:
        salary_min_net, salary_max_net = normalize_salary_range(
            parsed_vacancy.get("salary_from"),
            parsed_vacancy.get("salary_to"),
            gross=bool(parsed_vacancy.get("salary_gross")),
            currency=parsed_vacancy.get("currency"),
            currency_rates_to_rub=self.currency_rates_to_rub,
        )
        if salary_min_net is None and salary_max_net is None:
            return None

        return VacancyDatasetSchema(
            title=parsed_vacancy["title"],
            description=parsed_vacancy.get("description") or "",
            salary_min_net=salary_min_net,
            salary_max_net=salary_max_net,
            skills_required=parsed_vacancy.get("skills_required") or [],
            location=parsed_vacancy.get("location") or "",
            experience_range=parsed_vacancy.get("experience_range") or "",
            source_url=parsed_vacancy["source_url"],
        )

    async def _fetch_page(self, text: str, area: str, page: int) -> dict[str, Any] | None:
        params = {
            "text": text,
            "area": area,
            "page": page,
            "per_page": self.per_page,
            "only_with_salary": "true",
        }
        data = await self._request_json(self.search_url, params=params)
        return data if isinstance(data, dict) else None
