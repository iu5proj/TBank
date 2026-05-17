"""Deterministic final fallback for salary analysis.

This module is intentionally independent from the ML service. If the model
runner fails, times out, or emits non-JSON text, the backend can still return a
valid grounded answer based only on preflight vacancies and market_evidence.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.market_evidence import canonical_skill_key, decode_mojibake

ALLOWED_IMPACTS = {"low", "medium", "high"}
ALLOWED_RECOMMENDATION_TYPES = {
    "skill_gap",
    "experience_detail",
    "resume_clarity",
    "salary_expectation",
}


def build_grounded_fallback_output(input_payload: dict[str, Any], *, reason: str) -> dict[str, Any]:
    """Build a schema-valid salary result without asking an LLM."""
    vacancies = [item for item in input_payload.get("candidate_vacancies", []) if isinstance(item, dict)]
    used_ids = [str(item["id"]) for item in vacancies if item.get("id")]
    quantiles = _evidence_salary_quantiles(input_payload) or _salary_quantiles(vacancies, used_ids)
    profile = input_payload.get("profile") if isinstance(input_payload.get("profile"), dict) else {}
    profile_skills = _string_list(profile.get("skills"))
    profile_skill_keys = {canonical_skill_key(skill) for skill in profile_skills}
    skill_stats = _candidate_skill_stats(vacancies)
    matched_skills = [
        skill
        for skill in profile_skills
        if canonical_skill_key(skill) in skill_stats.display_by_key
    ]
    missing_skills = _missing_skills(input_payload, skill_stats, profile_skill_keys)
    recommendations = _recommendations(input_payload, missing_skills)
    factors = _factors(input_payload, vacancies, matched_skills, missing_skills)
    confidence_score = _confidence_score(len(used_ids))

    return {
        "request_hash": input_payload["request_hash"],
        "segment": {
            "segment_key": input_payload["segment"]["segment_key"],
            "segment_data_version": input_payload["segment"]["segment_data_version"],
        },
        "market_sample": {
            "candidate_vacancies_received": len(vacancies),
            "vacancies_used_for_estimation": len(used_ids),
            "used_vacancy_ids": used_ids,
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
            "level": _confidence_level(confidence_score),
            "reason": _fallback_reason(reason),
        },
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "factor_analysis": factors,
        "recommendations": recommendations,
    }


class _SkillStats:
    def __init__(self, counter: Counter[str], display_by_key: dict[str, str]) -> None:
        self.counter = counter
        self.display_by_key = display_by_key


def _market_evidence(input_payload: dict[str, Any]) -> dict[str, Any]:
    evidence = input_payload.get("market_evidence")
    return evidence if isinstance(evidence, dict) else {}


def _evidence_salary_quantiles(input_payload: dict[str, Any]) -> dict[str, int] | None:
    quantiles = _market_evidence(input_payload).get("salary_quantiles")
    if not isinstance(quantiles, dict):
        return None
    if not all(key in quantiles for key in ("p25", "p50", "p75")):
        return None
    p25 = _salary_amount(quantiles.get("p25"), 100_000)
    p50 = _salary_amount(quantiles.get("p50"), p25)
    p75 = _salary_amount(quantiles.get("p75"), p50)
    ordered = sorted([p25, p50, p75])
    return {"p25": ordered[0], "p50": ordered[1], "p75": ordered[2]}


def _salary_quantiles(vacancies: list[dict[str, Any]], used_ids: list[str]) -> dict[str, int]:
    used_id_set = set(used_ids)
    salaries = sorted(
        salary
        for salary in (
            _salary_midpoint(vacancy)
            for vacancy in vacancies
            if not used_id_set or str(vacancy.get("id")) in used_id_set
        )
        if salary > 0
    ) or [100_000]
    return {
        "p25": _percentile(salaries, 0.25),
        "p50": _percentile(salaries, 0.50),
        "p75": _percentile(salaries, 0.75),
    }


def _salary_midpoint(vacancy: dict[str, Any]) -> int:
    low = _positive_int(vacancy.get("salary_min_net"), 0)
    high = _positive_int(vacancy.get("salary_max_net"), 0)
    if low and high:
        return int((low + high) / 2)
    return low or high


def _percentile(values: list[int], q: float) -> int:
    if len(values) == 1:
        return values[0]
    index = round((len(values) - 1) * q)
    return values[index]


def _candidate_skill_stats(vacancies: list[dict[str, Any]]) -> _SkillStats:
    counter: Counter[str] = Counter()
    display_by_key: dict[str, str] = {}
    for vacancy in vacancies:
        seen_in_vacancy: set[str] = set()
        for skill in vacancy.get("skills_required") or []:
            key = canonical_skill_key(skill)
            if not key or key in seen_in_vacancy:
                continue
            seen_in_vacancy.add(key)
            counter[key] += 1
            display_by_key.setdefault(key, _display_skill(skill))
    return _SkillStats(counter=counter, display_by_key=display_by_key)


def _missing_skills(
    input_payload: dict[str, Any],
    skill_stats: _SkillStats,
    profile_skill_keys: set[str],
) -> list[dict[str, str]]:
    evidence_fit = _market_evidence(input_payload).get("resume_market_fit")
    raw_missing = evidence_fit.get("missing_skills") if isinstance(evidence_fit, dict) else []
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    if isinstance(raw_missing, list):
        for item in raw_missing:
            if not isinstance(item, dict):
                continue
            key = canonical_skill_key(item.get("skill"))
            if not key or key in seen or key in profile_skill_keys or key not in skill_stats.display_by_key:
                continue
            skill = skill_stats.display_by_key.get(key) or _display_skill(item.get("skill"))
            items.append(
                {
                    "skill": skill,
                    "impact": _impact(item.get("impact"), skill_stats.counter[key], len(skill_stats.counter)),
                    "reason": _text(
                        item.get("reason"),
                        f"{skill} встречается {_vacancy_phrase(skill_stats.counter[key])} в рыночной выборке.",
                    ),
                }
            )
            seen.add(key)
            if len(items) >= 5:
                return items

    for key, count in skill_stats.counter.most_common():
        if key in seen or key in profile_skill_keys:
            continue
        skill = skill_stats.display_by_key.get(key, _display_skill(key))
        items.append(
            {
                "skill": skill,
                "impact": _impact(None, count, len(skill_stats.counter)),
                "reason": f"{skill} встречается {_vacancy_phrase(count)} в рыночной выборке.",
            }
        )
        seen.add(key)
        if len(items) >= 5:
            break
    return items


def _recommendations(input_payload: dict[str, Any], missing_skills: list[dict[str, str]]) -> list[dict[str, Any]]:
    evidence_items = _market_evidence(input_payload).get("recommendation_candidates")
    recommendations: list[dict[str, Any]] = []
    if isinstance(evidence_items, list):
        for index, item in enumerate(evidence_items, start=1):
            if not isinstance(item, dict):
                continue
            recommendations.append(
                {
                    "priority": _positive_int(item.get("priority"), index),
                    "type": _recommendation_type(item.get("type")),
                    "title": _text(item.get("title"), "Усилить доказательность резюме"),
                    "resume_change": _text(
                        item.get("resume_change"),
                        "Добавьте конкретный проектный пример, если он отражает реальный опыт.",
                    ),
                    "expected_salary_effect": _optional_text(item.get("expected_salary_effect")),
                }
            )
            if len(recommendations) >= 5:
                return recommendations

    for index, item in enumerate(missing_skills[:5], start=1):
        skill = item["skill"]
        recommendations.append(
            {
                "priority": index,
                "type": "skill_gap",
                "title": f"Добавить подтверждение {skill}",
                "resume_change": (
                    f"Добавьте в резюме честный проектный пример с {skill}, "
                    "если такой опыт действительно есть."
                ),
                "expected_salary_effect": None,
            }
        )

    if recommendations:
        return recommendations

    return [
        {
            "priority": 1,
            "type": "experience_detail",
            "title": "Добавить измеримые результаты проектов",
            "resume_change": (
                "Опишите масштаб задач, нагрузку, бизнес-результат и технологии, "
                "которые реально использовались в проектах."
            ),
            "expected_salary_effect": None,
        }
    ]


def _factors(
    input_payload: dict[str, Any],
    vacancies: list[dict[str, Any]],
    matched_skills: list[str],
    missing_skills: list[dict[str, str]],
) -> list[dict[str, str]]:
    evidence = _market_evidence(input_payload)
    sample = evidence.get("sample") if isinstance(evidence.get("sample"), dict) else {}
    total = _positive_int(sample.get("total_vacancies"), len(vacancies))
    factors = [
        {
            "factor": "Рыночная выборка",
            "impact": "positive" if total >= 20 else "neutral",
            "explanation": (
                f"Зарплатная вилка рассчитана по {_vacancy_phrase(total)} "
                "из текущего сегмента и близких сегментов."
            ),
        }
    ]
    denominator = len(matched_skills) + len(missing_skills)
    if denominator:
        coverage = len(matched_skills) / denominator
        factors.append(
            {
                "factor": "Покрытие рыночных навыков",
                "impact": "positive" if coverage >= 0.6 else "negative",
                "explanation": f"Профиль закрывает {round(coverage * 100)}% видимых навыков в выборке.",
            }
        )
    return factors


def _fallback_reason(reason: str) -> str:
    detail = _human_reason(reason)
    return (
        "Модель не вернула валидный финальный JSON; "
        "показан расчет только по переданным вакансиям и market_evidence."
        + (f" {detail}" if detail else "")
    )


def _human_reason(reason: str) -> str:
    raw = decode_mojibake(" ".join(str(reason).split()))[:180]
    normalized = raw.casefold()
    if "timed out" in normalized or "timeout" in normalized or "таймаут" in normalized:
        return "Причина: таймаут локальной модели."
    if "no message content" in normalized or "thinking" in normalized:
        return "Причина: модель вернула reasoning/thinking без финального JSON."
    if "invalid json" in normalized or "невалид" in normalized:
        return "Причина: модель вернула невалидный JSON."
    if raw:
        return f"Причина: {raw}"
    return ""


def _confidence_score(vacancy_count: int) -> float:
    if vacancy_count >= 20:
        return 0.75
    if vacancy_count >= 5:
        return 0.55
    return 0.35


def _confidence_level(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _impact(value: Any, count: int, total_unique: int) -> str:
    text = str(value or "").strip().casefold()
    if text in ALLOWED_IMPACTS:
        return text
    share = count / max(1, total_unique)
    if share >= 0.5:
        return "high"
    if share >= 0.2:
        return "medium"
    return "low"


def _recommendation_type(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return text if text in ALLOWED_RECOMMENDATION_TYPES else "resume_clarity"


def _text(value: Any, default: str) -> str:
    text = decode_mojibake(str(value or "").strip())
    return text if text else default


def _optional_text(value: Any) -> str | None:
    text = _text(value, "")
    return text or None


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
    if amount < 10_000 and default >= 100_000:
        return amount * 1_000
    return amount


def _display_skill(value: Any) -> str:
    text = str(value or "").strip()
    return text.upper() if len(text) <= 3 else text.title()


def _vacancy_phrase(count: Any) -> str:
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
