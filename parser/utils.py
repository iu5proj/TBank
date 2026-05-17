from __future__ import annotations

import html
import re
from collections.abc import Iterable, Mapping
from typing import Any

from bs4 import BeautifulSoup


DEFAULT_CURRENCY_RATES_TO_RUB: dict[str, float] = {
    "rub": 1.0,
    "rur": 1.0,
    "руб": 1.0,
    "руб.": 1.0,
    "₽": 1.0,
}

COMMON_TECH_SKILLS = [
    # ===================== IT & DEVELOPMENT =====================
    # Programming Languages
    "Python", "Java", "JavaScript", "TypeScript", "C#", "C++", "Go", "Golang",
    "PHP", "Ruby", "Rust", "Kotlin", "Swift", "Scala", "R", "Dart", "Lua",
    # Databases
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "ClickHouse", "Redis", "Cassandra",
    "Oracle", "MSSQL", "SQLite", "Elasticsearch",
    # Messaging & Streaming
    "Kafka", "RabbitMQ", "NATS",
    # Data Engineering
    "Airflow", "Spark", "Hadoop", "dbt", "Flink",
    # DevOps & Cloud
    "Docker", "Kubernetes", "Linux", "Git", "GitLab", "CI/CD", "Terraform",
    "Ansible", "Jenkins", "Prometheus", "Grafana", "Nginx",
    "AWS", "Azure", "GCP", "Yandex Cloud",
    # Backend Frameworks
    "FastAPI", "Django", "Flask", "Aiohttp", "Spring", "Spring Boot",
    "ASP.NET", "Laravel", "Symfony", "Express.js", "NestJS",
    # Frontend
    "React", "Vue", "Angular", "Next.js", "Nuxt", "Svelte",
    "HTML", "CSS", "Sass", "Tailwind", "Webpack", "Vite",
    # Mobile
    "Flutter", "React Native", "SwiftUI", "Jetpack Compose",
    # APIs
    "REST", "GraphQL", "gRPC", "WebSocket", "SOAP",
    # ML & AI
    "PyTorch", "TensorFlow", "Pandas", "NumPy", "Scikit-learn",
    "ML", "NLP", "LLM", "MLOps", "OpenCV", "Keras", "XGBoost", "CatBoost",
    # 1C & ERP
    "1С", "1C", "SAP", "Bitrix", "Битрикс",

    # ===================== OFFICE & BUSINESS =====================
    "Excel", "Word", "Power BI", "Tableau", "Google Analytics",
    "Jira", "Confluence", "Trello", "Figma", "Photoshop",
    "AutoCAD", "SolidWorks", "Компас", "ArchiCAD", "Revit",
    "PowerPoint", "Outlook", "MS Office",

    # ===================== FINANCE & ACCOUNTING =====================
    "МСФО", "РСБУ", "налоговый учёт", "бюджетирование",
    "финансовый анализ", "аудит", "банковское дело",
    "бухгалтерский учёт", "бухгалтерский учет",
    "расчёт заработной платы", "расчет заработной платы",
    "кассовые операции", "инвентаризация",
    "налоговая отчётность", "налоговая отчетность",
    "управленческий учёт", "управленческий учет",

    # ===================== MARKETING & SALES =====================
    "CRM", "Яндекс.Директ", "Google Ads", "SEO", "SMM",
    "контекстная реклама", "таргетированная реклама",
    "AmoCRM", "Salesforce", "Bitrix24",
    "холодные звонки", "активные продажи", "B2B", "B2C",
    "работа с возражениями", "ведение переговоров",

    # ===================== MEDICINE & HEALTHCARE =====================
    "МИС", "ЕМИАС",
    "сестринское дело", "первая помощь", "СЛР",
    "ЭКГ", "УЗИ", "рентген", "МРТ", "КТ", "флюорография",
    "хирургия", "терапия", "педиатрия", "стоматология",
    "акушерство", "гинекология", "неврология", "кардиология",
    "анестезиология", "реанимация", "лабораторная диагностика",
    "фармакология", "фармация", "рецептура",
    "санитарные нормы", "СанПиН", "медицинская документация",
    "диспансеризация", "вакцинация", "перевязки", "инъекции",

    # ===================== EDUCATION =====================
    "педагогика", "методика преподавания", "дошкольное образование",
    "начальное образование", "ФГОС",
    "воспитательная работа", "внеурочная деятельность",
    "репетиторство", "логопедия", "дефектология",
    "психология", "коррекционная педагогика",

    # ===================== LEGAL =====================
    "Консультант+", "Гарант",
    "гражданское право", "трудовое право", "договорная работа",
    "претензионная работа", "исковая работа",
    "корпоративное право", "земельное право",
    "судебное представительство", "юридическая экспертиза",

    # ===================== CONSTRUCTION & ENGINEERING =====================
    "сварка", "электросварка", "газосварка", "аргонная сварка",
    "монтаж", "демонтаж", "отделочные работы",
    "штукатурка", "малярные работы", "плиточные работы",
    "сантехника", "электромонтаж", "электрика",
    "чтение чертежей", "проектирование", "сметное дело",
    "BIM", "ПИР", "СМР",
    "бетонные работы", "кладка", "кровельные работы",
    "фасадные работы", "ремонт", "строительство",
    "допуск СРО", "охрана труда", "техника безопасности",
    "промышленная безопасность", "пожарная безопасность",
    "ГОСТ", "СНиП", "СП",

    # ===================== MANUFACTURING & PRODUCTION =====================
    "станки ЧПУ", "ЧПУ", "токарная обработка", "фрезерная обработка",
    "слесарные работы", "наладка оборудования",
    "контроль качества", "ОТК", "метрология",
    "ХАССП", "HACCP", "ISO 9001",
    "управление производством", "lean", "бережливое производство",
    "ПЛК", "PLC", "SCADA", "АСУ ТП",
    "гидравлика", "пневматика", "КИПиА",

    # ===================== LOGISTICS & TRANSPORT =====================
    "WMS", "TMS", "складской учёт", "складской учет",
    "логистика", "ВЭД", "таможенное оформление",
    "категория B", "категория C", "категория D", "категория E",
    "водительские права", "тахограф",
    "управление автопарком", "грузоперевозки",
    "погрузчик", "кран", "экскаватор", "бульдозер",
    "1С Торговля", "1С Склад",

    # ===================== HR & RECRUITMENT =====================
    "подбор персонала", "кадровое делопроизводство",
    "адаптация персонала", "оценка персонала",
    "обучение персонала", "мотивация персонала",
    "трудовой кодекс", "ТК РФ",
    "воинский учёт", "воинский учет",

    # ===================== AGRICULTURE =====================
    "агрономия", "растениеводство", "животноводство",
    "ветеринария", "зоотехния", "механизация",
    "удобрения", "средства защиты растений",

    # ===================== HOSPITALITY & SERVICE =====================
    "R-Keeper", "iiko", "приготовление пищи", "кулинария",
    "обслуживание гостей", "сервировка",
    "барное дело", "кондитерское дело",
    "управление рестораном", "гостиничное дело",
    "клининг", "уборка помещений",

    # ===================== BEAUTY & WELLNESS =====================
    "парикмахерское дело", "колористика", "маникюр", "педикюр",
    "косметология", "массаж", "эстетическая медицина",

    # ===================== SECURITY =====================
    "охранная деятельность", "видеонаблюдение", "СКУД",
    "пропускной режим", "инкассация",

    # ===================== LANGUAGES =====================
    "английский язык", "немецкий язык", "китайский язык",
    "французский язык", "испанский язык",

    # ===================== UNIVERSAL SOFT SKILLS =====================
    "работа в команде", "многозадачность", "стрессоустойчивость",
    "обучаемость", "ответственность", "коммуникабельность",
    "грамотная речь", "деловая переписка", "наставничество",
]

NO_SALARY_RE = re.compile(r"(зарплата\s+не\s+указана|по\s+договор[её]нности)", re.IGNORECASE)
SALARY_RE = re.compile(
    r"(?P<prefix_from>от)?\s*"
    r"(?P<first>\d[\d\s]{2,})"
    r"(?:\s*(?:до|-|–|—)\s*(?P<second>\d[\d\s]{2,}))?"
    r"\s*(?P<currency>₽|руб\.?|р\.|\$|usd|eur|€)?",
    re.IGNORECASE,
)
LEVEL_RE = re.compile(
    r"\b(?P<level>Intern|Junior|Middle|Senior|Lead|Team\s*Lead|Tech\s*Lead|"
    r"Стаж[её]р|Джуниор|Младший|Средний|Старший|Ведущий)\b",
    re.IGNORECASE,
)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if "<" in text and ">" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_salary_range(
    salary_from: int | float | str | None,
    salary_to: int | float | str | None,
    *,
    gross: bool = False,
    currency: str | None = "rub",
    currency_rates_to_rub: Mapping[str, float] | None = None,
) -> tuple[int | None, int | None]:
    low = _positive_number(salary_from)
    high = _positive_number(salary_to)
    
    if low is None and high is None:
        return None, None

    rate = _currency_rate(currency, currency_rates_to_rub)
    if rate is None or rate <= 0:
        return None, None

    multiplier = rate * 0.87 if gross else rate

    out_low = max(1, round(low * multiplier)) if low is not None else None
    out_high = max(1, round(high * multiplier)) if high is not None else None
    
    return out_low, out_high


def parse_salary_text(text: str) -> tuple[int | None, int | None, bool, str | None]:
    cleaned = clean_text(text)
    if not cleaned or NO_SALARY_RE.search(cleaned):
        return None, None, False, None

    match = SALARY_RE.search(cleaned)
    if match is None:
        return None, None, False, None

    first = _parse_int(match.group("first"))
    second = _parse_int(match.group("second"))
    currency = _normalize_currency(match.group("currency"))
    prefix_from = bool(match.group("prefix_from"))

    if second is not None:
        return first, second, False, currency
    if prefix_from:
        return first, None, False, currency
    if "до" in cleaned[: match.start()].casefold():
        return None, first, False, currency
    return first, first, False, currency


def extract_experience_level(text: str) -> str:
    match = LEVEL_RE.search(clean_text(text))
    if match is None:
        return ""

    value = match.group("level").strip()
    normalized = value.casefold().replace(" ", "")
    mapping = {
        "стажер": "Intern",
        "стажёр": "Intern",
        "джуниор": "Junior",
        "младший": "Junior",
        "средний": "Middle",
        "старший": "Senior",
        "ведущий": "Lead",
        "teamlead": "Lead",
        "techlead": "Lead",
    }
    return mapping.get(normalized, value)


def extract_skills_from_text(text: str, *, extra_candidates: Iterable[str] = ()) -> list[str]:
    haystack = clean_text(text)
    found: list[str] = []
    for skill in [*COMMON_TECH_SKILLS, *extra_candidates]:
        if not skill:
            continue
        pattern = _skill_pattern(skill)
        if re.search(pattern, haystack, flags=re.IGNORECASE):
            found.append(skill)
    return unique_strings(found)


def unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = clean_text(value)
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _positive_number(value: int | float | str | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = _parse_int(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else None


def _currency_rate(
    currency: str | None,
    currency_rates_to_rub: Mapping[str, float] | None,
) -> float | None:
    currency_key = _normalize_currency(currency) or "rub"
    rates = {**DEFAULT_CURRENCY_RATES_TO_RUB, **dict(currency_rates_to_rub or {})}
    return rates.get(currency_key.casefold())


def _normalize_currency(currency: str | None) -> str | None:
    if currency is None:
        return "rub"
    value = currency.strip().casefold()
    if value in {"р", "р.", "rub", "rur", "руб", "руб.", "₽"}:
        return "rub"
    if value in {"$", "usd"}:
        return "usd"
    if value in {"€", "eur"}:
        return "eur"
    return value


def _skill_pattern(skill: str) -> str:
    escaped = re.escape(skill)
    if re.match(r"^[\w#+./-]+$", skill, flags=re.ASCII):
        return rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])"
    return escaped
