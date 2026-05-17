# API-контракт

## Response envelope

Все основные ответы backend используют envelope:

```json
{
  "status": "success",
  "source": "gpt-oss-20b",
  "data": {},
  "code": null,
  "message": null,
  "validation_errors": null
}
```

При ошибке:

```json
{
  "status": "error",
  "source": null,
  "data": null,
  "code": "LLM_OUTPUT_VALIDATION_FAILED",
  "message": "The model did not return a payload that matches the expected JSON contract.",
  "validation_errors": ["..."]
}
```

## `GET /health`

Backend:

```bash
curl http://127.0.0.1:8000/health
```

Ответ:

```json
{"status":"ok","service":"zarabotok-backend"}
```

ML service:

```bash
curl http://127.0.0.1:8002/health
```

Ответ содержит режим модели:

```json
{
  "status": "ok",
  "service": "zarabotok-ml",
  "mode": "openai_compatible",
  "model": "gpt-oss:20b",
  "api_style": "ollama",
  "base_url": "http://ollama:11434/v1",
  "timeout_seconds": 25.0
}
```

## `POST /api/v1/analyze`

Основной endpoint анализа резюме.

Пример:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d @backend/tests/fixtures/analyze_python_backend_middle_force_refresh.json
```

Минимальная структура request:

```json
{
  "profile": {
    "title": "Python Backend Developer",
    "experience_years": 3,
    "location": "Москва",
    "skills": ["Python", "FastAPI", "PostgreSQL"],
    "resume_text": "Разрабатывал backend-сервисы на FastAPI",
    "current_salary": 150000
  },
  "options": {
    "target_salary": 250000,
    "force_refresh": true
  }
}
```

Основной `data` response:

```json
{
  "request_hash": "...",
  "segment": {
    "segment_key": "backend_developer:python:moscow:middle",
    "segment_data_version": "2026-05-17"
  },
  "market_sample": {
    "candidate_vacancies_received": 14,
    "vacancies_used_for_estimation": 14,
    "used_vacancy_ids": ["..."],
    "excluded_vacancies": [],
    "salary_quantiles": {
      "p25": 200000,
      "p50": 215000,
      "p75": 250000
    }
  },
  "salary_range": {
    "min": 200000,
    "median": 215000,
    "max": 250000,
    "currency": "RUB"
  },
  "confidence": {
    "score": 0.55,
    "level": "medium",
    "reason": "..."
  },
  "matched_skills": ["Python", "FastAPI", "PostgreSQL"],
  "missing_skills": [
    {
      "skill": "Kubernetes",
      "impact": "high",
      "reason": "Kubernetes встречается в 3 вакансиях..."
    }
  ],
  "factor_analysis": [
    {
      "factor": "Рыночная выборка",
      "impact": "neutral",
      "explanation": "..."
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "type": "skill_gap",
      "title": "Добавить подтверждение Kubernetes",
      "resume_change": "Добавьте в резюме честный проектный пример с Kubernetes.",
      "expected_salary_effect": "+35000 RUB к медиане выборки"
    }
  ]
}
```

## `POST /api/v1/parser/refresh`

Endpoint ручного refresh вакансий без полного salary-analysis.

Пример:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/parser/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "title": "Python Backend Developer",
      "experience_years": 3,
      "location": "Москва",
      "skills": ["Python", "FastAPI", "PostgreSQL"]
    },
    "sources": ["trudvsem", "fixture"],
    "dry_run": false
  }'
```

Используется для:

- прогрева сегмента перед демо;
- диагностики источников;
- проверки HH/Trudvsem/Habr без вызова модели.

## Валидационные правила

Backend требует:

- `request_hash` совпадает с input;
- `segment_key` и `segment_data_version` совпадают с input;
- все `used_vacancy_ids` взяты из `candidate_vacancies`;
- salary values являются полными monthly RUB integers;
- `p25 <= p50 <= p75`;
- `confidence.level` один из `low`, `medium`, `high`;
- `factor_analysis` и `recommendations` являются массивами объектов;
- `recommendations` не пустой.

