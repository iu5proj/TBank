from __future__ import annotations

import os
from dataclasses import dataclass, field


# =============================================================================
# SEARCH QUERIES — covers ALL industries, not just IT
# =============================================================================
DEFAULT_SEARCH_TEXTS = (
    # ===== IT & Development =====
    "python developer", "python разработчик",
    "java developer", "java разработчик",
    "backend developer", "backend разработчик",
    "frontend developer", "frontend разработчик",
    "fullstack developer", "full stack разработчик",
    "golang developer", "go разработчик",
    "c# developer", ".net developer",
    "php developer", "ruby developer",
    "rust developer", "kotlin developer", "scala developer",
    "node.js developer", "react developer", "vue developer", "angular developer",
    "javascript developer", "typescript developer",
    "ios developer", "android developer",
    "flutter developer", "react native developer",
    "c++ разработчик", "embedded разработчик",
    "1с программист", "1с разработчик",
    # ===== Data & AI =====
    "data scientist", "data analyst", "аналитик данных",
    "data engineer", "machine learning engineer", "ml engineer",
    "deep learning", "nlp engineer", "computer vision",
    "mlops engineer", "bi analyst", "etl developer",
    # ===== DevOps & Infra =====
    "devops engineer", "devops инженер",
    "sre engineer", "системный администратор",
    "cloud engineer", "kubernetes engineer",
    "platform engineer", "linux администратор",
    # ===== QA =====
    "qa engineer", "qa инженер", "тестировщик",
    "автоматизатор тестирования", "qa automation",
    # ===== IT Management =====
    "system analyst", "системный аналитик", "бизнес аналитик",
    "product manager", "project manager", "product owner",
    "scrum master", "team lead", "tech lead", "cto",
    # ===== Design =====
    "ui ux designer", "ux дизайнер", "product designer",
    "web designer", "графический дизайнер", "дизайнер интерьеров",
    # ===== Security =====
    "информационная безопасность", "security engineer", "pentester",
    # ===== SAP & ERP =====
    "sap консультант", "erp консультант",

    # ===== FINANCE & ACCOUNTING =====
    "бухгалтер", "главный бухгалтер",
    "финансовый аналитик", "финансовый директор",
    "экономист", "аудитор",
    "кредитный специалист", "банковский специалист",
    "финансовый менеджер", "казначей",
    "налоговый консультант", "страховой агент",

    # ===== SALES & MARKETING =====
    "менеджер по продажам", "торговый представитель",
    "руководитель отдела продаж", "коммерческий директор",
    "маркетолог", "интернет маркетолог", "smm менеджер",
    "контент менеджер", "копирайтер",
    "pr менеджер", "бренд менеджер",
    "менеджер по рекламе", "таргетолог",
    "seo специалист", "директолог",
    "менеджер по работе с клиентами", "account manager",
    "продавец консультант", "кассир",

    # ===== HR & RECRUITMENT =====
    "hr менеджер", "рекрутер", "hr директор",
    "специалист по кадрам", "менеджер по персоналу",
    "hr бизнес партнер",

    # ===== MEDICINE & HEALTHCARE =====
    "врач терапевт", "врач хирург", "врач стоматолог",
    "медицинская сестра", "фельдшер", "фармацевт",
    "врач педиатр", "врач невролог", "врач кардиолог",
    "врач анестезиолог", "лаборант",

    # ===== EDUCATION =====
    "учитель", "преподаватель", "воспитатель",
    "репетитор", "педагог", "методист",
    "тренер", "логопед", "психолог",

    # ===== ENGINEERING & CONSTRUCTION =====
    "инженер", "инженер конструктор", "инженер проектировщик",
    "архитектор", "прораб", "мастер участка",
    "инженер строитель", "сметчик",
    "электрик", "электромонтажник", "сварщик",
    "слесарь", "токарь", "фрезеровщик",
    "инженер энергетик", "инженер механик",
    "инженер эколог", "геодезист",

    # ===== LOGISTICS & TRANSPORT =====
    "логист", "менеджер по логистике",
    "начальник склада", "кладовщик",
    "водитель", "водитель категории с", "водитель погрузчика",
    "экспедитор", "диспетчер", "курьер",
    "таможенный специалист", "декларант",

    # ===== LEGAL =====
    "юрист", "юрисконсульт", "адвокат",
    "нотариус", "помощник юриста",
    "юрист по недвижимости", "корпоративный юрист",

    # ===== MANUFACTURING & PRODUCTION =====
    "технолог", "инженер технолог",
    "начальник производства", "мастер смены",
    "оператор станков", "наладчик",
    "контролер отк", "упаковщик",
    "инженер по качеству",

    # ===== HOSPITALITY & SERVICE =====
    "повар", "шеф повар", "кондитер",
    "официант", "бармен", "администратор",
    "управляющий рестораном", "менеджер отеля",
    "горничная", "портье",

    # ===== AGRICULTURE =====
    "агроном", "зоотехник", "ветеринар",
    "тракторист", "механизатор",

    # ===== MEDIA & CREATIVE =====
    "журналист", "редактор", "корректор",
    "фотограф", "видеограф", "видеомонтажер",
    "переводчик", "лингвист",

    # ===== REAL ESTATE =====
    "риэлтор", "менеджер по недвижимости",
    "оценщик", "управляющий недвижимостью",

    # ===== EXECUTIVE =====
    "генеральный директор", "исполнительный директор",
    "операционный директор", "директор филиала",
    "руководитель подразделения",

    # ===== OFFICE & ADMIN =====
    "офис менеджер", "секретарь", "делопроизводитель",
    "личный помощник руководителя", "ассистент",
    "оператор call центра", "специалист техподдержки",

    # ===== SECURITY =====
    "охранник", "начальник службы безопасности",

    # ===== BEAUTY & WELLNESS =====
    "парикмахер", "косметолог", "мастер маникюра",
    "массажист", "фитнес тренер",
)


# HH.ru region IDs for splitting searches to bypass the 2000-result API cap.
HH_AREAS = (
    "113",   # Россия (все)
    "1",     # Москва
    "2",     # Санкт-Петербург
    "3",     # Екатеринбург
    "4",     # Новосибирск
    "88",    # Казань
    "66",    # Нижний Новгород
    "72",    # Самара
    "53",    # Краснодар
    "104",   # Ростов-на-Дону
    "76",    # Воронеж
    "99",    # Пермь
    "78",    # Красноярск
    "68",    # Уфа
    "98",    # Челябинск
)

# Import full region list from trudvsem parser
from parsers.trudvsem import TRUDVSEM_ALL_REGIONS as TRUDVSEM_REGIONS


@dataclass(frozen=True)
class ParserSettings:
    database_url: str | None
    search_texts: tuple[str, ...] = DEFAULT_SEARCH_TEXTS
    request_timeout_seconds: float = 30.0
    request_retries: int = 3
    max_pages: int = 20
    max_concurrency: int = 5
    save_batch_size: int = 200

    # HH.ru
    hh_areas: tuple[str, ...] = HH_AREAS
    hh_per_page: int = 100
    hh_rate_limit_rps: float = 2.0
    hh_user_agent: str = "ZarabotokApp/1.0 (mailto:leosp@yandex.ru)"
    hh_skip_details: bool = False

    # Habr Career
    habr_rate_limit_rps: float = 0.5
    habr_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    # SuperJob
    superjob_app_id: str | None = None
    superjob_count: int = 100
    superjob_rate_limit_rps: float = 1.0

    # Trudvsem (Работа России)
    trudvsem_regions: tuple[str, ...] = TRUDVSEM_REGIONS
    trudvsem_max_pages: int = 100  # 100 pages × 100 items = 10000 per region
    trudvsem_rate_limit_rps: float = 3.0  # Government API is generous with limits

    currency_rates_to_rub: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> ParserSettings:
        return cls(
            database_url=os.getenv("DATABASE_URL"),
            search_texts=_csv("PARSER_SEARCH_TEXTS", DEFAULT_SEARCH_TEXTS),
            request_timeout_seconds=_float("PARSER_TIMEOUT_SECONDS", 30.0),
            request_retries=_int("PARSER_REQUEST_RETRIES", 3),
            max_pages=_int("PARSER_MAX_PAGES", 20),
            max_concurrency=_int("PARSER_MAX_CONCURRENCY", 5),
            save_batch_size=_int("PARSER_SAVE_BATCH_SIZE", 200),
            hh_areas=_csv("HH_AREAS", HH_AREAS),
            hh_per_page=min(_int("HH_PER_PAGE", 100), 100),
            hh_rate_limit_rps=_float("HH_RATE_LIMIT_RPS", 2.0),
            hh_user_agent=os.getenv(
                "HH_USER_AGENT",
                "ZarabotokApp/1.0 (mailto:leosp@yandex.ru)",
            ),
            hh_skip_details=os.getenv("HH_SKIP_DETAILS", "").lower() in {"1", "true", "yes"},
            habr_rate_limit_rps=_float("HABR_RATE_LIMIT_RPS", 0.5),
            habr_user_agent=os.getenv(
                "HABR_USER_AGENT",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            ),
            superjob_app_id=os.getenv("SUPERJOB_APP_ID") or os.getenv("SJ_API_APP_ID"),
            superjob_count=min(_int("SUPERJOB_COUNT", 100), 100),
            superjob_rate_limit_rps=_float("SUPERJOB_RATE_LIMIT_RPS", 1.0),
            trudvsem_regions=_csv("TRUDVSEM_REGIONS", TRUDVSEM_REGIONS),
            trudvsem_max_pages=_int("TRUDVSEM_MAX_PAGES", 100),
            trudvsem_rate_limit_rps=_float("TRUDVSEM_RATE_LIMIT_RPS", 3.0),
            currency_rates_to_rub=_currency_rates_from_env(),
        )


def _csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if not raw:
        return default
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values or default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _currency_rates_from_env() -> dict[str, float]:
    rates: dict[str, float] = {}
    for code in ("USD", "EUR", "UAH", "UZS"):
        value = os.getenv(f"PARSER_{code}_RUB")
        if not value:
            continue
        try:
            rates[code.casefold()] = float(value)
        except ValueError:
            continue
    return rates
