"""Model-service boundary for the GPT-OSS salary contract.

The service can run a deterministic local stub for tests or proxy /analyze to a
local model runner. All modes keep the same strict JSON contract for backend
idempotency, validation, storage and API behavior.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.schemas import Counterfactual, PredictionRequest, PredictionResponse

logger = logging.getLogger(__name__)

ROLE_BASE_SALARIES: dict[str, int] = {
    "junior": 50_000,
    "middle": 90_000,
    "senior": 150_000,
    "lead": 200_000,
    "default": 80_000,
}

LOCATION_MULTIPLIERS: dict[str, float] = {
    "РјРѕСЃРєРІР°": 1.3,
    "москва": 1.3,
    "moscow": 1.3,
    "Р СљР С•РЎРѓР С”Р Р†Р В°": 1.3,
    "remote": 1.1,
    "default": 0.8,
}

HIGH_VALUE_SKILLS: dict[str, int] = {
    "python": 10_000,
    "docker": 8_000,
    "kubernetes": 12_000,
    "aws": 15_000,
    "postgresql": 6_000,
    "kafka": 10_000,
    "typescript": 7_000,
    "react": 8_000,
}

EDUCATION_BONUS: dict[str, int] = {
    "none": 0,
    "bachelor": 5_000,
    "master": 12_000,
    "phd": 20_000,
}

SKILL_ALIASES: dict[str, str] = {
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "rest api": "rest",
    "rest": "rest",
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
}

SKILL_DISPLAY: dict[str, str] = {
    "aws": "AWS",
    "ci/cd": "CI/CD",
    "docker": "Docker",
    "fastapi": "FastAPI",
    "git": "Git",
    "go": "Go",
    "kafka": "Kafka",
    "kubernetes": "Kubernetes",
    "ml": "ML",
    "postgres": "Postgres",
    "postgresql": "PostgreSQL",
    "python": "Python",
    "react": "React",
    "rest": "REST",
    "spark": "Spark",
}

DEFAULT_ANALYZE_PROMPT = """
You are the core salary-analysis model for the Zarabotok service.

You receive one JSON object with request_hash, profile, segment,
candidate_vacancies, market_evidence and rules. Use only candidate_vacancies
and market_evidence as market evidence. Do not invent vacancies, salaries,
skills or external market facts.

Return exactly one JSON object and no markdown. The object must contain:
{
  "request_hash": "same as input",
  "segment": {
    "segment_key": "same as input",
    "segment_data_version": "same as input"
  },
  "market_sample": {
    "candidate_vacancies_received": 1,
    "vacancies_used_for_estimation": 1,
    "used_vacancy_ids": ["candidate vacancy id"],
    "excluded_vacancies": [{"id": "candidate vacancy id", "reason": "short reason"}],
    "salary_quantiles": {"p25": 1, "p50": 1, "p75": 1}
  },
  "salary_range": {"min": 1, "median": 1, "max": 1, "currency": "RUB"},
  "confidence": {"score": 0.0, "level": "low|medium|high", "reason": "short reason"},
  "matched_skills": ["skill from profile.skills"],
  "missing_skills": [{"skill": "skill from candidate vacancies", "impact": "low|medium|high", "reason": "..."}],
  "factor_analysis": [{"factor": "factor name", "impact": "positive|negative|neutral", "explanation": "..."}],
  "recommendations": [
    {
      "priority": 1,
      "type": "skill_gap|experience_detail|resume_clarity|salary_expectation",
      "title": "short title",
      "resume_change": "concrete resume edit",
      "expected_salary_effect": null
    }
  ]
}

request_hash, segment_key and segment_data_version must exactly match input.
Every used_vacancy_id or excluded_vacancies.id must come from candidate_vacancies.
Every matched or missing skill must come from profile.skills or vacancy skills.
confidence.level must be exactly one of: low, medium, high.
factor_analysis must be an array of objects, never a string or object.
recommendations must be an array of objects, never an array of strings.
All salary values must be monthly salaries in full RUB integers. Use 200000,
not 200, 200k, "200 тыс." or "200 thousand".
Use the maximum number of relevant and current candidate_vacancies. Do not
downsample the market evidence. Backend already filtered candidate_vacancies by
segment, salary presence, currency and freshness, so use all of them unless a
vacancy is clearly irrelevant to the profile.
If market_evidence is present, treat its salary_quantiles, resume_market_fit
and skill_pricing as precomputed facts. Prefer them over free-form reasoning.
Use Russian for human-readable reason, explanation, title and resume_change text.
""".strip()

COMPACT_ANALYZE_PROMPT = """
You are the Zarabotok salary-analysis model. Return exactly one compact JSON object.
Use only the input candidate_vacancies and market_evidence. Do not invent
vacancies, salaries, skills, or external market facts.

Backend will calculate request_hash, segment, market_sample, salary_range,
matched_skills and missing_skills from the input evidence. You only need to
return:
{
  "confidence": {"score": 0.55, "level": "medium", "reason": "..."},
  "factor_analysis": [{"factor": "...", "impact": "neutral", "explanation": "..."}],
  "recommendations": [{"priority": 1, "type": "skill_gap", "title": "...",
    "resume_change": "...", "expected_salary_effect": "..."}]
}

Start the assistant response with "{" and finish with "}". Do not write any
analysis, markdown, prose, code fences, or explanations outside the JSON object.

Rules:
- confidence.level: low, medium, or high.
- factor_analysis and recommendations must be arrays of objects.
- Prefer market_evidence salary_quantiles, resume_market_fit, and recommendations.
- Use Russian for reason, explanation, title, and resume_change.
- Keep the JSON short.
""".strip()


class StubPredictor:
    """Deterministic local substitute for the model-service boundary."""

    def predict(self, request: PredictionRequest) -> PredictionResponse:
        """Legacy /predict endpoint kept for old local scripts."""
        title_lower = request.job_title.casefold()
        base = ROLE_BASE_SALARIES["default"]
        for level, salary in ROLE_BASE_SALARIES.items():
            if level in title_lower:
                base = salary
                break

        multiplier = _location_multiplier(request.location)
        exp_bonus = int(request.experience_years * 10_000)
        edu_bonus = EDUCATION_BONUS.get(request.education_level, 0)

        shap_values: dict[str, float] = {}
        skill_total = 0
        user_skills_lower = {skill.casefold() for skill in request.skills}
        for skill in request.skills:
            bonus = HIGH_VALUE_SKILLS.get(skill.casefold(), 3_000)
            skill_total += bonus
            shap_values[f"skills:{skill}"] = float(bonus)

        shap_values["experience_years"] = float(exp_bonus)
        shap_values[f"location:{request.location}"] = float(int(base * (multiplier - 1)))
        shap_values[f"education:{request.education_level}"] = float(edu_bonus)

        p50 = int((base + exp_bonus + skill_total + edu_bonus) * multiplier)
        p25 = int(p50 * 0.75)
        p75 = int(p50 * 1.35)

        counterfactuals: list[Counterfactual] = []
        for skill_name, bonus in sorted(HIGH_VALUE_SKILLS.items(), key=lambda item: -item[1]):
            if skill_name not in user_skills_lower and len(counterfactuals) < 3:
                counterfactuals.append(
                    Counterfactual(
                        change_description=f"Add skill {skill_name.title()}",
                        feature_changed="skills",
                        new_value=skill_name.title(),
                        estimated_salary_increase=int(bonus * multiplier),
                    )
                )

        logger.info("Stub prediction: p50=%d for '%s'", p50, request.job_title)
        return PredictionResponse(
            p25_salary=p25,
            p50_salary=p50,
            p75_salary=p75,
            shap_values=shap_values,
            counterfactuals=counterfactuals,
        )

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a GPT-OSS-compatible JSON response for local development."""
        profile = payload["profile"]
        candidate_vacancies = payload["candidate_vacancies"]
        used_vacancies = candidate_vacancies

        salaries = sorted(_salary_midpoint(vacancy) for vacancy in used_vacancies)
        salaries = [salary for salary in salaries if salary > 0] or [100_000]
        p25 = _percentile(salaries, 0.25)
        p50 = _percentile(salaries, 0.50)
        p75 = _percentile(salaries, 0.75)

        profile_skills = {str(skill).casefold() for skill in profile.get("skills", [])}
        required_skills: list[str] = []
        for vacancy in used_vacancies:
            required_skills.extend(vacancy.get("skills_required") or [])

        matched_skills: list[str] = []
        missing_skills: list[dict[str, str]] = []
        seen_required: set[str] = set()
        for skill in required_skills:
            normalized = str(skill).casefold()
            if normalized in seen_required:
                continue
            seen_required.add(normalized)
            if normalized in profile_skills:
                matched_skills.append(str(skill))
            elif len(missing_skills) < 3:
                missing_skills.append(
                    {
                        "skill": str(skill),
                        "impact": "medium",
                        "reason": (
                            "Навык встречается в переданных модели вакансиях."
                        ),
                    }
                )

        recommendations = _recommendations(missing_skills)
        used_ids = [str(vacancy["id"]) for vacancy in used_vacancies]
        excluded: list[dict[str, str]] = []

        return {
            "request_hash": payload["request_hash"],
            "segment": {
                "segment_key": payload["segment"]["segment_key"],
                "segment_data_version": payload["segment"]["segment_data_version"],
            },
            "market_sample": {
                "candidate_vacancies_received": len(candidate_vacancies),
                "vacancies_used_for_estimation": len(used_vacancies),
                "used_vacancy_ids": used_ids,
                "excluded_vacancies": excluded,
                "salary_quantiles": {"p25": p25, "p50": p50, "p75": p75},
            },
            "salary_range": {"min": p25, "median": p50, "max": p75, "currency": "RUB"},
            "confidence": {
                "score": min(0.9, 0.45 + len(used_vacancies) / 100),
                "level": "medium" if len(used_vacancies) < 20 else "high",
                "reason": (
                    f"Локальный stub использовал {_vacancy_count_phrase(len(used_vacancies))}."
                ),
            },
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "factor_analysis": [
                {
                    "factor": f"Experience: {profile.get('experience_years')} years",
                    "impact": "neutral",
                    "explanation": (
                        "Локальный stub; финальная интерпретация "
                        "остается за gpt-oss-20b."
                    ),
                }
            ],
            "recommendations": recommendations,
        }


class ModelRunnerError(RuntimeError):
    """Raised when a configured real model runner cannot return usable JSON."""


@dataclass(frozen=True)
class CandidateSkillStats:
    counter: Counter[str]
    display_by_key: dict[str, str]
    vacancy_count: int


class OpenAICompatibleAnalyzer:
    """Adapter for local gpt-oss runners exposing OpenAI or Ollama chat APIs."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model_name: str,
        api_style: str,
        timeout: float,
        max_tokens: int,
        num_ctx: int,
        temperature: float,
        reasoning_effort: str,
        json_mode: bool,
        prompt_path: str,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.api_style = api_style
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.json_mode = json_mode
        self.prompt_path = prompt_path

    async def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send the prepared salary-analysis payload to a real model runner."""
        candidate_count = len(payload.get("candidate_vacancies") or [])
        logger.info(
            "Calling model=%s at %s with %d candidate vacancies",
            self.model_name,
            self.base_url,
            candidate_count,
        )
        started_at = time.monotonic()
        progress_task = asyncio.create_task(_model_call_progress(self.model_name, started_at))
        if self.api_style == "ollama":
            body = self._ollama_generate_body(payload)
            url = f"{_strip_v1_suffix(self.base_url)}/api/generate"
        else:
            body = self._openai_chat_body(payload)
            url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        raw_error: str | None = None
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=body)
                raw_error = response.text
                response.raise_for_status()
                envelope = response.json()
        except httpx.TimeoutException as exc:
            elapsed = time.monotonic() - started_at
            logger.exception("OpenAI-compatible model call timed out after %.1fs", elapsed)
            if self.api_style == "ollama":
                return _fallback_analyze_output(payload, reason=f"таймаут вызова модели через {elapsed:.1f} с")
            raise ModelRunnerError(f"OpenAI-compatible model call timed out after {elapsed:.1f}s") from exc
        except httpx.HTTPStatusError as exc:
            logger.exception("OpenAI-compatible model returned HTTP %s: %s", exc.response.status_code, raw_error)
            if self.api_style == "ollama":
                return _fallback_analyze_output(
                    payload,
                    reason=f"локальный runner модели вернул HTTP {exc.response.status_code}",
                )
            raise ModelRunnerError(
                f"OpenAI-compatible model returned HTTP {exc.response.status_code}: {raw_error}"
            ) from exc
        except ValueError as exc:
            logger.exception("OpenAI-compatible model returned invalid response JSON: %s", exc)
            if self.api_style == "ollama":
                return _fallback_analyze_output(payload, reason="локальный runner модели вернул невалидный JSON")
            raise ModelRunnerError(f"OpenAI-compatible model returned invalid response JSON: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.exception("OpenAI-compatible model call failed: %s", exc)
            if self.api_style == "ollama":
                return _fallback_analyze_output(payload, reason="локальный runner модели недоступен")
            raise ModelRunnerError(f"OpenAI-compatible model call failed: {exc}") from exc
        finally:
            progress_task.cancel()

        try:
            content = _extract_message_content(envelope, api_style=self.api_style)
            parsed_output = _parse_json_object(content)
        except ModelRunnerError as exc:
            if self.api_style == "ollama":
                logger.warning("Using grounded fallback because model returned no valid final JSON: %s", exc)
                return _fallback_analyze_output(payload, reason=str(exc))
            raise

        normalized = _normalize_analyze_output(payload, parsed_output)
        elapsed = time.monotonic() - started_at
        logger.info(
            "Model call finished in %.1fs; used %d/%d vacancies",
            elapsed,
            normalized["market_sample"]["vacancies_used_for_estimation"],
            normalized["market_sample"]["candidate_vacancies_received"],
        )
        return normalized

    def _openai_chat_body(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model": self.model_name,
            "messages": _messages(payload, self.prompt_path),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        return body

    def _ollama_generate_body(self, payload: dict[str, Any]) -> dict[str, Any]:
        compact_payload = _compact_model_payload(payload)
        messages = _messages(compact_payload, self.prompt_path, compact=True)
        prompt = (
            f"{messages[0]['content']}\n\n"
            "Input JSON:\n"
            f"{messages[1]['content']}\n\n"
            "Return only the compact JSON object."
        )
        logger.info(
            "Prepared compact Ollama generate request: prompt_chars=%d payload_chars=%d vacancies=%d num_ctx=%d",
            len(messages[0]["content"]),
            len(messages[1]["content"]),
            len(compact_payload.get("candidate_vacancies") or []),
            self.num_ctx,
        )
        body = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "raw": True,
            "think": _ollama_think_value(self.reasoning_effort),
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
                "num_ctx": self.num_ctx,
            },
        }
        if self.json_mode:
            body["format"] = "json"
        return body


class ConfigurablePredictor:
    """Stable service facade: legacy /predict is stub, /analyze can use a real runner."""

    def __init__(self) -> None:
        self.stub = StubPredictor()
        self.mode = settings.predictor_mode
        self.model_name = "stub"
        self.openai: OpenAICompatibleAnalyzer | None = None

        if self.mode == "openai_compatible":
            self.model_name = settings.openai_model_name
            self.openai = OpenAICompatibleAnalyzer(
                base_url=settings.openai_base_url,
                api_key=settings.openai_api_key,
                model_name=settings.openai_model_name,
                api_style=settings.openai_api_style,
                timeout=settings.openai_timeout,
                max_tokens=settings.openai_max_tokens,
                num_ctx=settings.openai_num_ctx,
                temperature=settings.openai_temperature,
                reasoning_effort=settings.openai_reasoning_effort,
                json_mode=settings.openai_json_mode,
                prompt_path=settings.prompt_path,
            )
        elif self.mode != "stub":
            logger.warning("Unknown ML_PREDICTOR_MODE=%s; falling back to stub", self.mode)
            self.mode = "stub"

    def predict(self, request: PredictionRequest) -> PredictionResponse:
        return self.stub.predict(request)

    async def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.openai is not None:
            return await self.openai.analyze(payload)
        return self.stub.analyze(payload)


async def _model_call_progress(model_name: str, started_at: float) -> None:
    while True:
        await asyncio.sleep(15)
        elapsed = time.monotonic() - started_at
        logger.info("Still waiting for model=%s response; elapsed=%.0fs", model_name, elapsed)


def _messages(payload: dict[str, Any], prompt_path: str, *, compact: bool = False) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _load_prompt(prompt_path, compact=compact)},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def _compact_model_payload(payload: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "request_hash": payload.get("request_hash"),
        "profile": _compact_profile(payload.get("profile")),
        "segment": _compact_segment(payload.get("segment")),
        "candidate_vacancies": [
            _compact_vacancy(vacancy)
            for vacancy in payload.get("candidate_vacancies") or []
            if isinstance(vacancy, dict)
        ],
    }
    evidence = payload.get("market_evidence")
    if isinstance(evidence, dict):
        compact["market_evidence"] = _compact_market_evidence(evidence)
    return compact


def _compact_profile(profile: Any) -> dict[str, Any]:
    if not isinstance(profile, dict):
        return {}
    keep = ("title", "experience_years", "location", "skills", "resume_text", "current_salary")
    compact = {key: profile.get(key) for key in keep if profile.get(key) not in (None, "", [])}
    skills = compact.get("skills")
    if isinstance(skills, list):
        compact["skills"] = [str(skill)[:40] for skill in skills[:24]]
    if isinstance(compact.get("resume_text"), str):
        compact["resume_text"] = compact["resume_text"][:700]
    return compact


def _compact_segment(segment: Any) -> dict[str, Any]:
    if not isinstance(segment, dict):
        return {}
    keep = ("segment_key", "segment_data_version")
    return {key: segment.get(key) for key in keep if segment.get(key) not in (None, "")}


def _compact_vacancy(vacancy: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "id",
        "title",
        "salary_min_net",
        "salary_max_net",
        "skills_required",
    )
    compact = {key: vacancy.get(key) for key in keep if vacancy.get(key) not in (None, "", [])}
    skills = compact.get("skills_required")
    if isinstance(skills, list):
        compact["skills_required"] = [str(skill)[:40] for skill in skills[:10]]
    return compact


def _compact_market_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    sample = evidence.get("sample")
    if isinstance(sample, dict):
        compact["sample"] = {
            key: sample.get(key)
            for key in ("total_vacancies", "target_segment_vacancies", "adjacent_segment_vacancies")
            if sample.get(key) is not None
        }
    if isinstance(evidence.get("salary_quantiles"), dict):
        compact["salary_quantiles"] = evidence["salary_quantiles"]

    fit = evidence.get("resume_market_fit")
    if isinstance(fit, dict):
        compact_fit: dict[str, Any] = {}
        if isinstance(fit.get("matched_skills"), list):
            compact_fit["matched_skills"] = [str(skill)[:40] for skill in fit["matched_skills"][:12]]
        if fit.get("coverage_score") is not None:
            compact_fit["coverage_score"] = fit["coverage_score"]
        if isinstance(fit.get("missing_skills"), list):
            compact_fit["missing_skills"] = [
                _compact_missing_skill(item)
                for item in fit["missing_skills"][:5]
                if isinstance(item, dict)
            ]
        compact["resume_market_fit"] = compact_fit

    if isinstance(evidence.get("skill_pricing"), list):
        compact["skill_pricing"] = [
            _compact_skill_pricing(item)
            for item in evidence["skill_pricing"][:5]
            if isinstance(item, dict)
        ]
    if isinstance(evidence.get("recommendation_candidates"), list):
        compact["recommendation_candidates"] = [
            _compact_recommendation(item)
            for item in evidence["recommendation_candidates"][:3]
            if isinstance(item, dict)
        ]
    return compact


def _compact_missing_skill(item: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "skill",
        "vacancy_count",
        "estimated_monthly_uplift_in_sample",
        "impact",
    )
    return {key: item.get(key) for key in keep if item.get(key) not in (None, "")}


def _compact_skill_pricing(item: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "skill",
        "vacancy_count",
        "median_salary_with_skill",
        "estimated_monthly_uplift_in_sample",
        "impact",
    )
    return {key: item.get(key) for key in keep if item.get(key) not in (None, "")}


def _compact_recommendation(item: dict[str, Any]) -> dict[str, Any]:
    keep = ("priority", "type", "title", "resume_change", "expected_salary_effect")
    compact = {key: item.get(key) for key in keep if item.get(key) not in (None, "")}
    for key in ("title", "resume_change", "expected_salary_effect"):
        if isinstance(compact.get(key), str):
            compact[key] = compact[key][:180]
    return compact

def _strip_v1_suffix(base_url: str) -> str:
    return base_url[:-3] if base_url.endswith("/v1") else base_url


def _ollama_think_value(reasoning_effort: str) -> bool | str:
    """Map config values to Ollama's native think parameter.

    For local live-review we prefer final JSON over visible reasoning. Ollama
    accepts boolean false to disable thinking, while some models also accept
    string effort levels.
    """
    value = (reasoning_effort or "").strip().lower()
    if value in {"", "0", "false", "no", "none", "off", "disabled"}:
        return False
    if value == "low":
        return False
    return value


def _location_multiplier(location: str) -> float:
    normalized = _decode_mojibake(str(location or "")).casefold().strip()
    direct = LOCATION_MULTIPLIERS.get(normalized)
    if direct is not None:
        return direct
    if "moscow" in normalized or "москва" in normalized:
        return 1.3
    if "remote" in normalized:
        return 1.1
    return LOCATION_MULTIPLIERS["default"]


def _decode_mojibake(value: str) -> str:
    try:
        repaired = value.encode("cp1251").decode("utf-8")
    except UnicodeError:
        return value
    return repaired if repaired else value


def _extract_message_content(envelope: dict[str, Any], *, api_style: str = "openai") -> str:
    if api_style == "ollama":
        generated = envelope.get("response")
        if isinstance(generated, str) and generated.strip():
            return generated
        thinking = envelope.get("thinking")
        if isinstance(thinking, str):
            thinking_json = _extract_first_json_object(thinking)
            if thinking_json:
                return thinking_json
        message = envelope.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(message, dict):
            message_thinking = message.get("thinking")
            if isinstance(message_thinking, str):
                thinking_json = _extract_first_json_object(message_thinking)
                if thinking_json:
                    return thinking_json
        if not isinstance(content, str) or not content.strip():
            preview = json.dumps(envelope, ensure_ascii=False)[:1000]
            raise ModelRunnerError(f"ollama response has no message content: {preview}")
        return content

    choices = envelope.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ModelRunnerError("model response has no choices")
    first_choice = choices[0]
    message = first_choice.get("message") if isinstance(first_choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ModelRunnerError("model response has no message content")
    return content


def _parse_json_object(content: str) -> dict[str, Any]:
    cleaned = _strip_code_fence(content.strip())
    try:
        parsed = json.loads(cleaned)
    except ValueError as exc:
        extracted = _extract_first_json_object(cleaned)
        if extracted is None:
            raise ModelRunnerError("model returned invalid JSON content") from exc
        try:
            parsed = json.loads(extracted)
        except ValueError as nested_exc:
            raise ModelRunnerError("model returned invalid JSON content") from nested_exc

    if not isinstance(parsed, dict):
        raise ModelRunnerError("model returned non-object JSON content")
    return parsed


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


def _load_prompt(prompt_path: str, *, compact: bool = False) -> str:
    if prompt_path:
        return Path(prompt_path).read_text(encoding="utf-8")
    if compact:
        return COMPACT_ANALYZE_PROMPT
    return DEFAULT_ANALYZE_PROMPT


def _normalize_analyze_output(input_payload: dict[str, Any], model_output: dict[str, Any]) -> dict[str, Any]:
    """Repair common LLM formatting drift without changing the input evidence set."""
    output = dict(model_output)
    vacancies = input_payload.get("candidate_vacancies") or []
    vacancy_ids = [str(vacancy.get("id")) for vacancy in vacancies if vacancy.get("id")]
    vacancy_id_set = set(vacancy_ids)

    output["request_hash"] = input_payload["request_hash"]
    output["segment"] = {
        "segment_key": input_payload["segment"]["segment_key"],
        "segment_data_version": input_payload["segment"]["segment_data_version"],
    }

    output["market_sample"] = _normalize_market_sample(output.get("market_sample"), vacancies, vacancy_ids)
    raw_matched_skills = output.get("matched_skills")
    raw_missing_skills = output.get("missing_skills")
    raw_recommendations = output.get("recommendations")
    output["confidence"] = _normalize_confidence(output.get("confidence"))
    output["factor_analysis"] = _normalize_factors(output.get("factor_analysis"), input_payload)

    used_ids = [item for item in output["market_sample"]["used_vacancy_ids"] if item in vacancy_id_set]
    if not used_ids:
        used_ids = vacancy_ids[: min(5, len(vacancy_ids))]
    if len(used_ids) < len(vacancy_ids):
        used_ids = _expand_used_vacancies(used_ids, vacancies, input_payload)
    output["market_sample"]["used_vacancy_ids"] = used_ids
    output["market_sample"]["vacancies_used_for_estimation"] = len(used_ids)
    output["market_sample"]["salary_quantiles"] = _salary_quantiles_from_vacancies(vacancies, used_ids)
    output["salary_range"] = _normalize_salary_range(
        output.get("salary_range"),
        output["market_sample"]["salary_quantiles"],
    )
    output["matched_skills"] = _normalize_matched_skills(raw_matched_skills, input_payload, used_ids)
    output["missing_skills"] = _normalize_missing_skills(raw_missing_skills, input_payload, used_ids)
    output["recommendations"] = _normalize_recommendations(
        raw_recommendations,
        output["missing_skills"],
        input_payload,
    )

    used_id_set = set(used_ids)
    excluded = []
    seen_excluded: set[str] = set()
    for item in output["market_sample"].get("excluded_vacancies") or []:
        vacancy_id = str(item.get("id")) if isinstance(item, dict) else str(item)
        if vacancy_id not in vacancy_id_set or vacancy_id in used_id_set or vacancy_id in seen_excluded:
            continue
        reason = item.get("reason") if isinstance(item, dict) else None
        excluded.append({"id": vacancy_id, "reason": _clean_text(reason, "Не выбрано моделью.")})
        seen_excluded.add(vacancy_id)
    for vacancy_id in vacancy_ids:
        if vacancy_id not in used_id_set and vacancy_id not in seen_excluded:
            excluded.append({"id": vacancy_id, "reason": "Не выбрано моделью."})
            seen_excluded.add(vacancy_id)
    output["market_sample"]["excluded_vacancies"] = excluded
    return output


def _fallback_analyze_output(input_payload: dict[str, Any], *, reason: str) -> dict[str, Any]:
    """Build a deterministic grounded response when Ollama emits thinking only."""
    vacancies = [vacancy for vacancy in input_payload.get("candidate_vacancies") or [] if isinstance(vacancy, dict)]
    vacancy_ids = [str(vacancy.get("id")) for vacancy in vacancies if vacancy.get("id")]
    quantiles = _evidence_salary_quantiles(input_payload) or _salary_quantiles_from_vacancies(vacancies, vacancy_ids)
    confidence_score = 0.55 if len(vacancy_ids) >= 5 else 0.35
    raw_output = {
        "request_hash": input_payload["request_hash"],
        "segment": {
            "segment_key": input_payload["segment"]["segment_key"],
            "segment_data_version": input_payload["segment"]["segment_data_version"],
        },
        "market_sample": {
            "candidate_vacancies_received": len(vacancy_ids),
            "vacancies_used_for_estimation": len(vacancy_ids),
            "used_vacancy_ids": vacancy_ids,
            "excluded_vacancies": [],
            "salary_quantiles": quantiles,
        },
        "salary_range": {
            "min": quantiles["p25"],
            "median": quantiles["p50"],
            "max": quantiles["p75"],
            "currency": "RUB",
        },
        "confidence": {
            "score": confidence_score,
            "level": "medium" if confidence_score >= 0.5 else "low",
            "reason": _fallback_reason(reason),
        },
        "matched_skills": [],
        "missing_skills": [],
        "factor_analysis": [],
        "recommendations": [],
    }
    return _normalize_analyze_output(input_payload, raw_output)


def _fallback_reason(reason: str) -> str:
    short_reason = _human_fallback_detail(reason)
    if not short_reason:
        return (
            "Модель не вернула финальный JSON; "
            "использован расчет только по переданным вакансиям."
        )
    return (
        "Модель не вернула финальный JSON; "
        f"использован расчет только по переданным вакансиям. {short_reason}"
    )


def _human_fallback_detail(reason: str) -> str:
    raw = " ".join(str(reason).split())
    normalized = raw.casefold()
    if "таймаут" in normalized or "timed out" in normalized or "timeout" in normalized:
        return "Таймаут вызова локальной модели."
    if "no message content" in normalized:
        return "Модель вернула только thinking без финального JSON."
    if "invalid json" in normalized or "невалид" in normalized:
        return "Модель вернула невалидный JSON."
    if "http 5" in normalized:
        return "Локальный runner модели вернул серверную ошибку."
    return raw[:180]


def _normalize_market_sample(value: Any, vacancies: list[dict[str, Any]], vacancy_ids: list[str]) -> dict[str, Any]:
    market_sample = value if isinstance(value, dict) else {}
    used_ids = _string_list(market_sample.get("used_vacancy_ids"))
    if not used_ids:
        used_ids = vacancy_ids[: min(5, len(vacancy_ids))]

    quantiles = market_sample.get("salary_quantiles")
    if not isinstance(quantiles, dict):
        quantiles = {}
    fallback = _salary_quantiles_from_vacancies(vacancies, used_ids)
    p25 = _salary_amount(quantiles.get("p25"), fallback["p25"])
    p50 = _salary_amount(quantiles.get("p50"), fallback["p50"])
    p75 = _salary_amount(quantiles.get("p75"), fallback["p75"])
    p25, p50, p75 = sorted([p25, p50, p75])

    return {
        "candidate_vacancies_received": len(vacancy_ids),
        "vacancies_used_for_estimation": len(used_ids),
        "used_vacancy_ids": used_ids,
        "excluded_vacancies": market_sample.get("excluded_vacancies") or [],
        "salary_quantiles": {"p25": p25, "p50": p50, "p75": p75},
    }


def _normalize_salary_range(value: Any, quantiles: dict[str, int]) -> dict[str, Any]:
    salary_range = value if isinstance(value, dict) else {}
    low = _salary_amount(salary_range.get("min"), quantiles["p25"])
    median = _salary_amount(salary_range.get("median"), quantiles["p50"])
    high = _salary_amount(salary_range.get("max"), quantiles["p75"])
    low, median, high = sorted([low, median, high])
    return {"min": low, "median": median, "max": high, "currency": "RUB"}


def _normalize_confidence(value: Any) -> dict[str, Any]:
    confidence = value if isinstance(value, dict) else {}
    score = _float_between(confidence.get("score"), 0.65, minimum=0.0, maximum=1.0)
    return {
        "score": score,
        "level": _normalize_level(confidence.get("level"), score=score),
        "reason": _clean_text(confidence.get("reason"), "Model output normalized to the strict response schema."),
    }


def _normalize_matched_skills(
    value: Any,
    input_payload: dict[str, Any],
    used_ids: list[str] | None = None,
) -> list[str]:
    profile_skills = input_payload.get("profile", {}).get("skills") or []
    by_key = {_skill_key(skill): str(skill) for skill in profile_skills}
    matched = []
    for skill in _string_list(value):
        canonical = by_key.get(_skill_key(skill))
        if canonical and canonical not in matched:
            matched.append(canonical)
    if matched:
        return matched

    evidence_matched = _evidence_matched_skills(input_payload)
    for skill in evidence_matched:
        canonical = by_key.get(_skill_key(skill))
        if canonical and canonical not in matched:
            matched.append(canonical)
    if matched:
        return matched

    candidate_keys = _candidate_skill_stats(input_payload, used_ids).counter.keys()
    for skill in profile_skills:
        if _skill_key(skill) in candidate_keys:
            matched.append(str(skill))
    return matched


def _normalize_missing_skills(
    value: Any,
    input_payload: dict[str, Any],
    used_ids: list[str] | None = None,
) -> list[dict[str, str]]:
    stats = _candidate_skill_stats(input_payload, used_ids)
    profile_keys = {_skill_key(skill) for skill in input_payload.get("profile", {}).get("skills") or []}
    raw_items = value if isinstance(value, list) else []
    normalized = []
    seen: set[str] = set()
    for item in raw_items:
        if isinstance(item, dict):
            skill_value = item.get("skill") or item.get("name")
            reason = item.get("reason")
            impact = item.get("impact")
        else:
            skill_value = item
            reason = None
            impact = None
        skill_key = _skill_key(skill_value)
        skill = stats.display_by_key.get(skill_key)
        if not skill or skill_key in seen or skill_key in profile_keys:
            continue
        normalized.append(
            {
                "skill": skill,
                "impact": _normalize_level(impact),
                "reason": _clean_text(
                    reason,
                    "Навык встречается в переданных модели вакансиях.",
                ),
            }
        )
        seen.add(skill_key)
    if normalized:
        return normalized[:8]

    evidence_missing = _evidence_missing_skills(input_payload, stats, profile_keys)
    if evidence_missing:
        return evidence_missing[:8]

    total_used = max(1, stats.vacancy_count)
    for skill_key, count in stats.counter.most_common():
        if skill_key in profile_keys or skill_key in seen:
            continue
        skill = stats.display_by_key[skill_key]
        normalized.append(
            {
                "skill": skill,
                "impact": _skill_impact(count, total_used),
                "reason": (
                    f"Навык встречается {_vacancy_count_phrase(count)} "
                    f"из {total_used} использованных."
                ),
            }
        )
        seen.add(skill_key)
        if len(normalized) >= 6:
            break
    return normalized[:8]


def _normalize_factors(value: Any, input_payload: dict[str, Any] | None = None) -> list[dict[str, str]]:
    raw_items = value if isinstance(value, list) else [value] if value else []
    factors = []
    for item in raw_items:
        if isinstance(item, dict):
            factor = item.get("factor") or item.get("name") or item.get("title")
            impact = item.get("impact")
            explanation = item.get("explanation") or item.get("reason")
        else:
            factor = "Model factor"
            impact = "neutral"
            explanation = item
        factors.append(
            {
                "factor": _clean_text(factor, "Рынок и профиль"),
                "impact": _normalize_factor_impact(impact),
                "explanation": _clean_text(
                    explanation,
                    "Модель учла этот фактор в оценке зарплаты.",
                ),
            }
        )
    evidence_factors = _evidence_factors(input_payload or {})
    if factors:
        if evidence_factors and _factors_are_generic(factors):
            return evidence_factors
        return factors

    if evidence_factors:
        return evidence_factors

    return [
        {
            "factor": "Рынок и профиль",
            "impact": "neutral",
            "explanation": "Модель не вернула детальный факторный анализ.",
        }
    ]


def _factors_are_generic(factors: list[dict[str, str]]) -> bool:
    generic_markers = (
        "market and profile fit",
        "model did not provide",
        "the model considered this factor",
        "relevant backend profile",
        "рыночные вакансии",
        "зарплатная вилка рассчитана по переданным вакансиям",
        "рынок и профиль",
    )
    for factor in factors:
        text = f"{factor.get('factor') or ''} {factor.get('explanation') or ''}".casefold()
        if not any(marker in text for marker in generic_markers):
            return False
    return True


def _normalize_recommendations(
    value: Any,
    missing_skills: list[dict[str, str]] | None = None,
    input_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    raw_items = value if isinstance(value, list) else [value] if value else []
    recommendations = []
    for index, item in enumerate(raw_items, start=1):
        if isinstance(item, dict):
            title = item.get("title") or item.get("recommendation") or item.get("resume_change")
            resume_change = item.get("resume_change") or item.get("description") or title
            item_type = _normalize_recommendation_type(item.get("type"))
            expected_salary_effect = item.get("expected_salary_effect")
        else:
            title = item
            resume_change = item
            item_type = "resume_clarity"
            expected_salary_effect = None
        recommendations.append(
            {
                "priority": _positive_int(item.get("priority"), index) if isinstance(item, dict) else index,
                "type": item_type,
                "title": _clean_text(title, "Усилить доказательность резюме"),
                "resume_change": _clean_text(
                    resume_change,
                    "Добавьте конкретный и честный проектный пример.",
                ),
                "expected_salary_effect": expected_salary_effect if expected_salary_effect else None,
            }
        )
    evidence_recommendations = _evidence_recommendations(input_payload or {})
    if recommendations:
        if evidence_recommendations and _recommendations_are_generic(recommendations):
            return evidence_recommendations
        return recommendations

    if evidence_recommendations:
        return evidence_recommendations

    if missing_skills:
        return [
            {
                "priority": index + 1,
                "type": "skill_gap",
                "title": f"Добавить подтверждение {item['skill']}",
                "resume_change": (
                    f"Добавьте честный проектный пример с {item['skill']}, "
                    "если он есть."
                ),
                "expected_salary_effect": None,
            }
            for index, item in enumerate(missing_skills[:3])
        ]

    return [
        {
            "priority": 1,
            "type": "experience_detail",
            "title": "Добавить измеримые результаты проектов",
            "resume_change": (
                "Опишите масштаб, нагрузку, бизнес-результат "
                "и использованные технологии."
            ),
            "expected_salary_effect": None,
        }
    ]


def _market_evidence(input_payload: dict[str, Any]) -> dict[str, Any]:
    evidence = input_payload.get("market_evidence")
    return evidence if isinstance(evidence, dict) else {}


def _evidence_salary_quantiles(input_payload: dict[str, Any]) -> dict[str, int] | None:
    quantiles = _market_evidence(input_payload).get("salary_quantiles")
    if not isinstance(quantiles, dict):
        return None
    if not all(key in quantiles for key in ("p25", "p50", "p75")):
        return None
    return {
        "p25": _positive_int(quantiles.get("p25"), 100_000),
        "p50": _positive_int(quantiles.get("p50"), 100_000),
        "p75": _positive_int(quantiles.get("p75"), 100_000),
    }


def _evidence_matched_skills(input_payload: dict[str, Any]) -> list[str]:
    fit = _market_evidence(input_payload).get("resume_market_fit")
    if not isinstance(fit, dict):
        return []
    return _string_list(fit.get("matched_skills"))


def _evidence_missing_skills(
    input_payload: dict[str, Any],
    stats: CandidateSkillStats,
    profile_keys: set[str],
) -> list[dict[str, str]]:
    fit = _market_evidence(input_payload).get("resume_market_fit")
    raw_items = fit.get("missing_skills") if isinstance(fit, dict) else []
    if not isinstance(raw_items, list):
        return []

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        key = _skill_key(item.get("skill"))
        if not key or key in seen or key in profile_keys:
            continue
        skill = stats.display_by_key.get(key) or _display_skill(item.get("skill"))
        count = _positive_int(item.get("vacancy_count"), stats.counter.get(key, 0))
        reason = _clean_text(
            item.get("reason"),
            _evidence_skill_reason(skill, count, item.get("estimated_monthly_uplift_in_sample")),
        )
        normalized.append(
            {
                "skill": skill,
                "impact": _normalize_level(item.get("impact")),
                "reason": reason,
            }
        )
        seen.add(key)
    return normalized


def _evidence_factors(input_payload: dict[str, Any]) -> list[dict[str, str]]:
    evidence = _market_evidence(input_payload)
    if not evidence:
        return []

    factors: list[dict[str, str]] = []
    sample = evidence.get("sample") if isinstance(evidence.get("sample"), dict) else {}
    total = _positive_int(sample.get("total_vacancies"), 0)
    adjacent = _positive_int(sample.get("adjacent_segment_vacancies"), 0)
    if total:
        factors.append(
            {
                "factor": "Рыночная выборка",
                "impact": "positive" if total >= 20 else "neutral",
                "explanation": (
                    f"Зарплатная вилка рассчитана по {_vacancy_count_phrase(total)}; "
                    f"{adjacent} из них относятся к близким смежным сегментам."
                ),
            }
        )

    fit = evidence.get("resume_market_fit") if isinstance(evidence.get("resume_market_fit"), dict) else {}
    coverage = _float_between(fit.get("coverage_score"), 0.0, minimum=0.0, maximum=1.0)
    if coverage:
        factors.append(
            {
                "factor": "Покрытие рыночных навыков",
                "impact": "positive" if coverage >= 0.6 else "negative",
                "explanation": (
                    f"Резюме покрывает {round(coverage * 100)}% "
                    "самых заметных навыков выборки."
                ),
            }
        )

    missing = fit.get("missing_skills") if isinstance(fit.get("missing_skills"), list) else []
    top_missing = missing[0] if missing and isinstance(missing[0], dict) else None
    if top_missing:
        uplift = _positive_int(top_missing.get("estimated_monthly_uplift_in_sample"), 0)
        factors.append(
            {
                "factor": f"Пробел в навыках: {_display_skill(top_missing.get('skill'))}",
                "impact": "negative",
                "explanation": _evidence_skill_reason(
                    top_missing.get("skill"),
                    top_missing.get("vacancy_count"),
                    uplift,
                ),
            }
        )
    return factors


def _evidence_recommendations(input_payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = _market_evidence(input_payload).get("recommendation_candidates")
    if not isinstance(raw_items, list):
        return []

    recommendations: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items[:5], start=1):
        if not isinstance(item, dict):
            continue
        recommendations.append(
            {
                "priority": _positive_int(item.get("priority"), index),
                "type": _normalize_recommendation_type(item.get("type")),
                "title": _clean_text(item.get("title"), "Усилить доказательность резюме"),
                "resume_change": _clean_text(
                    item.get("resume_change"),
                    "Добавьте конкретный проектный пример.",
                ),
                "expected_salary_effect": item.get("expected_salary_effect") or None,
            }
        )
    return recommendations


def _recommendations_are_generic(recommendations: list[dict[str, Any]]) -> bool:
    generic_markers = (
        "improve resume evidence",
        "add measurable project evidence",
        "add concrete, truthful project evidence",
        "усилить доказательность резюме",
        "добавить измеримые результаты проектов",
        "добавьте конкретный",
    )
    for recommendation in recommendations:
        title = str(recommendation.get("title") or "").casefold()
        resume_change = str(recommendation.get("resume_change") or "").casefold()
        if not any(marker in title or marker in resume_change for marker in generic_markers):
            return False
    return True


def _evidence_skill_reason(skill: Any, vacancy_count: Any, uplift: Any) -> str:
    count = _positive_int(vacancy_count, 0)
    uplift_amount = _positive_int(uplift, 0)
    skill_name = _display_skill(skill)
    if uplift_amount > 0 and count > 0:
        return (
            f"{skill_name} встречается {_vacancy_count_phrase(count)} "
            f"с +{uplift_amount} RUB к медиане выборки."
        )
    if count > 0:
        return (
            f"{skill_name} встречается {_vacancy_count_phrase(count)} "
            "текущей рыночной выборки."
        )
    return f"{skill_name} встречается в текущей рыночной выборке."


def _vacancy_count_phrase(count: Any) -> str:
    value = _positive_int(count, 0)
    word = _russian_plural(value, "вакансии", "вакансиях", "вакансиях")
    return f"в {value} {word}"


def _russian_plural(value: int, one: str, few: str, many: str) -> str:
    value = abs(value)
    if 11 <= value % 100 <= 14:
        return many
    if value % 10 == 1:
        return one
    if 2 <= value % 10 <= 4:
        return few
    return many


def _salary_quantiles_from_vacancies(vacancies: list[dict[str, Any]], used_ids: list[str]) -> dict[str, int]:
    used_id_set = set(used_ids)
    salaries = [
        _salary_midpoint(vacancy)
        for vacancy in vacancies
        if not used_id_set or str(vacancy.get("id")) in used_id_set
    ]
    salaries = sorted(salary for salary in salaries if salary > 0) or [100_000]
    return {
        "p25": _percentile(salaries, 0.25),
        "p50": _percentile(salaries, 0.50),
        "p75": _percentile(salaries, 0.75),
    }


def _expand_used_vacancies(
    used_ids: list[str],
    vacancies: list[dict[str, Any]],
    input_payload: dict[str, Any],
) -> list[str]:
    selected = list(dict.fromkeys(used_ids))
    selected_set = set(selected)
    profile = input_payload.get("profile", {})
    profile_terms = {
        item.casefold()
        for item in [
            profile.get("title"),
            profile.get("location"),
            *(profile.get("skills") or []),
        ]
        if item
    }

    ranked = sorted(
        vacancies,
        key=lambda vacancy: _vacancy_relevance_score(vacancy, profile_terms),
        reverse=True,
    )
    for vacancy in ranked:
        vacancy_id = str(vacancy.get("id"))
        if not vacancy_id or vacancy_id in selected_set:
            continue
        selected.append(vacancy_id)
        selected_set.add(vacancy_id)
    return selected


def _vacancy_relevance_score(vacancy: dict[str, Any], profile_terms: set[str]) -> int:
    skills = {str(skill).casefold() for skill in vacancy.get("skills_required") or []}
    title = str(vacancy.get("title") or "").casefold()
    score = len(skills & profile_terms) * 10
    score += sum(1 for term in profile_terms if term and term in title)
    if _salary_midpoint(vacancy) > 0:
        score += 1
    return score


def _candidate_skill_stats(
    input_payload: dict[str, Any],
    used_ids: list[str] | None,
) -> CandidateSkillStats:
    used_id_set = set(used_ids or [])
    counter: Counter[str] = Counter()
    display_by_key: dict[str, str] = {}
    vacancy_count = 0
    for vacancy in input_payload.get("candidate_vacancies") or []:
        vacancy_id = str(vacancy.get("id"))
        if used_id_set and vacancy_id not in used_id_set:
            continue
        vacancy_count += 1
        seen_in_vacancy: set[str] = set()
        for skill in vacancy.get("skills_required") or []:
            key = _skill_key(skill)
            if not key or key in seen_in_vacancy:
                continue
            seen_in_vacancy.add(key)
            counter[key] += 1
            display_by_key.setdefault(key, _display_skill(skill))
    return CandidateSkillStats(counter=counter, display_by_key=display_by_key, vacancy_count=vacancy_count)


def _skill_key(value: Any) -> str:
    key = " ".join(str(value or "").strip().casefold().split())
    if not key:
        return ""
    key = key.replace("cicd", "ci/cd")
    return SKILL_ALIASES.get(key, key)


def _display_skill(value: Any) -> str:
    text = str(value or "").strip()
    key = _skill_key(text)
    return SKILL_DISPLAY.get(key, text.upper() if len(text) <= 3 else text.title())


def _skill_impact(count: int, total: int) -> str:
    share = count / max(1, total)
    if share >= 0.5:
        return "high"
    if share >= 0.2:
        return "medium"
    return "low"


def _normalize_level(value: Any, *, score: float | None = None) -> str:
    text = str(value or "").strip().casefold()
    if text in {"low", "низкий", "низкая", "низкое"}:
        return "low"
    if text in {"high", "высокий", "высокая", "высокое"}:
        return "high"
    if text in {"medium", "средний", "средняя", "среднее"}:
        return "medium"
    if score is not None:
        if score < 0.4:
            return "low"
        if score >= 0.75:
            return "high"
    return "medium"


def _normalize_factor_impact(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if text in {"positive", "положительный", "положительная", "+"}:
        return "positive"
    if text in {"negative", "отрицательный", "отрицательная", "-"}:
        return "negative"
    return "neutral"


def _normalize_recommendation_type(value: Any) -> str:
    text = str(value or "").strip().casefold()
    allowed = {"skill_gap", "experience_detail", "resume_clarity", "salary_expectation"}
    return text if text in allowed else "resume_clarity"


def _clean_text(value: Any, default: str) -> str:
    text = str(value or "").strip()
    return text if text else default


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = default
    return parsed if parsed > 0 else default


def _salary_amount(value: Any, default: int) -> int:
    amount = _positive_int(value, default)
    if amount < 1_000 and default >= 50_000:
        return amount * 1_000
    if amount < 10_000 and default >= 100_000:
        return amount * 1_000
    return amount


def _float_between(value: Any, default: float, *, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _recommendations(missing_skills: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not missing_skills:
        return [
            {
                "priority": 1,
                "type": "experience_detail",
                "title": "Добавить измеримые результаты проектов",
                "resume_change": (
                    "Опишите масштаб, нагрузку, бизнес-результат "
                    "и использованные технологии."
                ),
                "expected_salary_effect": None,
            }
        ]

    return [
        {
            "priority": index + 1,
            "type": "skill_gap",
            "title": f"Добавить подтверждение {item['skill']}",
            "resume_change": (
                f"Добавьте {item['skill']} только при наличии "
                "реального проектного опыта."
            ),
            "expected_salary_effect": None,
        }
        for index, item in enumerate(missing_skills)
    ]


def _salary_midpoint(vacancy: dict[str, Any]) -> int:
    salary_min = vacancy.get("salary_min_net")
    salary_max = vacancy.get("salary_max_net")
    if salary_min and salary_max:
        return int((int(salary_min) + int(salary_max)) / 2)
    if salary_min:
        return int(salary_min)
    if salary_max:
        return int(salary_max)
    return 0


def _percentile(values: list[int], q: float) -> int:
    if len(values) == 1:
        return values[0]
    index = round((len(values) - 1) * q)
    return values[index]


predictor = ConfigurablePredictor()
