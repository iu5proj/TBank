from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping, Sequence
from typing import Any

from base import BaseParser
from schemas import VacancyDatasetSchema
from utils import clean_text, extract_skills_from_text, normalize_salary_range, unique_strings


# --------------------------------------------------------------------------- #
# Full list of OKATO region codes — all 85 subjects of the Russian Federation
# --------------------------------------------------------------------------- #
TRUDVSEM_ALL_REGIONS = (
    # Cities of federal significance
    "77",  # Москва
    "78",  # Санкт-Петербург
    "92",  # Севастополь
    # Republics
    "01",  # Адыгея
    "02",  # Башкортостан
    "03",  # Бурятия
    "04",  # Алтай
    "05",  # Дагестан
    "06",  # Ингушетия
    "07",  # Кабардино-Балкария
    "08",  # Калмыкия
    "09",  # Карачаево-Черкесия
    "10",  # Карелия
    "11",  # Коми
    "12",  # Марий Эл
    "13",  # Мордовия
    "14",  # Саха (Якутия)
    "15",  # Северная Осетия
    "16",  # Татарстан
    "17",  # Тыва
    "18",  # Удмуртия
    "19",  # Хакасия
    "20",  # Чечня
    "21",  # Чувашия
    "91",  # Крым
    # Krais
    "22",  # Алтайский край
    "23",  # Краснодарский край
    "24",  # Красноярский край
    "25",  # Приморский край
    "26",  # Ставропольский край
    "27",  # Хабаровский край
    "75",  # Забайкальский край
    "41",  # Камчатский край
    "59",  # Пермский край
    # Oblasts
    "28",  # Амурская область
    "29",  # Архангельская область
    "30",  # Астраханская область
    "31",  # Белгородская область
    "32",  # Брянская область
    "33",  # Владимирская область
    "34",  # Волгоградская область
    "35",  # Вологодская область
    "36",  # Воронежская область
    "37",  # Ивановская область
    "38",  # Иркутская область
    "39",  # Калининградская область
    "40",  # Калужская область
    "42",  # Кемеровская область
    "43",  # Кировская область
    "44",  # Костромская область
    "45",  # Курганская область
    "46",  # Курская область
    "47",  # Ленинградская область
    "48",  # Липецкая область
    "49",  # Магаданская область
    "50",  # Московская область
    "51",  # Мурманская область
    "52",  # Нижегородская область
    "53",  # Новгородская область
    "54",  # Новосибирская область
    "55",  # Омская область
    "56",  # Оренбургская область
    "57",  # Орловская область
    "58",  # Пензенская область
    "60",  # Псковская область
    "61",  # Ростовская область
    "62",  # Рязанская область
    "63",  # Самарская область
    "64",  # Саратовская область
    "65",  # Сахалинская область
    "66",  # Свердловская область
    "67",  # Смоленская область
    "68",  # Тамбовская область
    "69",  # Тверская область
    "70",  # Томская область
    "71",  # Тульская область
    "72",  # Тюменская область
    "73",  # Ульяновская область
    "74",  # Челябинская область
    "76",  # Ярославская область
    # Autonomous okrugs and oblast
    "79",  # Еврейская АО
    "83",  # Ненецкий АО
    "86",  # Ханты-Мансийский АО
    "87",  # Чукотский АО
    "89",  # Ямало-Ненецкий АО
)

# Map OKATO codes to human-readable region names for ML features
OKATO_TO_REGION_NAME: dict[str, str] = {
    "77": "Москва", "78": "Санкт-Петербург", "92": "Севастополь",
    "01": "Адыгея", "02": "Башкортостан", "03": "Бурятия",
    "04": "Алтай", "05": "Дагестан", "06": "Ингушетия",
    "07": "Кабардино-Балкария", "08": "Калмыкия", "09": "Карачаево-Черкесия",
    "10": "Карелия", "11": "Коми", "12": "Марий Эл", "13": "Мордовия",
    "14": "Саха (Якутия)", "15": "Северная Осетия", "16": "Татарстан",
    "17": "Тыва", "18": "Удмуртия", "19": "Хакасия", "20": "Чечня",
    "21": "Чувашия", "91": "Крым",
    "22": "Алтайский край", "23": "Краснодарский край", "24": "Красноярский край",
    "25": "Приморский край", "26": "Ставропольский край", "27": "Хабаровский край",
    "75": "Забайкальский край", "41": "Камчатский край", "59": "Пермский край",
    "28": "Амурская область", "29": "Архангельская область",
    "30": "Астраханская область", "31": "Белгородская область",
    "32": "Брянская область", "33": "Владимирская область",
    "34": "Волгоградская область", "35": "Вологодская область",
    "36": "Воронежская область", "37": "Ивановская область",
    "38": "Иркутская область", "39": "Калининградская область",
    "40": "Калужская область", "42": "Кемеровская область",
    "43": "Кировская область", "44": "Костромская область",
    "45": "Курганская область", "46": "Курская область",
    "47": "Ленинградская область", "48": "Липецкая область",
    "49": "Магаданская область", "50": "Московская область",
    "51": "Мурманская область", "52": "Нижегородская область",
    "53": "Новгородская область", "54": "Новосибирская область",
    "55": "Омская область", "56": "Оренбургская область",
    "57": "Орловская область", "58": "Пензенская область",
    "60": "Псковская область", "61": "Ростовская область",
    "62": "Рязанская область", "63": "Самарская область",
    "64": "Саратовская область", "65": "Сахалинская область",
    "66": "Свердловская область", "67": "Смоленская область",
    "68": "Тамбовская область", "69": "Тверская область",
    "70": "Томская область", "71": "Тульская область",
    "72": "Тюменская область", "73": "Ульяновская область",
    "74": "Челябинская область", "76": "Ярославская область",
    "79": "Еврейская АО", "83": "Ненецкий АО",
    "86": "Ханты-Мансийский АО", "87": "Чукотский АО",
    "89": "Ямало-Ненецкий АО",
}

# Regex to extract city name from long Trudvsem addresses
_CITY_RE = re.compile(
    r"(?:^|,\s*)"                          # start or comma separator
    r"(?:г(?:ород)?\.?\s*)"                # "г", "г.", "город"
    r"([А-ЯЁа-яё][А-ЯЁа-яё\s\-]{1,60})"  # city name
)
_SETTLEMENT_RE = re.compile(
    r"(?:^|,\s*)"
    r"(?:пос(?:ёлок|елок)?\.?\s*|с(?:ело)?\.?\s*|пгт\.?\s*|рп\.?\s*|д(?:еревня)?\.?\s*)"
    r"([А-ЯЁа-яё][А-ЯЁа-яё\s\-]{1,60})"
)


def _extract_city(raw_location: str, region_code: str) -> str:
    """Extract a clean city/settlement name from a verbose Trudvsem address.

    Strategy:
    1. Try to find "г <CityName>" pattern
    2. Try settlement patterns (пос., с., пгт, рп, д.)
    3. Fallback to the region name from OKATO mapping
    """
    if not raw_location:
        return OKATO_TO_REGION_NAME.get(region_code, "")

    # Try city pattern first
    m = _CITY_RE.search(raw_location)
    if m:
        city = m.group(1).strip().rstrip(",. ")
        if len(city) >= 2:
            return city

    # Try settlement patterns
    m = _SETTLEMENT_RE.search(raw_location)
    if m:
        settlement = m.group(1).strip().rstrip(",. ")
        if len(settlement) >= 2:
            region_name = OKATO_TO_REGION_NAME.get(region_code, "")
            return f"{settlement}, {region_name}" if region_name else settlement

    # Fallback: use region name
    return OKATO_TO_REGION_NAME.get(region_code, raw_location[:200])


class TrudvsemParser(BaseParser):
    """Parser for trudvsem.ru (Работа России) open data API.

    This is a GOLD MINE for non-IT professions. The government portal
    contains hundreds of thousands of vacancies across ALL industries:
    construction, medicine, education, logistics, manufacturing, etc.

    Key improvements over v1:
    - All 85 Russian regions instead of 20
    - Deep pagination: up to 10000 vacancies per region
    - Smart location extraction: city names instead of full addresses
    - Robust salary handling with outlier filtering

    API docs: https://opendata.trudvsem.ru/api/v1/vacancies/application.wadl
    No auth required. Free. Up to 100 results per page, max 10000 per query.
    """

    source_name = "trudvsem"
    base_url = "http://opendata.trudvsem.ru/api/v1/vacancies"

    def __init__(
        self,
        *,
        regions: Sequence[str] = TRUDVSEM_ALL_REGIONS,
        max_pages: int = 100,  # Each page = 100 items, so 100 pages = 10000 per region
        currency_rates_to_rub: Mapping[str, float] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            headers={"Accept": "application/json"},
            **kwargs,
        )
        self.regions = tuple(regions)
        self.max_pages = max(1, min(max_pages, 100))  # API limit: offset < 10000
        self.currency_rates_to_rub = dict(currency_rates_to_rub or {})

    async def fetch_vacancies(self) -> list[dict[str, Any]]:
        """Fetch vacancies from all configured regions."""
        all_items: list[dict[str, Any]] = []
        failed_regions: list[str] = []

        for region_code in self.regions:
            try:
                region_items = await self._fetch_region(region_code)
                all_items.extend(region_items)
                if region_items:
                    self.logger.info(
                        "Trudvsem region %s (%s): fetched %d vacancies",
                        region_code,
                        OKATO_TO_REGION_NAME.get(region_code, "?"),
                        len(region_items),
                    )
            except Exception:
                failed_regions.append(region_code)
                self.logger.exception("Failed to fetch trudvsem region %s", region_code)

        unique = self.deduplicate_by(all_items, "_source_url")
        self.logger.info(
            "Trudvsem: fetched %d total (%d unique) from %d regions (%d failed)",
            len(all_items), len(unique), len(self.regions), len(failed_regions),
        )
        return unique

    async def _fetch_region(self, region_code: str) -> list[dict[str, Any]]:
        """Paginate through all vacancies for a given region."""
        items: list[dict[str, Any]] = []
        limit = 100
        empty_pages_in_a_row = 0

        for page in range(self.max_pages):
            offset = page * limit
            if offset >= 10000:  # API hard limit
                break

            url = f"{self.base_url}/region/{region_code}"
            try:
                data = await self._request_json(url, params={"offset": offset, "limit": limit})
            except Exception:
                self.logger.warning("Request failed for region %s page %d", region_code, page)
                break

            if not isinstance(data, dict):
                break

            results = data.get("results", {})
            vacancies_list = results.get("vacancies", [])

            if not vacancies_list:
                empty_pages_in_a_row += 1
                if empty_pages_in_a_row >= 2:
                    break
                continue
            else:
                empty_pages_in_a_row = 0

            for entry in vacancies_list:
                vacancy = entry.get("vacancy", entry)
                vacancy["_source_url"] = self._build_source_url(vacancy)
                vacancy["_region_code"] = region_code
                items.append(vacancy)

            # Check if we've reached the end
            total = results.get("total", 0)
            if offset + limit >= total:
                break

        return items

    async def parse_vacancy(self, raw_vacancy: dict[str, Any]) -> dict[str, Any] | None:
        """Parse a single trudvsem vacancy dict into our intermediate format."""
        title = clean_text(raw_vacancy.get("job-name"))
        if not title:
            return None

        # Salary extraction — trudvsem uses "salary_min" and "salary_max"
        salary_min = self._safe_int(raw_vacancy.get("salary_min") or raw_vacancy.get("salary"))
        salary_max = self._safe_int(raw_vacancy.get("salary_max"))

        # Skip vacancies without any salary info
        if salary_min is None and salary_max is None:
            return None

        # Filter out obvious outliers (monthly salary)
        # Less than 5000 RUB is suspicious, more than 1M is likely an error
        for val in (salary_min, salary_max):
            if val is not None and (val < 5000 or val > 1_000_000):
                if val < 5000:
                    salary_min = None if salary_min == val else salary_min
                    salary_max = None if salary_max == val else salary_max

        if salary_min is None and salary_max is None:
            return None

        # Description
        duty = clean_text(raw_vacancy.get("duty"))
        requirement_text = ""
        requirement = raw_vacancy.get("requirement")
        if isinstance(requirement, dict):
            education = requirement.get("education", "")
            experience_val = requirement.get("experience", "")
            qualification = clean_text(requirement.get("qualification"))
            parts = []
            if education:
                parts.append(f"Образование: {education}")
            if experience_val:
                parts.append(f"Опыт: {experience_val}")
            if qualification:
                parts.append(qualification)
            requirement_text = ". ".join(parts)
        elif isinstance(requirement, str):
            requirement_text = clean_text(requirement)

        description = f"{duty}\n{requirement_text}".strip()

        # ---- Location: extract CITY, not full address ----
        region_code = raw_vacancy.get("_region_code", "")
        raw_location = ""
        addresses = raw_vacancy.get("addresses", {})
        address = addresses.get("address", [])
        if isinstance(address, list) and address:
            first_addr = address[0] if isinstance(address[0], dict) else {}
            raw_location = first_addr.get("location", "")
        elif isinstance(address, dict):
            raw_location = address.get("location", "")

        location = _extract_city(clean_text(raw_location), region_code)

        if not location:
            region = raw_vacancy.get("region", {})
            if isinstance(region, dict):
                location = clean_text(region.get("name", ""))

        # Experience
        experience_range = ""
        if isinstance(requirement, dict):
            exp = requirement.get("experience")
            if exp is not None:
                experience_range = f"{exp} лет" if isinstance(exp, (int, float)) else str(exp)

        # Category from Trudvsem (profession area)
        category = clean_text(raw_vacancy.get("category", {}).get("specialisation", "")) if isinstance(raw_vacancy.get("category"), dict) else ""

        # Skills extraction from title + description + category
        skills = extract_skills_from_text(f"{title} {description} {category}")

        source_url = self._build_source_url(raw_vacancy)
        if not source_url:
            return None

        return {
            "title": title,
            "description": description,
            "salary_from": salary_min,
            "salary_to": salary_max,
            "salary_gross": False,  # Trudvsem typically shows net salary
            "currency": "rub",
            "skills_required": skills,
            "location": location,
            "experience_range": experience_range,
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

    @staticmethod
    def _build_source_url(vacancy: dict[str, Any]) -> str:
        vac_id = vacancy.get("id")
        company = vacancy.get("company", {})
        company_id = company.get("companycode") or company.get("inn") or "unknown"
        if vac_id:
            return f"https://trudvsem.ru/vacancy/card/{company_id}/{vac_id}"
        return ""

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            result = int(float(str(value)))
            return result if result > 0 else None
        except (ValueError, TypeError):
            return None
