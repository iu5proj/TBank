from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VacancyDatasetSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="")
    salary_min_net: int | None = Field(default=None, gt=0)
    salary_max_net: int | None = Field(default=None, gt=0)
    skills_required: list[str] = Field(default_factory=list)
    location: str = Field(default="", max_length=1000)
    experience_range: str = Field(default="", max_length=255)
    source_url: str = Field(..., min_length=1, max_length=1000)

    @field_validator("description", "location", "experience_range", mode="before")
    @classmethod
    def none_to_empty_string(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @field_validator("skills_required", mode="before")
    @classmethod
    def normalize_skills(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]

        seen: set[str] = set()
        result: list[str] = []
        for item in value:
            skill = str(item).strip()
            if not skill:
                continue
            dedupe_key = skill.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            result.append(skill[:100])
        return result

    @field_validator("salary_max_net")
    @classmethod
    def check_salary_bounds(cls, max_val: int | None, info: Any) -> int | None:
        min_val = info.data.get("salary_min_net")
        if min_val is None and max_val is None:
            raise ValueError("At least one of salary_min_net or salary_max_net must be provided")
        if min_val is not None and max_val is not None and min_val > max_val:
            raise ValueError("salary_min_net cannot be greater than salary_max_net")
        return max_val
