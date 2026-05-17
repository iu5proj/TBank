from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from base import BaseParser
from schemas import VacancyDatasetSchema
from utils import (
    NO_SALARY_RE,
    clean_text,
    extract_experience_level,
    extract_skills_from_text,
    normalize_salary_range,
    parse_salary_text,
    unique_strings,
)


class HabrCareerParser(BaseParser):
    """Parser for career.habr.com via HTML scraping.

    Habr Career doesn't have a public API, so we scrape search result pages
    and individual vacancy pages. Key considerations:
    - Very aggressive rate limiting (0.5 rps recommended)
    - Uses a real browser User-Agent to avoid blocks
    - Fetches pages SEQUENTIALLY per search query to avoid triggering anti-bot
    - Falls back gracefully if page structure changes
    """

    source_name = "habr_career"
    base_url = "https://career.habr.com"
    vacancies_url = f"{base_url}/vacancies"

    def __init__(
        self,
        *,
        search_texts: Sequence[str],
        max_pages: int = 10,
        user_agent: str,
        currency_rates_to_rub: Mapping[str, float] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            **kwargs,
        )
        self.search_texts = tuple(search_texts)
        self.max_pages = max(1, max_pages)
        self.currency_rates_to_rub = dict(currency_rates_to_rub or {})

    async def fetch_vacancies(self) -> list[dict[str, Any]]:
        """Fetch vacancy cards from search result pages.

        Pages are fetched SEQUENTIALLY per query to mimic human browsing
        and avoid Habr's anti-bot detection. We stop paginating early
        if a page returns no cards (end of results).
        """
        raw_items: list[dict[str, Any]] = []

        for search_text in self.search_texts:
            for page in range(1, self.max_pages + 1):
                page_html = await self._fetch_search_page(search_text, page)
                if not page_html:
                    break

                cards = self._extract_cards(page_html)
                if not cards:
                    self.logger.debug("Habr: no cards on page %d for q=%r, stopping", page, search_text)
                    break

                raw_items.extend(cards)
                self.logger.debug("Habr: %d cards from page %d for q=%r", len(cards), page, search_text)

        unique = self.deduplicate_by(raw_items, "source_url")
        self.logger.info("Habr Career: fetched %d unique vacancy cards", len(unique))
        return unique

    async def parse_vacancy(self, raw_vacancy: dict[str, Any]) -> dict[str, Any] | None:
        source_url = raw_vacancy.get("source_url")
        if not source_url:
            return None

        # Fetch detail page for richer data
        detail_html = await self._request_text(source_url)
        detail = self._parse_detail_page(detail_html, raw_vacancy) if detail_html else raw_vacancy

        salary_from, salary_to, salary_gross, currency = parse_salary_text(detail.get("salary_text", ""))
        if salary_from is None and salary_to is None:
            return None

        description = clean_text(detail.get("description") or raw_vacancy.get("description"))
        title = clean_text(detail.get("title") or raw_vacancy.get("title"))
        if not title:
            return None

        explicit_skills = detail.get("skills_required") or raw_vacancy.get("skills_required") or []
        skills = unique_strings(explicit_skills) or extract_skills_from_text(f"{title} {description}")
        experience = clean_text(detail.get("experience_range")) or extract_experience_level(
            " ".join([title, raw_vacancy.get("summary_text", ""), description])
        )

        return {
            "title": title,
            "description": description,
            "salary_from": salary_from,
            "salary_to": salary_to,
            "salary_gross": salary_gross,
            "currency": currency,
            "skills_required": skills,
            "location": clean_text(detail.get("location") or raw_vacancy.get("location")),
            "experience_range": experience,
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

    async def _fetch_search_page(self, search_text: str, page: int) -> str | None:
        return await self._request_text(
            self.vacancies_url,
            params={
                "q": search_text,
                "type": "all",
                "page": page,
                "with_salary": "true",  # Only vacancies that mention salary
            },
        )

    def _extract_cards(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        cards: list[dict[str, Any]] = []

        for link in soup.select('a[href*="/vacancies/"]'):
            href = link.get("href", "")
            # Skip navigation/filter links
            if not href or re.search(r"/vacancies/(?:skills|page|rss|\?)", href):
                continue
            # Must look like a vacancy URL (ends with a number or slug)
            if not re.search(r"/vacancies/\d+", href):
                continue

            card = self._find_card_container(link)
            card_text = clean_text(card.get_text(" ", strip=True) if card else link.get_text(" ", strip=True))
            if not card_text:
                continue

            title = clean_text(link.get_text(" ", strip=True))
            if not title or len(title) < 3:
                continue

            salary_text = self._extract_salary_text(card) or card_text
            # Skip cards that explicitly say "salary not specified"
            if NO_SALARY_RE.search(salary_text) and not re.search(r"\d", salary_text):
                continue

            skills = self._extract_skills(card)
            location = self._extract_location(card_text)

            cards.append(
                {
                    "title": title,
                    "salary_text": salary_text,
                    "skills_required": skills,
                    "location": location,
                    "experience_range": extract_experience_level(card_text),
                    "summary_text": card_text,
                    "source_url": urljoin(self.base_url, href),
                }
            )

        return cards

    def _parse_detail_page(self, html: str, fallback: dict[str, Any]) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.select_one("h1")
        title = clean_text(h1.get_text(" ", strip=True) if h1 else "")

        # Try multiple selectors for the description body
        body = soup.select_one(
            '[class*="vacancy-section"], [class*="vacancy-body"], '
            '[class*="description"], article, .content, main'
        )
        full_text = clean_text(body.get_text(" ", strip=True) if body else "")
        if not full_text:
            full_text = clean_text(soup.get_text(" ", strip=True))

        salary_text = self._extract_salary_text(soup) or fallback.get("salary_text", "")
        skills = self._extract_skills(soup)

        return {
            "title": title or fallback.get("title", ""),
            "description": full_text,
            "salary_text": salary_text,
            "skills_required": skills or fallback.get("skills_required", []),
            "location": fallback.get("location", ""),
            "experience_range": extract_experience_level(full_text) or fallback.get("experience_range", ""),
            "source_url": fallback.get("source_url"),
        }

    @staticmethod
    def _find_card_container(link: Tag) -> Tag | None:
        current: Tag | None = link
        for _ in range(8):
            if current is None:
                return None
            classes = " ".join(current.get("class", []))
            if current.name in {"article", "li", "div"} and (
                "vacancy" in classes or "card" in classes or "item" in classes
            ):
                return current
            parent = current.parent
            current = parent if isinstance(parent, Tag) else None
        return link.parent if isinstance(link.parent, Tag) else None

    @staticmethod
    def _extract_salary_text(node: Tag | BeautifulSoup | None) -> str:
        if node is None:
            return ""

        # Look for salary-specific elements first
        salary_candidates = node.select('[class*="salary"], [data-qa*="salary"], [class*="compensation"]')
        for candidate in salary_candidates:
            text = clean_text(candidate.get_text(" ", strip=True))
            if text and re.search(r"\d", text) and not NO_SALARY_RE.search(text):
                return text

        # Fallback: find salary pattern in full text
        text = clean_text(node.get_text(" ", strip=True))
        if NO_SALARY_RE.search(text):
            return ""
        match = re.search(
            r"(?:от\s*)?\d[\d\s]{2,}(?:\s*(?:до|-|–|—)\s*\d[\d\s]{2,})?\s*(?:₽|руб\.?|\$|€|rub|usd|eur)",
            text,
            re.IGNORECASE,
        )
        return match.group(0) if match else ""

    @staticmethod
    def _extract_skills(node: Tag | BeautifulSoup | None) -> list[str]:
        if node is None:
            return []

        skills = [
            tag.get_text(" ", strip=True)
            for tag in node.select(
                'a[href*="/skills/"], [class*="skill"] a, [class*="skills"] a, '
                '[class*="tag"] a, [class*="tags"] a, [class*="tech"] a'
            )
        ]
        return unique_strings(skills)

    @staticmethod
    def _extract_location(text: str) -> str:
        if "Можно удалённо" in text or "Можно удаленно" in text or "Удалённо" in text:
            return "Удалённо"
        known_cities = (
            "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань",
            "Нижний Новгород", "Самара", "Ростов-на-Дону", "Краснодар", "Воронеж",
            "Пермь", "Челябинск", "Красноярск", "Уфа", "Тюмень", "Калининград",
            "Минск", "Алматы", "Ташкент",
        )
        for city in known_cities:
            if city in text:
                return city
        return ""
