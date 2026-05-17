# Zarabotok ML/RAG

Zarabotok - сервис оценки рыночной зарплаты по резюме. Пользователь заполняет
профиль, навыки, опыт и желаемую зарплату, а система возвращает зарплатную
вилку, уверенность оценки, факторы влияния и рекомендации по улучшению резюме.

Проект сделан как локальный full-stack контур: frontend, backend, база,
Redis-lock, ML-boundary и локальная gpt-oss модель работают вместе через
Docker Compose.

## Зачем это нужно

Обычная оценка зарплаты по резюме часто выглядит как одна условная цифра без
объяснений. Здесь результат строится иначе:

- берутся реальные или тестовые вакансии подходящего сегмента;
- backend заранее считает рыночные факты: квантили зарплат, совпавшие навыки,
  недостающие навыки и кандидаты рекомендаций;
- gpt-oss используется для объяснений и структурирования вывода, а не как
  единственный источник правды;
- если модель не вернула JSON или не успела ответить, пользователь всё равно
  получает валидный расчет по тем же рыночным данным.

Главный принцип:

```text
пользователь должен получить ответ даже при сбое локальной модели
```

## Что входит в проект

- `frontend/` - Next.js интерфейс: форма резюме, пошаговый ввод, страница результата.
- `backend/` - FastAPI API: валидация запроса, подготовка рыночных данных,
  cache/lock, строгая проверка результата и сохранение ответа.
- `ml_service/` - HTTP-граница модели: локальный deterministic stub для быстрых
  проверок или прокси к Ollama/gpt-oss.
- `nginx/` - единая точка входа: `/` ведет во frontend, `/api/*` в backend.
- `scripts/` - smoke-проверки и прогрев локальной модели.
- `docs/` - подробности API, архитектуры, live-review и деплоя.

## Как работает запрос

1. Пользователь открывает frontend на `http://localhost`.
2. Frontend отправляет профиль в `POST /api/v1/analyze`.
3. Backend нормализует должность, город, опыт и навыки.
4. Backend определяет рыночный сегмент, например
   `backend_developer:python:moscow:middle`.
5. Backend подбирает актуальные вакансии для сегмента и близких направлений.
6. Backend строит `market_evidence`: зарплатные квантили, покрытие навыков,
   недостающие навыки и заготовки рекомендаций.
7. Backend считает `request_hash`. Если такой валидный результат уже есть в
   базе, он возвращается из cache без повторного вызова модели.
8. Для нового запроса backend берет Redis-lock, чтобы одинаковые запросы не
   запускали несколько дорогих модельных вызовов одновременно.
9. Backend вызывает `ml_service`.
10. `ml_service` либо обращается к gpt-oss через Ollama, либо возвращает быстрый
    deterministic ответ в stub-режиме.
11. Backend валидирует строгий JSON-контракт.
12. Если модель вернула не JSON, неполную схему или timeout, backend строит
    `grounded-fallback` из уже подготовленных вакансий и `market_evidence`.
13. Валидный результат сохраняется в PostgreSQL и возвращается frontend.

## Источники ответа

В успешном response envelope поле `source` показывает, откуда пришел результат:

- `gpt-oss-20b` - модель вернула валидный JSON, backend его принял;
- `grounded-fallback` - модельный путь дал сбой, backend собрал ответ сам по
  рыночным данным;
- `cache` - результат уже был сохранен для такого `request_hash`.

`grounded-fallback` не использует внешние знания и не придумывает зарплаты. Он
берет только переданные вакансии, профиль пользователя и заранее рассчитанный
`market_evidence`. Поэтому это не аварийная заглушка “из воздуха”, а безопасный
способ не оставлять пользователя без результата.

## Быстрый запуск

```bash
cd /mnt/d/projects/MLtbank
cp .env.example .env
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed_test_data
```

После запуска:

```text
Приложение: http://localhost
Frontend напрямую: http://localhost:3000
Backend docs: http://localhost:8000/docs
Backend health: http://localhost:8000/health
ML health: http://localhost:8002/health
```

## Минимальная проверка API

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "title": "Python Backend Developer",
      "experience_years": 3,
      "location": "Москва",
      "skills": ["Python", "FastAPI", "PostgreSQL"],
      "resume_text": "Разрабатывал backend-сервисы на FastAPI и PostgreSQL",
      "current_salary": 150000
    },
    "options": {
      "target_salary": 250000,
      "force_refresh": false
    }
  }'
```

Ожидаемый верхний уровень ответа:

```json
{
  "status": "success",
  "source": "gpt-oss-20b",
  "data": {
    "request_hash": "...",
    "salary_range": {
      "min": 180000,
      "median": 220000,
      "max": 280000,
      "currency": "RUB"
    },
    "recommendations": []
  }
}
```

Если `source` равен `grounded-fallback`, пользовательский сценарий всё равно
успешен: модель не дала корректный JSON, но расчет построен по рыночным данным.

## Режимы ML

По умолчанию для локального запуска можно оставить быстрый stub:

```env
ML_PREDICTOR_MODE=stub
```

Для реального локального gpt-oss через Ollama:

```env
ML_PREDICTOR_MODE=openai_compatible
ML_OPENAI_BASE_URL=http://ollama:11434/v1
ML_OPENAI_MODEL_NAME=gpt-oss:20b
ML_OPENAI_API_STYLE=ollama
ML_OPENAI_TIMEOUT=25
GPT_OSS_TIMEOUT=90
```

Запуск Ollama в compose:

```bash
docker compose --profile llm up -d ollama
docker compose exec ollama ollama pull gpt-oss:20b
docker compose up -d --build --force-recreate ml_service backend frontend nginx
```

Для GPU-режима используется `docker-compose.gpu.yml`:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile llm up -d ollama
docker compose exec ollama ollama pull gpt-oss:20b
TIMEOUT_SECONDS=600 bash scripts/warm_ollama_gpu.sh
```

## Конфигурация

Основные переменные в `.env`:

```env
DATABASE_URL=postgresql+asyncpg://zarabotok:change_me_in_production@postgres:5432/zarabotok_db
REDIS_URL=redis://redis:6379/0

GPT_OSS_SERVICE_URL=http://ml_service:8001
GPT_OSS_CLIENT_MODE=service
GPT_OSS_PROMPT_VERSION=salary_estimation_prompt_v13

ML_PREDICTOR_MODE=stub
ML_OPENAI_BASE_URL=http://ollama:11434/v1
ML_OPENAI_MODEL_NAME=gpt-oss:20b
ML_OPENAI_API_STYLE=ollama

NEXT_PUBLIC_API_URL=/api/v1
NEXT_PUBLIC_ANALYZE_TIMEOUT_MS=120000
```

Для приватного демо можно включить bearer-token:

```env
API_AUTH_TOKEN=<strong-token>
NEXT_PUBLIC_API_AUTH_TOKEN=<same-token-for-private-demo-only>
```

`NEXT_PUBLIC_*` попадает в browser bundle, поэтому это удобно только для
закрытого демо. Для публичного production лучше закрывать доступ внешним
auth/proxy-слоем.

## Проверки

Полная проверка backend и ml_service:

```bash
bash scripts/run_backend_ml_checks.sh
```

Smoke для live-review:

```bash
bash scripts/live_review_smoke.sh
```

Frontend:

```bash
cd frontend
npm install
npm run lint
npm run build
```

Backend вручную:

```bash
cd backend
python -m pip install -e ".[dev]"
python -m ruff check app tests
python -m pytest
```

ML service вручную:

```bash
cd ml_service
python -m pip install -e ".[dev]"
python -m pytest tests/test_predictor.py
```

## Деплой

Подробный порядок запуска, GPU-вариант, миграции, smoke и production-like
настройки описаны в [DEPLOYMENT.md](DEPLOYMENT.md).

Короткий production-like цикл:

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build --force-recreate backend ml_service frontend nginx
docker compose exec backend alembic upgrade head
bash scripts/live_review_smoke.sh
```

Перед реальным деплоем обязательно поменять:

- `POSTGRES_PASSWORD`;
- `SECRET_KEY`;
- `API_AUTH_TOKEN` или внешний auth-контур;
- `BACKEND_CORS_ORIGINS`;
- режим `DEBUG=false`;
- стратегию резервного копирования PostgreSQL volume.
