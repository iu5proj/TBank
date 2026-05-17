"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings loaded from environment."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://zarabotok:change_me_in_production@localhost:5432/zarabotok_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # GPT-OSS model service. The current ml_service container is the integration point
    # that can later be replaced by the real gpt-oss-20b runner.
    GPT_OSS_SERVICE_URL: str = "http://ml_service:8001"
    GPT_OSS_ANALYZE_PATH: str = "/analyze"
    GPT_OSS_BASE_URL: str = "http://llm-service:8000/v1"
    GPT_OSS_API_KEY: str = "local-dev-key"
    GPT_OSS_MODEL_NAME: str = "gpt-oss-20b"
    GPT_OSS_MODEL_VERSION: str = "gpt-oss-20b-salary-v1"
    GPT_OSS_PROMPT_VERSION: str = "salary_estimation_prompt_v13"
    GPT_OSS_TIMEOUT: float = 90.0
    GPT_OSS_MAX_TOKENS: int = 1400
    GPT_OSS_TEMPERATURE: float = 0.1
    GPT_OSS_CLIENT_MODE: str = "service"  # service | openai_compatible

    # Segment-scoped vacancy refresh. HH can be blocked, so every source is
    # optional and parser refresh succeeds with data from any enabled source.
    VACANCY_SOURCES: str = "hh,trudvsem,habr,fixture"
    VACANCY_SOURCE_TIMEOUT: float = 20.0
    VACANCY_SOURCE_LIMIT: int = 80
    MIN_CANDIDATE_VACANCIES: int = 5
    MIN_REFRESHED_VACANCIES: int = 1
    SEGMENT_STALE_DAYS: int = 14
    MAX_STALE_SEGMENT_DAYS: int = 45
    PARSER_ENABLE_FIXTURE_SOURCE: bool = True
    HH_BASE_URL: str = "https://api.hh.ru"
    TRUDVSEM_BASE_URL: str = "https://opendata.trudvsem.ru/api/v1"
    HABR_CAREER_BASE_URL: str = "https://career.habr.com"
    HABR_CAREER_API_TOKEN: str = ""
    PARSER_USER_AGENT: str = "ZarabotokMLRAG/0.1"

    LLM_LOCK_TTL_SECONDS: int = 120

    # Legacy ML Service values kept for compatibility with old local scripts.
    ML_SERVICE_URL: str = "http://ml_service:8001"
    ML_SERVICE_TIMEOUT: float = 30.0

    # Anthropic Claude
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # App
    SECRET_KEY: str = "change_me_to_random_string"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    API_AUTH_TOKEN: str = ""
    RATE_LIMIT_ANALYZE_PER_MINUTE: int = 30

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
