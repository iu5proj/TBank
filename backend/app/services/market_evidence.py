"""Deterministic market evidence derived from candidate vacancies.

This module does not call an LLM and does not use external salary knowledge.
It prepares compact facts that are cheap to compute and easy for the model to
interpret during a live request.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median
from typing import Any

from app.schemas.analyze import CandidateVacancy, ResumeProfile

SKILL_ALIASES: dict[str, str] = {
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "rest api": "rest",
    "rest": "rest",
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
    "golang": "go",
}

SKILL_DISPLAY: dict[str, str] = {
    "aws": "AWS",
    "ci/cd": "CI/CD",
    "django": "Django",
    "docker": "Docker",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "git": "Git",
    "go": "Go",
    "graphql": "GraphQL",
    "java": "Java",
    "kafka": "Kafka",
    "kubernetes": "Kubernetes",
    "ml": "ML",
    "postgresql": "PostgreSQL",
    "python": "Python",
    "redis": "Redis",
    "rest": "REST",
    "spark": "Spark",
    "sqlalchemy": "SQLAlchemy",
    "typescript": "TypeScript",
}

RELATED_SPECIALIZATIONS: dict[str, tuple[str, ...]] = {
    "python": ("django", "fastapi", "backend", "go", "java"),
    "java": ("backend", "go", "python"),
    "go": ("backend", "java", "python"),
    "react": ("typescript", "javascript", "frontend"),
    "typescript": ("react", "javascript", "frontend"),
    "machine_learning": ("data", "python", "ml"),
}


def build_candidate_segment_keys(segment_key: str) -> list[str]:
    """Return target and close adjacent segment keys for vacancy retrieval."""
    parts = segment_key.split(":")
    if len(parts) != 4:
        return [segment_key]

    role_cluster, specialization, region, experience_bucket = parts
    keys = [segment_key]
    for related in RELATED_SPECIALIZATIONS.get(specialization, ()):
        related_key = f"{role_cluster}:{related}:{region}:{experience_bucket}"
        if related_key not in keys:
            keys.append(related_key)
    return keys


def canonical_skill_key(value: Any) -> str:
    key = " ".join(str(value or "").strip().casefold().split())
    if not key:
        return ""
    key = key.replace("cicd", "ci/cd")
    return SKILL_ALIASES.get(key, key)


def decode_mojibake(value: str) -> str:
    """Repair UTF-8 text that was accidentally decoded as cp1251."""
    try:
        repaired = value.encode("cp1251").decode("utf-8")
    except UnicodeError:
        return value
    return repaired if repaired else value


def build_market_evidence(
    *,
    profile: ResumeProfile,
    target_segment_key: str,
    candidate_segment_keys: list[str],
    candidate_vacancies: list[CandidateVacancy],
) -> dict[str, Any]:
    """Build deterministic salary, fit and skill-pricing facts."""
    vacancies = [vacancy for vacancy in candidate_vacancies if _salary_midpoint(vacancy) > 0]
    vacancy_ids = [vacancy.id for vacancy in vacancies]
    salary_midpoints = sorted(_salary_midpoint(vacancy) for vacancy in vacancies)
    quantiles = _salary_quantiles(salary_midpoints)
    baseline_median = quantiles["p50"]
    skill_salary_midpoints: dict[str, list[int]] = defaultdict(list)
    skill_display: dict[str, str] = {}
    skill_vacancy_counter: Counter[str] = Counter()

    for vacancy in vacancies:
        seen_in_vacancy: set[str] = set()
        midpoint = _salary_midpoint(vacancy)
        for skill in vacancy.skills_required or []:
            key = canonical_skill_key(skill)
            if not key or key in seen_in_vacancy:
                continue
            seen_in_vacancy.add(key)
            skill_salary_midpoints[key].append(midpoint)
            skill_vacancy_counter[key] += 1
            skill_display.setdefault(key, _display_skill(skill))

    profile_skill_keys = {canonical_skill_key(skill) for skill in profile.skills}
    matched_skills = [
        str(skill)
        for skill in profile.skills
        if canonical_skill_key(skill) in skill_vacancy_counter
    ]
    skill_pricing = _skill_pricing(
        skill_salary_midpoints=skill_salary_midpoints,
        skill_vacancy_counter=skill_vacancy_counter,
        skill_display=skill_display,
        baseline_median=baseline_median,
        total_vacancies=max(1, len(vacancies)),
    )
    missing_skills = [
        item
        for item in skill_pricing
        if canonical_skill_key(item["skill"]) not in profile_skill_keys
    ][:8]

    market_skill_keys = {canonical_skill_key(item["skill"]) for item in skill_pricing[:12]}
    covered_market_skills = len(profile_skill_keys & market_skill_keys)
    coverage_score = round(covered_market_skills / max(1, len(market_skill_keys)), 2)

    return {
        "strategy": "deterministic_precomputed_market_evidence",
        "target_segment_key": target_segment_key,
        "candidate_segment_keys": candidate_segment_keys,
        "sample": {
            "total_vacancies": len(vacancies),
            "target_segment_vacancies": sum(1 for vacancy in vacancies if vacancy.segment_key == target_segment_key),
            "adjacent_segment_vacancies": sum(1 for vacancy in vacancies if vacancy.segment_key != target_segment_key),
            "used_vacancy_ids": vacancy_ids,
        },
        "salary_quantiles": quantiles,
        "resume_market_fit": {
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "coverage_score": coverage_score,
        },
        "skill_pricing": skill_pricing,
        "recommendation_candidates": _recommendation_candidates(missing_skills),
    }


def _skill_pricing(
    *,
    skill_salary_midpoints: dict[str, list[int]],
    skill_vacancy_counter: Counter[str],
    skill_display: dict[str, str],
    baseline_median: int,
    total_vacancies: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, salaries in skill_salary_midpoints.items():
        if not salaries:
            continue
        skill_median = int(median(salaries))
        uplift = skill_median - baseline_median
        vacancy_count = skill_vacancy_counter[key]
        vacancy_share = round(vacancy_count / total_vacancies, 2)
        rows.append(
            {
                "skill": skill_display.get(key, _display_skill(key)),
                "vacancy_count": vacancy_count,
                "vacancy_share": vacancy_share,
                "median_salary_with_skill": skill_median,
                "estimated_monthly_uplift_in_sample": uplift,
                "impact": _skill_impact(vacancy_share, uplift),
            }
        )

    return sorted(
        rows,
        key=lambda item: (
            item["estimated_monthly_uplift_in_sample"],
            item["vacancy_share"],
            item["median_salary_with_skill"],
        ),
        reverse=True,
    )


def _recommendation_candidates(missing_skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    for index, skill in enumerate(missing_skills[:5], start=1):
        uplift = int(skill["estimated_monthly_uplift_in_sample"])
        effect = f"+{uplift} RUB к медиане выборки" if uplift > 0 else None
        recommendations.append(
            {
                "priority": index,
                "type": "skill_gap",
                "title": f"Добавить подтверждение {skill['skill']}",
                "resume_change": (
                    "Добавьте в резюме честный проектный "
                    f"пример с {skill['skill']}."
                ),
                "expected_salary_effect": effect,
                "market_reason": (
                    f"{skill['skill']} встречается {_vacancy_phrase(skill['vacancy_count'])}; "
                    f"медиана вакансий с навыком — {skill['median_salary_with_skill']} RUB."
                ),
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
                "Опишите масштаб, нагрузку, бизнес-результат "
                "и использованные технологии."
            ),
            "expected_salary_effect": None,
            "market_reason": (
                "Профиль уже покрывает самые сильные видимые "
                "навыки в рыночной выборке."
            ),
        }
    ]


def _salary_midpoint(vacancy: CandidateVacancy) -> int:
    return int((vacancy.salary_min_net + vacancy.salary_max_net) / 2)


def _salary_quantiles(values: list[int]) -> dict[str, int]:
    salaries = sorted(value for value in values if value > 0) or [100_000]
    return {
        "p25": _percentile(salaries, 0.25),
        "p50": _percentile(salaries, 0.50),
        "p75": _percentile(salaries, 0.75),
    }


def _percentile(values: list[int], q: float) -> int:
    if len(values) == 1:
        return values[0]
    index = round((len(values) - 1) * q)
    return values[index]


def _display_skill(value: Any) -> str:
    text = str(value or "").strip()
    key = canonical_skill_key(text)
    return SKILL_DISPLAY.get(key, text.upper() if len(text) <= 3 else text.title())


def _skill_impact(vacancy_share: float, uplift: int) -> str:
    if vacancy_share >= 0.45 or uplift >= 30_000:
        return "high"
    if vacancy_share >= 0.2 or uplift >= 10_000:
        return "medium"
    return "low"


def _vacancy_phrase(count: Any) -> str:
    value = int(count or 0)
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
