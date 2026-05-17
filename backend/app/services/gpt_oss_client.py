"""HTTP client for gpt-oss-20b salary analysis."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class GptOssClientError(RuntimeError):
    """Raised when the model endpoint cannot return usable JSON."""

    def __init__(self, message: str, *, raw_payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.raw_payload = raw_payload


class GptOssClient:
    """Thin client that sends one prepared payload to the model service."""

    async def generate_once(self, input_payload: dict[str, Any]) -> dict[str, Any]:
        """Call the configured model endpoint once and return raw JSON."""
        mode = settings.GPT_OSS_CLIENT_MODE.strip().lower()
        if mode == "openai_compatible":
            return await self._generate_openai_compatible(input_payload)
        return await self._generate_service(input_payload)

    async def _generate_service(self, input_payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{settings.GPT_OSS_SERVICE_URL.rstrip('/')}{settings.GPT_OSS_ANALYZE_PATH}"
        try:
            async with httpx.AsyncClient(timeout=settings.GPT_OSS_TIMEOUT) as client:
                response = await client.post(url, json=input_payload)
                response.raise_for_status()
                try:
                    data = response.json()
                except ValueError as exc:
                    raise GptOssClientError(
                        "model service returned invalid JSON",
                        raw_payload={"raw_text": response.text},
                    ) from exc
        except GptOssClientError:
            raise
        except httpx.HTTPStatusError as exc:
            logger.exception("gpt-oss service returned HTTP %s", exc.response.status_code)
            message = f"gpt-oss service returned HTTP {exc.response.status_code}: {exc.response.text}"
            raise GptOssClientError(
                message,
                raw_payload={"error": exc.response.text},
            ) from exc
        except httpx.TimeoutException as exc:
            logger.exception("gpt-oss service call timed out")
            raise GptOssClientError("gpt-oss service call timed out", raw_payload={"error": str(exc)}) from exc
        except httpx.HTTPError as exc:
            logger.exception("gpt-oss service call failed")
            raise GptOssClientError(f"gpt-oss service call failed: {exc}", raw_payload={"error": str(exc)}) from exc

        if not isinstance(data, dict):
            raise GptOssClientError("model service returned non-object JSON", raw_payload={"response": data})
        return data

    async def _generate_openai_compatible(self, input_payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{settings.GPT_OSS_BASE_URL.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.GPT_OSS_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": settings.GPT_OSS_MODEL_NAME,
            "messages": [
                {"role": "system", "content": _load_prompt()},
                {"role": "user", "content": json.dumps(input_payload, ensure_ascii=False)},
            ],
            "temperature": settings.GPT_OSS_TEMPERATURE,
            "max_tokens": settings.GPT_OSS_MAX_TOKENS,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.GPT_OSS_TIMEOUT) as client:
                response = await client.post(url, headers=headers, json=body)
                response.raise_for_status()
                envelope = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.exception("gpt-oss openai-compatible call failed")
            raw = {"error": str(exc)}
            if "response" in locals():
                raw["raw_text"] = response.text
            raise GptOssClientError("gpt-oss openai-compatible call failed", raw_payload=raw) from exc

        content = _extract_message_content(envelope)
        try:
            data = _parse_json_object(content)
        except ValueError as exc:
            raise GptOssClientError(
                "gpt-oss returned invalid JSON content",
                raw_payload={"raw_text": content, "envelope": envelope},
            ) from exc
        if not isinstance(data, dict):
            raise GptOssClientError("gpt-oss returned non-object JSON content", raw_payload={"response": data})
        return data


def _extract_message_content(envelope: dict[str, Any]) -> str:
    choices = envelope.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GptOssClientError("gpt-oss response has no choices", raw_payload={"envelope": envelope})
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise GptOssClientError("gpt-oss response has no message content", raw_payload={"envelope": envelope})
    return message["content"]


def _parse_json_object(content: str) -> dict[str, Any]:
    cleaned = _strip_code_fence(content.strip())
    try:
        data = json.loads(cleaned)
    except ValueError:
        extracted = _extract_first_json_object(cleaned)
        if extracted is None:
            raise
        data = json.loads(extracted)
    if not isinstance(data, dict):
        raise ValueError("gpt-oss returned non-object JSON content")
    return data


def _strip_code_fence(content: str) -> str:
    if not content.startswith("```"):
        return content
    lines = content.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return content


def _extract_first_json_object(content: str) -> str | None:
    start = content.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(content[start:], start=start):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[start : index + 1]
    return None


def _load_prompt() -> str:
    prompt_dir = Path(__file__).resolve().parents[1] / "prompts"
    prompt_path = prompt_dir / f"{settings.GPT_OSS_PROMPT_VERSION}.txt"
    if not prompt_path.exists():
        prompt_path = prompt_dir / "salary_estimation_prompt_v1.txt"
    return prompt_path.read_text(encoding="utf-8")


gpt_oss_client = GptOssClient()
