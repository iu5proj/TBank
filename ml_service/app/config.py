"""Runtime configuration for the ML service."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value == "" else value


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Environment-backed settings.

    The service intentionally avoids reading a local dotenv file: docker compose
    injects variables through env_file, and tests can patch os.environ directly.
    """

    predictor_mode: str
    openai_base_url: str
    openai_api_key: str
    openai_model_name: str
    openai_api_style: str
    openai_timeout: float
    openai_max_tokens: int
    openai_num_ctx: int
    openai_temperature: float
    openai_reasoning_effort: str
    openai_json_mode: bool
    prompt_path: str


def load_settings() -> Settings:
    return Settings(
        predictor_mode=_env("ML_PREDICTOR_MODE", "stub").strip().lower(),
        openai_base_url=_env(
            "ML_OPENAI_BASE_URL",
            _env("GPT_OSS_BASE_URL", "http://llm-service:8000/v1"),
        ),
        openai_api_key=_env("ML_OPENAI_API_KEY", _env("GPT_OSS_API_KEY", "local-dev-key")),
        openai_model_name=_env("ML_OPENAI_MODEL_NAME", _env("GPT_OSS_MODEL_NAME", "gpt-oss-20b")),
        openai_api_style=_env("ML_OPENAI_API_STYLE", "openai").strip().lower(),
        openai_timeout=_float_env("ML_OPENAI_TIMEOUT", _float_env("GPT_OSS_TIMEOUT", 25.0)),
        openai_max_tokens=_int_env("ML_OPENAI_MAX_TOKENS", _int_env("GPT_OSS_MAX_TOKENS", 900)),
        openai_num_ctx=_int_env("ML_OPENAI_NUM_CTX", 4096),
        openai_temperature=_float_env("ML_OPENAI_TEMPERATURE", _float_env("GPT_OSS_TEMPERATURE", 0.1)),
        openai_reasoning_effort=_env("ML_OPENAI_REASONING_EFFORT", "low").strip().lower(),
        openai_json_mode=_bool_env("ML_OPENAI_JSON_MODE", True),
        prompt_path=_env("ML_OPENAI_PROMPT_PATH", ""),
    )


settings = load_settings()
