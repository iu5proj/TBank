from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from base import BaseParser
from schemas import VacancyDatasetSchema
from utils import clean_text, extract_skills_from_text, normalize_salary_range, unique_strings


class SuperJobParser(BaseParser):
    source_name = "superjob"
    vacancies_url = "https://api.superjob.ru/2.0/vacancies/"

    def __init__(
        self,
        *,
        search_texts: Sequence[str],
        app_id: str | None,
        count: int = 100,
        max_pages: int = 10,
        currency_rates_to_rub: Mapping[str, float] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            headers={
                "Accept": "application/json",
                **({"X-Api-App-Id": app_id} if app_id else {}),
            },
            **kwargs,
        )
        self.search_texts = tuple(search_texts)
        self.app_id = app_id
        self.count = max(1, min(count, 100))
        self.max_pages = max(1, max_pages)
        self.currency_rates_to_rub = dict(currency_rates_to_rub or {})

    async def fetch_vacancies(self) -> list[dict[str, Any]]:
        if not self.app_id:
            self.logger.warning("SUPERJOB_APP_ID is not set; SuperJob parser is skipped")
            return []

        all_items: list[dict[str, Any]] = []
        for keyword in self.search_texts:
            pages = await self._fetch_keyword_pages(keyword)
            all_items.extend(item for page in pages for item in page.get("objects", []))

        return self.deduplicate_by(all_items, "id")

    async def parse_vacancy(self, raw_vacancy: dict[str, Any]) -> dict[str, Any] | None:
        if raw_vacancy.get("agreement"):
            return None

        title = clean_text(raw_vacancy.get("profession"))
        work = clean_text(raw_vacancy.get("work"))
        candidate = clean_text(raw_vacancy.get("candidat") or raw_vacancy.get("candidate"))
        compensation = clean_text(raw_vacancy.get("compensation"))
        description = "\n".join(part for part in [work, candidate, compensation] if part)
        town = raw_vacancy.get("town") or {}
        experience = raw_vacancy.get("experience") or {}

        explicit_skills = raw_vacancy.get("skills") or raw_vacancy.get("key_skills") or []
        if isinstance(explicit_skills, list):
            explicit_skills = [
                skill.get("title") if isinstance(skill, dict) else skill
                for skill in explicit_skills
            ]

        skills = unique_strings(explicit_skills) or extract_skills_from_text(f"{title} {description}")
        source_url = raw_vacancy.get("link")
        if not source_url and raw_vacancy.get("id"):
            source_url = f"https://www.superjob.ru/vakansii/{raw_vacancy['id']}.html"
        if not title or not source_url:
            return None

        return {
            "title": title,
            "description": description,
            "salary_from": raw_vacancy.get("payment_from"),
            "salary_to": raw_vacancy.get("payment_to"),
            "salary_gross": bool(raw_vacancy.get("payment_gross") or raw_vacancy.get("gross")),
            "currency": raw_vacancy.get("currency"),
            "skills_required": skills,
            "location": town.get("title", "") if isinstance(town, dict) else clean_text(town),
            "experience_range": experience.get("title", "") if isinstance(experience, dict) else clean_text(experience),
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

    async def _fetch_keyword_pages(self, keyword: str) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        for page in range(self.max_pages):
            page_data = await self._fetch_page(keyword, page)
            if not page_data:
                break
            pages.append(page_data)
            if not page_data.get("more"):
                break
        return pages

    async def _fetch_page(self, keyword: str, page: int) -> dict[str, Any] | None:
        params = {
            "keyword": keyword,
            "page": page,
            "count": self.count,
            "no_agreement": 1,
            "payment_from": 1,
        }
        data = await self._request_json(self.vacancies_url, params=params)
        return data if isinstance(data, dict) else None
