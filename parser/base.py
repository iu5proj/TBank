from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from schemas import VacancyDatasetSchema


class AsyncRateLimiter:
    """Simple per-parser request start limiter."""

    def __init__(self, requests_per_second: float) -> None:
        self._min_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0.0
        self._lock = asyncio.Lock()
        self._next_request_at = 0.0

    async def acquire(self) -> None:
        if self._min_interval <= 0:
            return

        async with self._lock:
            now = time.monotonic()
            delay = self._next_request_at - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_request_at = time.monotonic() + self._min_interval


class BaseParser(ABC):
    """Template Method base class for vacancy data sources."""

    source_name: str = "base"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        rate_limit_rps: float = 1.0,
        max_concurrency: int = 5,
        timeout_seconds: float = 30.0,
        request_retries: int = 3,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        max_concurrency = max(1, max_concurrency)
        self.logger = logging.getLogger(f"parser.{self.source_name}")
        self.rate_limiter = AsyncRateLimiter(rate_limit_rps)
        self.parse_semaphore = asyncio.Semaphore(max_concurrency)
        self.request_retries = max(0, request_retries)
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            headers=dict(headers or {}),
            follow_redirects=True,
            limits=httpx.Limits(
                max_connections=max(1, max_concurrency * 2),
                max_keepalive_connections=max(1, max_concurrency),
            ),
        )

    async def __aenter__(self) -> BaseParser:
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def collect(self) -> list[VacancyDatasetSchema]:
        """Fetch raw vacancies, parse details concurrently, normalize to one schema."""

        raw_vacancies = await self.fetch_vacancies()
        if not raw_vacancies:
            self.logger.info("No raw vacancies fetched")
            return []

        tasks = [self._parse_and_normalize(raw_vacancy) for raw_vacancy in raw_vacancies]
        parsed = await asyncio.gather(*tasks, return_exceptions=True)

        normalized: list[VacancyDatasetSchema] = []
        for item in parsed:
            if isinstance(item, Exception):
                self.logger.exception("Vacancy parse failed", exc_info=item)
                continue
            if item is not None:
                normalized.append(item)

        self.logger.info(
            "Collected %s normalized vacancies from %s raw items",
            len(normalized),
            len(raw_vacancies),
        )
        return normalized

    async def _parse_and_normalize(self, raw_vacancy: Any) -> VacancyDatasetSchema | None:
        async with self.parse_semaphore:
            parsed = await self.parse_vacancy(raw_vacancy)
            if parsed is None:
                return None
            return self.normalize_data(parsed)

    async def _request_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        response = await self._request("GET", url, params=params, headers=headers)
        return response.json() if response is not None else None

    async def _request_text(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> str | None:
        response = await self._request("GET", url, params=params, headers=headers)
        return response.text if response is not None else None

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response | None:
        last_error: Exception | None = None

        for attempt in range(1, self.request_retries + 2):
            await self.rate_limiter.acquire()
            try:
                response = await self.client.request(method, url, params=params, headers=headers)
                if response.status_code == 404:
                    self.logger.debug("404 for %s", response.url)
                    return None

                if response.status_code == 429 or response.status_code >= 500:
                    await self._sleep_before_retry(response, attempt)
                    continue

                if 400 <= response.status_code < 500:
                    self.logger.warning(
                        "Client error response: %s %s body=%s",
                        response.status_code,
                        response.url,
                        response.text[:1000],
                    )
                    return None

                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt > self.request_retries:
                    break
                await self._sleep_before_retry(None, attempt)

        self.logger.warning("Request failed after retries: %s params=%s error=%r", url, params, last_error)
        return None

    async def _sleep_before_retry(self, response: httpx.Response | None, attempt: int) -> None:
        retry_after = response.headers.get("Retry-After") if response is not None else None
        if retry_after and retry_after.isdigit():
            delay = float(retry_after)
        else:
            delay = min(30.0, 0.75 * (2 ** (attempt - 1)))
        await asyncio.sleep(delay)

    @staticmethod
    def deduplicate_by(items: Sequence[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        seen: set[Any] = set()
        unique: list[dict[str, Any]] = []
        for item in items:
            marker = item.get(key)
            if marker is None or marker in seen:
                continue
            seen.add(marker)
            unique.append(item)
        return unique

    @abstractmethod
    async def fetch_vacancies(self) -> list[Any]:
        """Fetch raw vacancy references from a source."""

    @abstractmethod
    async def parse_vacancy(self, raw_vacancy: Any) -> dict[str, Any] | None:
        """Parse one raw vacancy into source-specific normalized primitives."""

    @abstractmethod
    def normalize_data(self, parsed_vacancy: dict[str, Any]) -> VacancyDatasetSchema | None:
        """Convert parsed source data to VacancyDatasetSchema or skip it."""
